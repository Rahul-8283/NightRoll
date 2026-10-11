"""Enrollment codes, lockout tracking, and student withdrawal services."""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import asyncpg
import httpx
from redis.asyncio import Redis

from app import ratelimit
from app.config import Settings
from app.db.queries import enrollment as enrollment_q
from app.errors import AppError
from app.logging import request_headers
from app.redis import keys
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


def _inflight_key(student_id: UUID) -> str:
    return f"enrollment:inflight:{student_id}"


INFLIGHT_SECONDS = 90


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


def _locked(retry_after: int) -> AppError:
    error = ratelimit.too_many(
        retry_after,
        "Too many failed attempts. Try again in a few minutes, or ask the warden for a new code.",
    )
    error.code = "CODE_LOCKED"
    return error


async def is_student_locked_out(redis: Redis, student_id: UUID) -> bool:
    is_locked = await redis.get(_locked_key(student_id))
    return is_locked is not None


async def record_failed_attempt(redis: Redis, student_id: UUID) -> int:
    key = _failed_key(student_id)
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, LOCKOUT_WINDOW_SECONDS)
    if count >= MAX_FAILED_ATTEMPTS:
        await redis.set(_locked_key(student_id), "1", ex=LOCKOUT_WINDOW_SECONDS)
    return count


async def clear_lockout(redis: Redis, student_id: UUID) -> None:
    await redis.delete(_failed_key(student_id), _locked_key(student_id))


