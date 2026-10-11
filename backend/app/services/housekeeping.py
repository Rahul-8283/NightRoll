"""Housekeeping jobs (Phase 12, section 5): clearing spent enrollment codes and recording room health.

Frame cleanup runs in the face worker and the heartbeat in the scheduler. These two run in the scheduler's
process, and each leaves a record in Redis (`ops.record_job`) for the System page.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.db.queries import enrollment as enrollment_q
from app.logging import log_event
from app.services import dashboard as dashboard_service
from app.services import ops

logger = logging.getLogger("nightroll.housekeeping")

SPENT_CODE_GRACE = timedelta(days=1)
CODE_CLEANUP_JOB = "enrollment-code-cleanup"
ROOM_HEALTH_JOB = "room-health"


async def clear_spent_enrollment_codes(pool: asyncpg.Pool, redis: Redis) -> int:
    removed = await enrollment_q.delete_spent_codes(pool, datetime.now(UTC) - SPENT_CODE_GRACE)
    await ops.record_job(redis, CODE_CLEANUP_JOB, removed=removed)
    log_event(logger, logging.INFO, "spent enrollment codes cleared", removed=removed)
    return removed


async def snapshot_room_health(pool: asyncpg.Pool, redis: Redis, window_id: UUID) -> dict[str, list[str]]:
    """Work out the Phase 11 flags for every room once a window has closed, and keep the result.

    The dashboard computes the same flags live from the marks; this is the record of how the night ended.
    Only rooms with a flag are kept.
    """
    flags = {
        str(room_id): room_flags
        for room_id, room_flags in (await dashboard_service.room_health(pool, window_id)).items()
        if room_flags
    }
    await ops.record_job(redis, ROOM_HEALTH_JOB, window_id=str(window_id), flagged=flags)
    log_event(logger, logging.INFO, "room health recorded", window_id=str(window_id), rooms_flagged=len(flags))
    return flags
