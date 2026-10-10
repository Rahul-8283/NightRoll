"""Nonce and window-state keys in Redis.

A nonce is a hash `value` + `used` that expires when the window closes. Consuming it is
a single Lua step (`consume_nonce.lua`), so simultaneous requests cannot both succeed.
"""

from __future__ import annotations

import secrets
from datetime import datetime
from pathlib import Path
from uuid import UUID

from redis.asyncio import Redis

from app.redis import keys

CONSUME_LUA = (Path(__file__).resolve().parent.parent / "redis" / "consume_nonce.lua").read_text()
STATE_TTL_SECONDS = 86400


async def issue(redis: Redis, window_id: UUID, student_ids: list[UUID], closes_at: datetime) -> None:
    expires_at = int(closes_at.timestamp())
    async with redis.pipeline(transaction=False) as pipe:
        for student_id in student_ids:
            key = keys.nonce_key(window_id, student_id)
            pipe.hsetnx(key, "value", secrets.token_urlsafe(32))
            pipe.hsetnx(key, "used", "0")
            pipe.expireat(key, expires_at)
        await pipe.execute()


async def peek(redis: Redis, window_id: UUID, student_id: UUID) -> tuple[str, str | None]:
    value, used = await redis.hmget(keys.nonce_key(window_id, student_id), "value", "used")
    if value is None:
        return "missing", None
    if used == "1":
        return "already_used", None
    return "ok", value


async def consume(redis: Redis, window_id: UUID, student_id: UUID, value: str) -> str:
    script = redis.register_script(CONSUME_LUA)
    return await script(keys=[keys.nonce_key(window_id, student_id)], args=[value])


async def set_open(redis: Redis, window_id: UUID, closes_at: datetime) -> None:
    exat = int(closes_at.timestamp())
    await redis.set(keys.WINDOW_CURRENT, str(window_id), exat=exat)
    await redis.set(keys.window_state_key(window_id), "open", exat=exat)


async def set_closed(redis: Redis, window_id: UUID) -> None:
    await redis.delete(keys.WINDOW_CURRENT)
    await redis.set(keys.window_state_key(window_id), "closed", ex=STATE_TTL_SECONDS)


async def extend(redis: Redis, window_id: UUID, student_ids: list[UUID], closes_at: datetime) -> None:
    expires_at = int(closes_at.timestamp())
    async with redis.pipeline(transaction=False) as pipe:
        for student_id in student_ids:
            pipe.expireat(keys.nonce_key(window_id, student_id), expires_at)
        await pipe.execute()
    await set_open(redis, window_id, closes_at)


async def drop(redis: Redis, window_id: UUID, student_ids: list[UUID]) -> None:
    if not student_ids:
        return
    await redis.delete(*(keys.nonce_key(window_id, sid) for sid in student_ids))
