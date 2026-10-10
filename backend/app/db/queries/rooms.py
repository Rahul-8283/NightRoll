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


async def get_room_with_reset_status(pool: asyncpg.Pool, room_id: UUID) -> asyncpg.Record | None:
    return await pool.fetchrow(
        """
        select id, number, floor, subnet::text as subnet, fingerprint_reset_pending
        from rooms
        where id = $1
        """,
        room_id,
    )


async def set_fingerprint_reset(pool: asyncpg.Pool, room_id: UUID, reset_pending: bool) -> None:
    await pool.execute(
        "update rooms set fingerprint_reset_pending = $2 where id = $1",
        room_id,
        reset_pending,
    )


async def get_latest_room_fingerprint(pool: asyncpg.Pool, room_id: UUID) -> asyncpg.Record | None:
    return await pool.fetchrow(
        """
        select id, room_id, version, pattern, created_at
        from room_fingerprints
        where room_id = $1
        order by version desc
        limit 1
        """,
        room_id,
    )


async def list_all_access_points(pool: asyncpg.Pool) -> list[asyncpg.Record]:
    return await pool.fetch("select bssid::text, room_id, band from access_points")


async def get_student_room_id(pool: asyncpg.Pool, student_id: UUID) -> UUID | None:
    row = await pool.fetchrow("select room_id from students where id = $1", student_id)
    return row["room_id"] if row else None

