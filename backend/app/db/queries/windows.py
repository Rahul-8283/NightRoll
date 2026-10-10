"""Hand-written, parameterised SQL for attendance windows."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

import asyncpg

Db = asyncpg.Pool | asyncpg.Connection


async def insert_if_absent(
    db: Db, *, night: date, opens_at: datetime, closes_at: datetime, state: str
) -> asyncpg.Record | None:
    return await db.fetchrow(
        """
        insert into attendance_windows (night, opens_at, closes_at, state)
        values ($1, $2, $3, $4)
        on conflict (night) do nothing
        returning id, night, opens_at, closes_at, state
        """,
        night,
        opens_at,
        closes_at,
        state,
    )


async def get_by_id(db: Db, window_id: UUID) -> asyncpg.Record | None:
    return await db.fetchrow(
        "select id, night, opens_at, closes_at, state from attendance_windows where id = $1",
        window_id,
    )


async def lock_by_id(conn: asyncpg.Connection, window_id: UUID) -> asyncpg.Record | None:
    return await conn.fetchrow(
        "select id, night, opens_at, closes_at, state from attendance_windows where id = $1 for update",
        window_id,
    )


async def lock_by_night(conn: asyncpg.Connection, night: date) -> asyncpg.Record | None:
    return await conn.fetchrow(
        "select id, night, opens_at, closes_at, state from attendance_windows where night = $1 for update",
        night,
    )


async def update_times(
    conn: asyncpg.Connection, window_id: UUID, *, opens_at: datetime, closes_at: datetime, state: str
) -> asyncpg.Record:
    return await conn.fetchrow(
        """
        update attendance_windows set opens_at = $2, closes_at = $3, state = $4
        where id = $1
        returning id, night, opens_at, closes_at, state
        """,
        window_id,
        opens_at,
        closes_at,
        state,
    )


async def set_state(conn: asyncpg.Connection, window_id: UUID, state: str) -> asyncpg.Record:
    return await conn.fetchrow(
        """
        update attendance_windows set state = $2
        where id = $1
        returning id, night, opens_at, closes_at, state
        """,
        window_id,
        state,
    )


async def set_open(conn: asyncpg.Connection, window_id: UUID) -> asyncpg.Record:
    return await conn.fetchrow(
        """
        update attendance_windows set state = 'open', opens_at = least(opens_at, now())
        where id = $1
        returning id, night, opens_at, closes_at, state
        """,
        window_id,
    )


async def set_closed(conn: asyncpg.Connection, window_id: UUID) -> asyncpg.Record:
    # The one-second floor keeps the closes_at > opens_at check when a window is opened and closed in the same second.
    return await conn.fetchrow(
        """
        update attendance_windows
        set state = 'closed', closes_at = greatest(least(closes_at, now()), opens_at + interval '1 second')
        where id = $1
        returning id, night, opens_at, closes_at, state
        """,
        window_id,
    )


async def due_to_open(db: Db, now: datetime) -> list[asyncpg.Record]:
    return await db.fetch(
        "select id from attendance_windows where state = 'scheduled' and opens_at <= $1 order by opens_at",
        now,
    )


async def due_to_close(db: Db, now: datetime) -> list[asyncpg.Record]:
    return await db.fetch(
        "select id from attendance_windows where state = 'open' and closes_at <= $1 order by closes_at",
        now,
    )


async def open_window(db: Db) -> asyncpg.Record | None:
    return await db.fetchrow(
        """
        select id, night, opens_at, closes_at, state from attendance_windows
        where state = 'open' order by opens_at desc limit 1
        """
    )


async def next_upcoming(db: Db, now: datetime) -> asyncpg.Record | None:
    return await db.fetchrow(
        """
        select id, night, opens_at, closes_at, state from attendance_windows
        where state in ('scheduled', 'off') and closes_at > $1
        order by opens_at limit 1
        """,
        now,
    )


async def current(db: Db, now: datetime) -> asyncpg.Record | None:
    return await db.fetchrow(
        """
        select id, night, opens_at, closes_at, state from attendance_windows
        where state = 'open' or closes_at > $1
        order by (state = 'open') desc, opens_at limit 1
        """,
        now,
    )


async def latest(db: Db) -> asyncpg.Record | None:
    return await db.fetchrow(
        "select id, night, opens_at, closes_at, state from attendance_windows order by night desc limit 1"
    )


async def list_recent(db: Db, limit: int) -> list[asyncpg.Record]:
    return await db.fetch(
        "select id, night, opens_at, closes_at, state from attendance_windows order by night desc limit $1",
        limit,
    )
