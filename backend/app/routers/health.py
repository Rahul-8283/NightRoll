from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from fastapi import APIRouter

from app.db import pool as db_pool
from app.redis import client as redis_client
from app.schemas.health import HealthOut

router = APIRouter(tags=["health"])


def _app_version() -> str:
    try:
        return version("nightroll-backend")
    except PackageNotFoundError:
        return "0.1.0"


@router.get("/v1/health", response_model=HealthOut)
async def health() -> HealthOut:
    db_ok = await db_pool.ping()
    redis_ok = await redis_client.ping()
    overall = "ok" if (db_ok and redis_ok) else "degraded"
    return HealthOut(
        status=overall,
        db="ok" if db_ok else "degraded",
        redis="ok" if redis_ok else "degraded",
        version=_app_version(),
    )
