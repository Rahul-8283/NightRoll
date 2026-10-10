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
