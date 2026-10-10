"""Hand-written, parameterised SQL the verification gates read from."""

from __future__ import annotations

from uuid import UUID

import asyncpg


async def active_device_key(pool: asyncpg.Pool, student_id: UUID) -> bytes | None:
    return await pool.fetchval(
        "select public_key from devices where student_id = $1 and active = true order by enrolled_at desc limit 1",
        student_id,
    )


async def student_room_network(pool: asyncpg.Pool, student_id: UUID) -> asyncpg.Record | None:
    """The student's room, its subnet as text, and the BSSIDs of its access points."""
    return await pool.fetchrow(
        """
        select s.room_id, s.active, s.enrolled_at is not null as enrolled,
               r.subnet::text as subnet,
               coalesce(
                 (select array_agg(lower(a.bssid::text)) from access_points a where a.room_id = r.id),
                 '{}'::text[]
               ) as access_point_bssids
        from students s
        join rooms r on r.id = s.room_id
        where s.id = $1
        """,
        student_id,
    )


async def attempt_counts(pool: asyncpg.Pool, window_id: UUID, student_id: UUID) -> tuple[int, int]:
    """(all attempts, rejected attempts) this student has made in this window."""
    row = await pool.fetchrow(
        """
        select count(*) as total, count(*) filter (where verdict = 'REJECTED') as rejected
        from attendance_marks
        where window_id = $1 and student_id = $2
        """,
        window_id,
        student_id,
    )
    return int(row["total"]), int(row["rejected"])


async def window_exists(pool: asyncpg.Pool, window_id: UUID) -> bool:
    return bool(await pool.fetchval("select exists(select 1 from attendance_windows where id = $1)", window_id))


async def insert_attempt(
    conn: asyncpg.Connection,
    *,
    window_id: UUID,
    student_id: UUID,
    verdict: str,
    reasons: list[str],
    scores: str,
    attempt: int,
) -> UUID:
    return await conn.fetchval(
        """
        insert into attendance_marks (window_id, student_id, verdict, reasons, scores, attempt)
        values ($1, $2, $3, $4, $5::jsonb, $6)
        returning id
        """,
        window_id,
        student_id,
        verdict,
        reasons,
        scores,
        attempt,
    )
