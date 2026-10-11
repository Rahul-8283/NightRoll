"""Database queries for enrollment codes, status, and device/student management."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import asyncpg


async def create_enrollment_code(
    pool: asyncpg.Pool,
    *,
    code_hash: str,
    student_id: UUID,
    created_by: UUID | None,
    expires_at: datetime,
) -> None:
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Cancel/remove any earlier unused codes for this student
            await conn.execute(
                "delete from enrollment_codes where student_id = $1 and used_at is null",
                student_id,
            )
            await conn.execute(
                """
                insert into enrollment_codes (code_hash, student_id, created_by, expires_at)
                values ($1, $2, $3, $4)
                """,
                code_hash,
                student_id,
                created_by,
                expires_at,
            )


async def get_student_enrollment_details(
    pool: asyncpg.Pool,
    student_id: UUID,
) -> asyncpg.Record | None:
    return await pool.fetchrow(
        """
        select
          s.id as student_id,
          s.roll_number,
          s.name,
          s.room_id,
          s.enrolled_at,
          s.consent_at,
          s.consent_version,
          s.active,
          r.number as room_number,
          (exists (select 1 from face_embeddings fe where fe.student_id = s.id)) as face_enrolled,
          (exists (select 1 from devices d where d.student_id = s.id and d.active = true)) as device_enrolled,
          (
            select d.key_alias from devices d
            where d.student_id = s.id and d.active = true
            order by d.enrolled_at desc limit 1
          ) as device_security_level,
          (
            select max(rf.version) from room_fingerprints rf
            where rf.room_id = s.room_id
          ) as room_fingerprint_version
        from students s
        join rooms r on r.id = s.room_id
        where s.id = $1
        """,
        student_id,
    )


async def get_student_by_roll_number(
    pool: asyncpg.Pool,
    roll_number: str,
) -> asyncpg.Record | None:
    return await pool.fetchrow(
        """
        select s.id, s.roll_number, s.name, s.room_id, s.active, r.number as room_number
        from students s
        join rooms r on r.id = s.room_id
        where s.roll_number = $1
        """,
        roll_number,
    )


async def get_valid_code_record(
    pool: asyncpg.Pool,
    *,
    code_hash: str,
    student_id: UUID,
) -> asyncpg.Record | None:
    return await pool.fetchrow(
        """
        select code_hash, student_id, expires_at, used_at
        from enrollment_codes
        where code_hash = $1 and student_id = $2
        """,
        code_hash,
        student_id,
    )


async def delete_spent_codes(pool: asyncpg.Pool, older_than: datetime) -> int:
    """Remove codes that were used, or expired, before `older_than`. Returns how many were removed.

    A code is kept for a day after it is spent, so a student who types a stale code still hears "used" or
    "expired" instead of "invalid".
    """
    return await pool.fetchval(
        """
        with removed as (
          delete from enrollment_codes
          where coalesce(used_at, expires_at) < $1
            and (used_at is not null or expires_at < $1)
          returning 1
        )
        select count(*) from removed
        """,
        older_than,
    )
