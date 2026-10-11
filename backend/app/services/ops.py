"""Operational state the scheduler leaves in Redis: its heartbeat and the last run of each housekeeping job.

The dashboard's System page and /v1/health read these. The scheduler is a separate process, so Redis is the only
place it can say "I am alive" and "I last did this".
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from redis.asyncio import Redis

from app.redis import keys

# A scheduler that has not written its heartbeat for this long is reported as stale.
HEARTBEAT_STALE_SECONDS = 60
# The heartbeat is kept long after it goes stale, so "last seen 3 hours ago" can still be shown.
HEARTBEAT_KEEP_SECONDS = 86400


async def write_heartbeat(redis: Redis, now: datetime) -> None:
    await redis.set(keys.SCHEDULER_HEARTBEAT, now.isoformat(), ex=HEARTBEAT_KEEP_SECONDS)


async def last_heartbeat(redis: Redis, key: str = keys.SCHEDULER_HEARTBEAT) -> datetime | None:
    raw = await redis.get(key)
    return datetime.fromisoformat(raw) if raw else None


async def scheduler_heartbeat_age(redis: Redis, key: str = keys.SCHEDULER_HEARTBEAT) -> float | None:
    """Seconds since the scheduler last wrote its heartbeat, or None if it never has (or the record expired)."""
    beat = await last_heartbeat(redis, key)
    return None if beat is None else max(0.0, (datetime.now(UTC) - beat).total_seconds())


def heartbeat_is_fresh(age: float | None) -> bool:
    return age is not None and age <= HEARTBEAT_STALE_SECONDS


async def record_job(redis: Redis, job: str, **result) -> None:
    """Remember when a housekeeping job last finished and what it did."""
    entry = {"at": datetime.now(UTC).isoformat(), **result}
    await redis.set(keys.job_record_key(job), json.dumps(entry), ex=30 * 86400)


async def last_job(redis: Redis, job: str) -> dict | None:
    raw = await redis.get(keys.job_record_key(job))
    return json.loads(raw) if raw else None
