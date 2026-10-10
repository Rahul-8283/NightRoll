from __future__ import annotations

import logging
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

import asyncpg
from redis.asyncio import Redis

from app.config import Settings
from app.db.queries import students as students_q
from app.db.queries import windows as windows_q
from app.errors import AppError
from app.logging import log_event
from app.services import absentees, audit, nonces

logger = logging.getLogger("nightroll.windows")


def _invalid(field: str, issue: str) -> AppError:
    return AppError("VALIDATION_FAILED", 422, "Request failed validation", [{"field": field, "issue": issue}])


def _conflict(code: str, message: str) -> AppError:
    return AppError(code, 409, message)


def _check_times(opens_at: datetime, closes_at: datetime, off: bool, now: datetime) -> None:
    if closes_at <= opens_at:
        raise _invalid("closes_at", "must be after opens_at")
    if not off and closes_at <= now:
        raise _invalid("closes_at", "must be in the future")


async def create_or_update(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    night: date,
    opens_at: datetime,
    closes_at: datetime,
    off: bool,
    actor: str,
) -> asyncpg.Record:
    now = datetime.now(UTC)
    _check_times(opens_at, closes_at, off, now)
    new_state = "off" if off else "scheduled"

    async with pool.acquire() as conn, conn.transaction():
        created = await windows_q.insert_if_absent(
            conn, night=night, opens_at=opens_at, closes_at=closes_at, state=new_state
        )
        if created is not None:
            await audit.write(
                conn,
                actor=actor,
                action="window.create",
                target_id=str(created["id"]),
                payload={"night": night.isoformat(), "state": new_state},
            )
            return created

        current = await windows_q.lock_by_night(conn, night)
        if current["state"] == "closed":
            raise _conflict("WINDOW_CLOSED", "This window has closed and cannot be edited")

        if current["state"] == "open":
            if off:
                raise _conflict("WINDOW_OPEN", "An open window cannot become an off day")
            if closes_at < current["closes_at"]:
                raise _conflict("WINDOW_OPEN", "An open window can only be extended, not shortened")
            opens_at = current["opens_at"]
            new_state = "open"

        updated = await windows_q.update_times(
            conn, current["id"], opens_at=opens_at, closes_at=closes_at, state=new_state
        )
        await audit.write(
            conn,
            actor=actor,
            action="window.update",
            target_id=str(updated["id"]),
            payload={"night": night.isoformat(), "state": new_state, "closes_at": closes_at.isoformat()},
        )
        if new_state == "open" and closes_at != current["closes_at"]:
            student_ids = await students_q.list_enrolled_student_ids(conn)
            await nonces.extend(redis, updated["id"], student_ids, closes_at)
        return updated


async def mark_off(pool: asyncpg.Pool, window_id: UUID, actor: str) -> asyncpg.Record:
    async with pool.acquire() as conn, conn.transaction():
        window = await windows_q.lock_by_id(conn, window_id)
        if window is None:
            raise AppError("NOT_FOUND", 404, "Window not found")
        if window["state"] != "scheduled":
            raise _conflict("WINDOW_STATE_CONFLICT", "Only a scheduled window can become an off day")
        updated = await windows_q.set_state(conn, window_id, "off")
        await audit.write(conn, actor=actor, action="window.off", target_id=str(window_id))
        return updated


async def open_window(pool: asyncpg.Pool, redis: Redis, window_id: UUID, actor: str) -> bool:
    async with pool.acquire() as conn, conn.transaction():
        window = await windows_q.lock_by_id(conn, window_id)
        if window is None or window["state"] != "scheduled":
            return False
        opened = await windows_q.set_open(conn, window_id)
        await audit.write(conn, actor=actor, action="window.open", target_id=str(window_id))
        student_ids = await students_q.list_enrolled_student_ids(conn)
        await nonces.issue(redis, window_id, student_ids, opened["closes_at"])
        await nonces.set_open(redis, window_id, opened["closes_at"])
    log_event(logger, logging.INFO, "window opened", window_id=str(window_id), students=len(student_ids))
    return True


async def close_window(pool: asyncpg.Pool, redis: Redis, window_id: UUID, actor: str) -> bool:
    async with pool.acquire() as conn, conn.transaction():
        window = await windows_q.lock_by_id(conn, window_id)
        if window is None or window["state"] != "open":
            return False
        await windows_q.set_closed(conn, window_id)
        absent_count = await absentees.record(conn, window_id)
        await audit.write(
            conn, actor=actor, action="window.close", target_id=str(window_id), payload={"absent": absent_count}
        )
        student_ids = await students_q.list_enrolled_student_ids(conn)

    await nonces.drop(redis, window_id, student_ids)
    await nonces.set_closed(redis, window_id)
    log_event(logger, logging.INFO, "window closed", window_id=str(window_id), absent=absent_count)
    return True


async def ensure_default_windows(pool: asyncpg.Pool, settings: Settings, now: datetime) -> None:
    tz = ZoneInfo(settings.TIMEZONE)
    today = now.astimezone(tz).date()
    for night in (today, today + timedelta(days=1)):
        opens_at = datetime.combine(night, time.fromisoformat(settings.WINDOW_DEFAULT_OPEN), tzinfo=tz)
        closes_at = datetime.combine(night, time.fromisoformat(settings.WINDOW_DEFAULT_CLOSE), tzinfo=tz)
        if closes_at <= now:
            continue
        await windows_q.insert_if_absent(pool, night=night, opens_at=opens_at, closes_at=closes_at, state="scheduled")


async def current_window(pool: asyncpg.Pool) -> asyncpg.Record | None:
    now = datetime.now(UTC)
    return await windows_q.current(pool, now) or await windows_q.latest(pool)
