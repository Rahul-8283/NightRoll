"""Hand-written, parameterised SQL for students. No embedding or public key is ever selected."""

from __future__ import annotations

from uuid import UUID

import asyncpg


async def list_enrolled_student_ids(db: asyncpg.Pool | asyncpg.Connection) -> list[UUID]:
    rows = await db.fetch("select id from students where active and enrolled_at is not null")
    return [row["id"] for row in rows]


async def get_active_enrolled(pool: asyncpg.Pool, student_id: UUID) -> asyncpg.Record | None:
    return await pool.fetchrow(
        "select id, room_id from students where id = $1 and active and enrolled_at is not null",
        student_id,
    )


async def list_students(
    pool: asyncpg.Pool,
    *,
    room_id: UUID | None = None,
    floor: int | None = None,
    search: str | None = None,
) -> list[asyncpg.Record]:
    pattern = None
    if search:
        escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
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
          and ($3::text is null or s.name ilike $3 or s.roll_number ilike $3)
        order by r.floor, r.number, s.roll_number
        """,
        room_id,
        floor,
        pattern,
    )


async def set_student_room(pool: asyncpg.Pool, student_id: UUID, room_id: UUID) -> asyncpg.Record | None:
    return await pool.fetchrow(
        "update students set room_id = $2 where id = $1 returning id, room_id",
        student_id,
        room_id,
    )