async def withdraw_student_consent(
    pool: asyncpg.Pool,
    redis: Redis,
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
                headers={"Authorization": f"Bearer {settings.FACE_WORKER_TOKEN}", **request_headers()},
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
    await redis.publish(
        keys.ENROLLMENT_CHANNEL,
        json.dumps({"type": "enrollment_update", "student_id": str(student_id), "enrolled": False}),
    )


def validate_p256_public_key(public_key_b64: str) -> bytes:
    import base64

    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.serialization import load_der_public_key

    try:
        der_bytes = base64.b64decode(public_key_b64.strip())
    except Exception as exc:
        raise AppError(
            code="INVALID_PUBLIC_KEY",
            status_code=400,
            message="Public key must be valid base64 DER",
        ) from exc

    try:
        key = load_der_public_key(der_bytes)
    except Exception as exc:
        raise AppError(
            code="INVALID_PUBLIC_KEY",
            status_code=400,
            message="Public key does not parse as DER SubjectPublicKeyInfo",
        ) from exc

    if not isinstance(key, ec.EllipticCurvePublicKey):
        raise AppError(code="INVALID_PUBLIC_KEY", status_code=400, message="Public key is not an elliptic curve key")

    if not isinstance(key.curve, ec.SECP256R1):
        raise AppError(
            code="INVALID_PUBLIC_KEY",
            status_code=400,
            message=f"Public key must use curve P-256 (SECP256R1), got {key.curve.name}",
        )

    return der_bytes


async def complete_student_enrollment(
    pool: asyncpg.Pool,
    redis: Redis,
    settings: Settings,
    *,
    code: str,
    roll_number: str,
    public_key_b64: str,
    key_security_level: str,
    consent_version: str,
    frames: list[tuple[str, bytes, str]],  # (filename, bytes, content_type)
) -> dict[str, Any]:
    # Validate security level
    if key_security_level not in ("strongbox", "tee", "software"):
        raise AppError(
            code="INVALID_SECURITY_LEVEL",
            status_code=400,
            message="key_security_level must be strongbox, tee, or software",
        )

    # 3.1 Validate the code against the student. Count failed attempts.
    student = await enrollment_q.get_student_by_roll_number(pool, roll_number)
    if student is None:
        raise AppError(code="NOT_FOUND", status_code=404, message=f"Student with roll number {roll_number} not found")

    student_id: UUID = student["id"]

    # Check lockout
    if await is_student_locked_out(redis, student_id):
        raise _locked(await redis.ttl(_locked_key(student_id)))

    # Validate code hash against database
    code_hash = hash_code(code)
    record = await enrollment_q.get_valid_code_record(pool, code_hash=code_hash, student_id=student_id)

    if record is None:
        failed_count = await record_failed_attempt(redis, student_id)
        if failed_count >= MAX_FAILED_ATTEMPTS:
            raise _locked(LOCKOUT_WINDOW_SECONDS)
        raise AppError(
            code="INVALID_CODE",
            status_code=400,
            message=f"Invalid enrollment code. Attempt {failed_count} of {MAX_FAILED_ATTEMPTS}.",
        )

    if record["used_at"] is not None:
        await record_failed_attempt(redis, student_id)
        raise AppError(code="USED_CODE", status_code=400, message="This enrollment code has already been used.")

    if record["expires_at"] < datetime.now(UTC):
        await record_failed_attempt(redis, student_id)
        raise AppError(
            code="EXPIRED_CODE",
            status_code=400,
            message="Enrollment code has expired. Ask the warden to issue a new code.",
        )

    # 3.2 Check the public key parses as a P-256 key
    der_public_key = validate_p256_public_key(public_key_b64)

    # One enrollment per student at a time: the face worker stores the embedding before the code is
    # claimed, so two simultaneous requests could otherwise overwrite or delete each other's work.
    if not await redis.set(_inflight_key(student_id), "1", nx=True, ex=INFLIGHT_SECONDS):
        raise AppError(
            code="ENROLLMENT_IN_PROGRESS",
            status_code=409,
            message="An enrollment for this student is already in progress.",
        )
    try:
        return await _enroll_locked(
            pool,
            settings,
            redis,
            student=student,
            code_hash=code_hash,
            roll_number=roll_number,
            der_public_key=der_public_key,
            key_security_level=key_security_level,
            consent_version=consent_version,
            frames=frames,
        )
    finally:
        await redis.delete(_inflight_key(student_id))


async def _enroll_locked(
    pool: asyncpg.Pool,
    settings: Settings,
    redis: Redis,
    *,
    student: asyncpg.Record,
    code_hash: str,
    roll_number: str,
    der_public_key: bytes,
    key_security_level: str,
    consent_version: str,
    frames: list[tuple[str, bytes, str]],
) -> dict[str, Any]:
    student_id: UUID = student["id"]

    # Check frames count
    if len(frames) < 3 or len(frames) > 5:
        raise AppError(
            code="INVALID_FRAMES",
            status_code=400,
            message=f"Enrollment requires between 3 and 5 frames, received {len(frames)}",
        )

    # 3.3 Send the frames to the face worker's /enroll.
    # If it rejects them, return its reason so the app can ask for a retake.
    # The code is not consumed on a retake.
    face_worker_url = f"{settings.FACE_WORKER_URL.rstrip('/')}/enroll"
    files_payload = [
        ("frames", (fname or f"frame_{idx}.jpg", fcontent, fctype or "image/jpeg"))
        for idx, (fname, fcontent, fctype) in enumerate(frames)
    ]

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                face_worker_url,
                data={"student_id": str(student_id)},
                files=files_payload,
                headers={"Authorization": f"Bearer {settings.FACE_WORKER_TOKEN}", **request_headers()},
            )
    except Exception as exc:
        logger.error(f"Failed to communicate with face worker: {exc}")
        raise AppError(
            code="FACE_SERVICE_UNAVAILABLE",
            status_code=503,
            message="Face verification service is currently unavailable",
        ) from exc

    if resp.status_code != 200:
        try:
            err_detail = resp.json().get("detail", "Face quality or detection check failed")
        except Exception:
            err_detail = resp.text or "Face check failed"
        raise AppError(
            code="FACE_REJECTED",
            status_code=400,
            message=str(err_detail),
        )

    # 3.4 In one transaction: mark code used, set consent_at and consent version,
    # deactivate earlier device, insert new device, set enrolled_at, write audit row
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                # Claim the code. Only one request can flip used_at from null.
                claimed = await conn.fetchval(
                    "update enrollment_codes set used_at = now() where code_hash = $1 and used_at is null returning 1",
                    code_hash,
                )
                if claimed is None:
                    raise AppError(
                        code="USED_CODE", status_code=400, message="This enrollment code has already been used."
                    )

                # Update student
                await conn.execute(
                    """
                    update students
                    set consent_at = now(), consent_version = $2, enrolled_at = now()
                    where id = $1
                    """,
                    student_id,
                    consent_version,
                )

                # Deactivate earlier device
                await conn.execute(
                    "update devices set active = false where student_id = $1 and active = true",
                    student_id,
                )

                # Insert new device
                await conn.execute(
                    """
                    insert into devices (student_id, public_key, key_alias, active, enrolled_at)
                    values ($1, $2, $3, true, now())
                    """,
                    student_id,
                    der_public_key,
                    key_security_level,
                )

                # Write audit row
                await audit.write(
                    conn,
                    actor=str(student_id),
                    action="student.enrolled",
                    target_id=str(student_id),
                    payload={
                        "roll_number": roll_number,
                        "key_security_level": key_security_level,
                        "consent_version": consent_version,
                    },
                )
    except AppError:
        # The code was already claimed by another request, which owns the embedding now.
        raise
    except Exception as exc:
        # If step 3.4 fails after face worker stored an embedding, delete it
        logger.error(f"Enrollment transaction failed, rolling back embedding: {exc}")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.delete(
                    f"{settings.FACE_WORKER_URL.rstrip('/')}/students/{student_id}/embedding",
                    headers={"Authorization": f"Bearer {settings.FACE_WORKER_TOKEN}", **request_headers()},
                )
        except Exception as rollback_err:
            logger.error(f"Failed to delete face embedding on rollback: {rollback_err}")
        raise

    # Clear lockout counters
    await clear_lockout(redis, student_id)
    await redis.publish(
        keys.ENROLLMENT_CHANNEL,
        json.dumps({"type": "enrollment_update", "student_id": str(student_id), "enrolled": True}),
    )

    # 3.5 Return {student_id, room_id, room_number}
    return {
        "student_id": student["id"],
        "room_id": student["room_id"],
        "room_number": student["room_number"],
    }
