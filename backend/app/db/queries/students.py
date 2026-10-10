"""Hand-written, parameterised SQL for students. No embedding or public key is ever selected."""

from __future__ import annotations

from uuid import UUID

import asyncpg


async def list_students(
    pool: asyncpg.Pool,
    *,
    room_id: UUID | None = None,
    floor: int | None = None,
) -> list[asyncpg.Record]:
    return await pool.fetch(
        """
        select
          s.id, s.roll_number, s.name, s.room_id, s.active,
          (s.enrolled_at is not null) as enrolled,
          r.number as room_number, r.floor
        from students s
        join rooms r on r.id = s.room_id
        where ($1::uuid is null or s.room_id = $1)
          and ($2::int is null or r.floor = $2)
        order by r.floor, r.number, s.roll_number
        """,
        room_id,
        floor,
    )
