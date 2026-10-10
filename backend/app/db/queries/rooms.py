"""Hand-written, parameterised SQL for rooms. No embedding or public key is ever selected."""

from __future__ import annotations

from uuid import UUID

import asyncpg


async def list_rooms(pool: asyncpg.Pool) -> list[asyncpg.Record]:
    return await pool.fetch(
        """
        select
          r.id, r.number, r.floor,
          count(s.id) filter (where s.active) as student_count
        from rooms r
        left join students s on s.room_id = r.id
        group by r.id, r.number, r.floor
        order by r.floor, r.number
        """
    )


async def get_room(pool: asyncpg.Pool, room_id: UUID) -> asyncpg.Record | None:
    return await pool.fetchrow(
        "select id, number, floor, subnet::text as subnet from rooms where id = $1",
        room_id,
    )


async def list_access_points(pool: asyncpg.Pool, room_id: UUID) -> list[asyncpg.Record]:
    return await pool.fetch(
        "select bssid, band from access_points where room_id = $1 order by bssid",
        room_id,
    )


async def list_students_in_room(pool: asyncpg.Pool, room_id: UUID) -> list[asyncpg.Record]:
    return await pool.fetch(
        """
        select id, roll_number, name, active, (enrolled_at is not null) as enrolled
        from students
        where room_id = $1
        order by roll_number
        """,
        room_id,
    )
