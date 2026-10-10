from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.db.queries import windows as windows_q
from app.deps import AdminWarden, CurrentWarden, DbPool, RedisClient
from app.errors import AppError
from app.schemas.dashboard import WindowHistoryOut
from app.schemas.windows import WindowIn, WindowOut
from app.services import dashboard as dashboard_service
from app.services import windows as windows_service

router = APIRouter(prefix="/v1/windows", tags=["windows"])


def _not_found() -> AppError:
    return AppError("NOT_FOUND", 404, "Window not found")


@router.post("", response_model=WindowOut)
async def upsert_window(body: WindowIn, pool: DbPool, redis: RedisClient, warden: CurrentWarden) -> WindowOut:
    row = await windows_service.create_or_update(
        pool,
        redis,
        night=body.night,
        opens_at=body.opens_at,
        closes_at=body.closes_at,
        off=body.off,
        actor=warden.user_id,
    )
    return WindowOut(**dict(row))


@router.get("/current", response_model=WindowOut)
async def current(pool: DbPool, _: CurrentWarden) -> WindowOut:
    row = await windows_service.current_window(pool)
    if row is None:
        raise _not_found()
    return WindowOut(**dict(row))


@router.get("/history", response_model=list[WindowHistoryOut])
async def window_history(pool: DbPool, _: CurrentWarden) -> list[WindowHistoryOut]:
    return await dashboard_service.window_history(pool, limit=60)


@router.get("", response_model=list[WindowOut])
async def list_windows(pool: DbPool, _: CurrentWarden) -> list[WindowOut]:
    return [WindowOut(**dict(row)) for row in await windows_q.list_recent(pool, limit=60)]


@router.post("/{window_id}/off", response_model=WindowOut)
async def mark_off(window_id: UUID, pool: DbPool, redis: RedisClient, warden: CurrentWarden) -> WindowOut:
    row = await windows_service.mark_off(pool, redis, window_id, actor=warden.user_id)
    return WindowOut(**dict(row))


@router.post("/{window_id}/open-now", response_model=WindowOut)
async def open_now(window_id: UUID, pool: DbPool, redis: RedisClient, admin: AdminWarden) -> WindowOut:
    if await windows_q.get_by_id(pool, window_id) is None:
        raise _not_found()
    if not await windows_service.open_window(pool, redis, window_id, actor=admin.user_id):
        raise AppError("WINDOW_STATE_CONFLICT", 409, "Only a scheduled window can be opened")
    return WindowOut(**dict(await windows_q.get_by_id(pool, window_id)))


@router.post("/{window_id}/close-now", response_model=WindowOut)
async def close_now(window_id: UUID, pool: DbPool, redis: RedisClient, admin: AdminWarden) -> WindowOut:
    if await windows_q.get_by_id(pool, window_id) is None:
        raise _not_found()
    if not await windows_service.close_window(pool, redis, window_id, actor=admin.user_id):
        raise AppError("WINDOW_STATE_CONFLICT", 409, "Only an open window can be closed")
    return WindowOut(**dict(await windows_q.get_by_id(pool, window_id)))
