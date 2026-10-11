"""The admin System page and the alert banner every warden sees (Phase 12, tasks 6.4 and 6.5)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.deps import AdminWarden, CurrentWarden, DbPool, RedisClient
from app.schemas.system import AlertsOut, SystemOut
from app.services import system as system_service

router = APIRouter(prefix="/v1", tags=["system"])


@router.get("/alerts", response_model=AlertsOut)
async def alerts(
    pool: DbPool, redis: RedisClient, _: CurrentWarden, settings: Annotated[Settings, Depends(get_settings)]
) -> AlertsOut:
    return AlertsOut(alerts=await system_service.alerts(settings, pool, redis))


@router.get("/system", response_model=SystemOut)
async def system(
    pool: DbPool, redis: RedisClient, _: AdminWarden, settings: Annotated[Settings, Depends(get_settings)]
) -> SystemOut:
    return await system_service.overview(settings, pool, redis)
