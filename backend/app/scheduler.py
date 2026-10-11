"""Opens and closes attendance windows on the server clock.

Run as its own process: `uv run python -m app.scheduler`. Every tick is safe to repeat:
the database row lock and the state check make each transition happen once, and the
Redis claim keeps two scheduler processes from running the same job at the same time.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from redis.asyncio import Redis

from app.config import Settings, get_settings
from app.db import pool as db_pool
from app.db.queries import windows as windows_q
from app.logging import configure_logging, log_event
from app.redis import client as redis_client
from app.redis import keys
from app.services import ops
from app.services import windows as windows_service

TICK_SECONDS = 15
CLAIM_SECONDS = 120
SCHEDULER_ACTOR = "scheduler"

logger = logging.getLogger("nightroll.scheduler")


async def _claim(redis: Redis, window_id, job: str) -> bool:
    return bool(await redis.set(keys.window_lock_key(window_id, job), "1", nx=True, ex=CLAIM_SECONDS))


async def tick(settings: Settings, pool, redis: Redis) -> None:
    now = datetime.now(UTC)
    await ops.write_heartbeat(redis, now)
    await windows_service.ensure_default_windows(pool, settings, now)

    for row in await windows_q.due_to_open(pool, now):
        if not await _claim(redis, row["id"], "open"):
            continue
        try:
            await windows_service.open_window(pool, redis, row["id"], SCHEDULER_ACTOR)
        except Exception:
            logger.exception("window open failed", extra={"extra_fields": {"window_id": str(row["id"])}})

    for row in await windows_q.due_to_close(pool, now):
        if not await _claim(redis, row["id"], "close"):
            continue
        try:
            await windows_service.close_window(pool, redis, row["id"], SCHEDULER_ACTOR)
        except Exception:
            logger.exception("window close failed", extra={"extra_fields": {"window_id": str(row["id"])}})


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.LOG_LEVEL)
    pool = await db_pool.connect(settings)
    redis = await redis_client.connect(settings)

    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        tick,
        "interval",
        seconds=TICK_SECONDS,
        args=[settings, pool, redis],
        next_run_time=datetime.now(UTC),
        max_instances=1,
        coalesce=True,
        id="tick",
    )
    scheduler.start()
    log_event(
        logger, logging.INFO, "scheduler started", tick_seconds=TICK_SECONDS, server_time=datetime.now(UTC).isoformat()
    )

    try:
        await asyncio.Event().wait()
    finally:
        scheduler.shutdown(wait=False)
        await redis_client.disconnect()
        await db_pool.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
