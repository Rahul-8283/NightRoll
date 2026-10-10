"""Enrollment codes, lockout tracking, and student withdrawal services."""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import asyncpg
import httpx
from redis.asyncio import Redis

from app.config import Settings
from app.db.queries import enrollment as enrollment_q
from app.errors import AppError
from app.services import audit

logger = logging.getLogger("nightroll.enrollment")

# 8 characters from an alphabet without look-alike characters (omits 0, 1, I, L, O)
ENROLLMENT_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
EXPIRY_MINUTES = 15
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_WINDOW_SECONDS = 900  # 15 minutes


def generate_code() -> str:
    return "".join(secrets.choice(ENROLLMENT_ALPHABET) for _ in range(8))


def hash_code(code: str) -> str:
    return hashlib.sha256(code.strip().upper().encode("utf-8")).hexdigest()


def _failed_key(student_id: UUID) -> str:
    return f"enrollment:failed:{student_id}"


def _locked_key(student_id: UUID) -> str:
    return f"enrollment:locked:{student_id}"


async def issue_enrollment_code(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    student_id: UUID,
    warden_id: UUID | None,
) -> tuple[str, datetime]:
    # 1. Verify student exists
    row = await pool.fetchrow("select id from students where id = $1", student_id)
    if row is None:
        raise AppError(code="NOT_FOUND", status_code=404, message="Student not found")

    code = generate_code()
    code_hash = hash_code(code)
    expires_at = datetime.now(UTC) + timedelta(minutes=EXPIRY_MINUTES)

    # 2. Store SHA-256 in DB, cancelling any earlier unused codes
    await enrollment_q.create_enrollment_code(
        pool,
        code_hash=code_hash,
        student_id=student_id,
        created_by=warden_id,
        expires_at=expires_at,
    )

    # 3. Clear any lockout or failed attempts count for this student
    await redis.delete(_failed_key(student_id), _locked_key(student_id))

    return code, expires_at


async def is_student_locked_out(redis: Redis, student_id: UUID) -> bool:
    is_locked = await redis.get(_locked_key(student_id))
    return is_locked is not None


async def record_failed_attempt(redis: Redis, student_id: UUID) -> int:
    key = _failed_key(student_id)
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, LOCKOUT_WINDOW_SECONDS)
    if count >= MAX_FAILED_ATTEMPTS:
        await redis.set(_locked_key(student_id), "1")
    return count


async def clear_lockout(redis: Redis, student_id: UUID) -> None:
    await redis.delete(_failed_key(student_id), _locked_key(student_id))


async def withdraw_student_consent(
    pool: asyncpg.Pool,
    settings: Settings,
    *,
    student_id: UUID,
    actor_id: str,
) -> None:
    # 1. Verify student exists
    student = await pool.fetchrow("select id, roll_number from students where id = $1", student_id)
    if student is None:
        raise AppError(code="NOT_FOUND", status_code=404, message="Student not found")

    # 2. Delete embedding in face worker
    face_worker_url = f"{settings.FACE_WORKER_URL.rstrip('/')}/students/{student_id}/embedding"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.delete(
                face_worker_url,
                headers={"Authorization": f"Bearer {settings.FACE_WORKER_TOKEN}"},
            )
            if resp.status_code not in (200, 404):
                logger.warning(
                    f"Face worker returned status {resp.status_code} during withdrawal for student {student_id}"
                )
    except Exception as exc:
        logger.warning(f"Could not reach face worker to delete embedding for student {student_id}: {exc}")

    # 3. DB Transaction: deactivate devices, clear enrolled_at and consent_at, write audit row
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("update devices set active = false where student_id = $1", student_id)
            await conn.execute(
                """
                update students
                set enrolled_at = null, consent_at = null, consent_version = null
                where id = $1
                """,
                student_id,
            )
            # Remove any pending enrollment codes
            await conn.execute("delete from enrollment_codes where student_id = $1", student_id)

            await audit.write(
                conn,
                actor=actor_id,
                action="student.consent_withdrawn",
                target_id=str(student_id),
                payload={"roll_number": student["roll_number"]},
            )
