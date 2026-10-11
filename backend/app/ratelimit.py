"""Fixed-window rate limits kept in Redis (Phase 12 section 4).

A limited request gets 429 with a Retry-After header. If Redis cannot be reached the limit is skipped
and logged: the verify path needs Redis anyway, and /v1/health already reports it as degraded.
"""

from __future__ import annotations

import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.errors import AppError

logger = logging.getLogger("nightroll.ratelimit")

NONCE_PER_MINUTE = 10
SIGNATURE_FAILURES_PER_MINUTE = 20
SIGNATURE_WINDOW_SECONDS = 60
WARDEN_PER_MINUTE = 300
EXPORT_PER_HOUR = 10


def _key(name: str, subject: str) -> str:
    return f"ratelimit:{name}:{subject}"


def too_many(retry_after: int, message: str = "Too many requests. Wait a moment and try again.") -> AppError:
    return AppError(
        code="RATE_LIMITED",
        status_code=429,
        message=message,
        headers={"Retry-After": str(max(1, retry_after))},
    )


async def count(redis: Redis, name: str, subject: str, window_seconds: int) -> tuple[int, int]:
    """Add one to the counter. Returns (count in this window, seconds left in it)."""
    key = _key(name, subject)
    async with redis.pipeline(transaction=False) as pipe:
        pipe.incr(key)
        pipe.ttl(key)
        total, ttl = await pipe.execute()
    if ttl < 0:
        await redis.expire(key, window_seconds)
        ttl = window_seconds
    return int(total), int(ttl)


async def enforce(redis: Redis, name: str, subject: str, limit: int, window_seconds: int) -> None:
    """Count this request and raise 429 when the subject is over `limit` in the window."""
    try:
        total, ttl = await count(redis, name, subject, window_seconds)
    except (RedisError, OSError):
        logger.warning("rate limit skipped: redis unavailable", extra={"extra_fields": {"limit": name}})
        return
    if total > limit:
        raise too_many(ttl)


async def blocked(redis: Redis, name: str, subject: str, limit: int) -> None:
    """Raise 429 when the subject already has `limit` or more in the current window, without counting this request."""
    try:
        total = await redis.get(_key(name, subject))
        ttl = await redis.ttl(_key(name, subject)) if total is not None else 0
    except (RedisError, OSError):
        return
    if total is not None and int(total) >= limit:
        raise too_many(ttl)


async def record(redis: Redis, name: str, subject: str, window_seconds: int) -> None:
    try:
        await count(redis, name, subject, window_seconds)
    except (RedisError, OSError):
        logger.warning("rate limit not recorded: redis unavailable", extra={"extra_fields": {"limit": name}})
