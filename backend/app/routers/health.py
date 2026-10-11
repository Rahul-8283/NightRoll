from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from fastapi import APIRouter
from redis.exceptions import RedisError

from app.db import pool as db_pool
from app.redis import client as redis_client
from app.schemas.health import HealthOut
from app.services import ops

router = APIRouter(tags=["health"])


def _app_version() -> str:
    try:
        return version("nightroll-backend")
    except PackageNotFoundError:
        return "0.1.0"


async def _scheduler_status() -> tuple[str, float | None]:
    """Stale (reported as degraded) once the heartbeat is more than 60 seconds old, or has never been written."""
    try:
        age = await ops.scheduler_heartbeat_age(redis_client.get_client())
    except (RedisError, OSError, ValueError):
        return "degraded", None
    return ("ok" if ops.heartbeat_is_fresh(age) else "degraded"), age


@router.get("/v1/health", response_model=HealthOut)
async def health() -> HealthOut:
    db_ok = await db_pool.ping()
    redis_ok = await redis_client.ping()
    overall = "ok" if (db_ok and redis_ok) else "degraded"
    scheduler, scheduler_age = await _scheduler_status()
    return HealthOut(
        status=overall,
        db="ok" if db_ok else "degraded",
        redis="ok" if redis_ok else "degraded",
        scheduler=scheduler,
        scheduler_age_seconds=None if scheduler_age is None else round(scheduler_age, 1),
        version=_app_version(),
    )
