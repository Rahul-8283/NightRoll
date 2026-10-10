"""Warden review endpoints: the queue, one mark, approve or decline, override and manual marks (Phase 11 section 2)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.db.queries import windows as windows_q
from app.deps import CurrentWarden, DbPool, RedisClient
from app.schemas.reviews import (
    AbsenteeListOut,
    FramesViewIn,
    FramesViewOut,
    ManualMarkIn,
    ManualMarkOut,
    MarkDecisionOut,
    MarkDetailOut,
    OverrideIn,
    ReviewDecisionIn,
    ReviewItem,
)
from app.services import absentees as absentees_svc
from app.services import frames as frames_svc
from app.services import review as review_svc

router = APIRouter(tags=["reviews"])


@router.get("/v1/reviews", response_model=list[ReviewItem])
async def review_queue(pool: DbPool, _: CurrentWarden, window_id: UUID | None = None) -> list[ReviewItem]:
    """Marks awaiting a decision, oldest first. Defaults to tonight's window."""
    target = window_id or await review_svc.current_window_id(pool)
    if target is None:
        return []
    return await review_svc.awaiting(pool, target)


@router.get("/v1/attendance/marks/{mark_id}", response_model=MarkDetailOut)
async def mark_detail(mark_id: UUID, pool: DbPool, _: CurrentWarden) -> MarkDetailOut:
    return await review_svc.mark_detail(pool, mark_id)


@router.post("/v1/attendance/marks/{mark_id}/review", response_model=MarkDecisionOut)
async def decide_review(
    mark_id: UUID, body: ReviewDecisionIn, pool: DbPool, redis: RedisClient, warden: CurrentWarden
) -> MarkDecisionOut:
    return await review_svc.review(pool, redis, mark_id, body, warden)


@router.post("/v1/attendance/marks/{mark_id}/override", response_model=MarkDecisionOut)
async def override_mark(
    mark_id: UUID, body: OverrideIn, pool: DbPool, redis: RedisClient, warden: CurrentWarden
) -> MarkDecisionOut:
    return await review_svc.override(pool, redis, mark_id, body, warden)


@router.post("/v1/attendance/manual", response_model=ManualMarkOut)
async def manual_mark(body: ManualMarkIn, pool: DbPool, redis: RedisClient, warden: CurrentWarden) -> ManualMarkOut:
    return await review_svc.manual_mark(pool, redis, body, warden)


@router.post("/v1/attendance/marks/{mark_id}/frames/view", response_model=FramesViewOut)
async def view_frames(
    mark_id: UUID,
    body: FramesViewIn,
    pool: DbPool,
    warden: CurrentWarden,
    settings: Annotated[Settings, Depends(get_settings)],
) -> FramesViewOut:
    """Signed links to a disputed mark's frames. Needs a written reason, which is audited before any link is made."""
    result = await frames_svc.view_frames(pool, settings, mark_id, body.reason, warden)
    return FramesViewOut(**result)


@router.get("/v1/attendance/absentees", response_model=AbsenteeListOut)
async def absentees(pool: DbPool, _: CurrentWarden, window_id: UUID | None = None) -> AbsenteeListOut:
    """Students not present in tonight's window, or the one given. Grouped by floor on the page."""
    if window_id is None:
        window = await windows_q.current(pool, datetime.now(UTC))
    else:
        window = await windows_q.get_by_id(pool, window_id)
    target = window["id"] if window is not None else None
    state = window["state"] if window is not None else None
    return await absentees_svc.list_for_window(pool, target, state)
