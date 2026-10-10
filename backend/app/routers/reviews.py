"""Warden review endpoints: the queue, one mark, approve or decline, override and manual marks (Phase 11 section 2)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.deps import CurrentWarden, DbPool, RedisClient
from app.schemas.reviews import (
    ManualMarkIn,
    ManualMarkOut,
    MarkDecisionOut,
    MarkDetailOut,
    OverrideIn,
    ReviewDecisionIn,
    ReviewItem,
)
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
