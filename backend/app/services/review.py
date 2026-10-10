"""Warden decisions on attendance: review, override and manual marks.

Marks are never edited. Each action adds a `reviews` row or a manual mark, writes its audit row in the same
transaction, and publishes a room update so every open dashboard changes at once.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.auth.supabase import Warden
from app.db.queries import reviews as review_q
from app.db.queries import windows as windows_q
from app.errors import AppError
from app.redis import keys
from app.schemas.dashboard import ScorerOut
from app.schemas.reviews import (
    AttemptOut,
    DecisionOut,
    ManualMarkIn,
    ManualMarkOut,
    MarkDecisionOut,
    MarkDetailOut,
    OverrideIn,
    ReviewDecisionIn,
    ReviewItem,
)
from app.services import audit
from app.services.dashboard import reason_out

MIN_NOTE_LENGTH = 10
MANUAL_GRACE = timedelta(hours=24)


def actor_of(warden: Warden) -> str:
    """The name written to reviews, the audit log and exports: the warden's email when known."""
    return warden.email or warden.user_id


def scorers_of(scores) -> list[ScorerOut]:
    data = scores if isinstance(scores, dict) else json.loads(scores or "{}")
    return [ScorerOut(**item) for item in data.get("scorers", [])]


def _review_item(row: asyncpg.Record, *, attempts_tonight: int, fingerprint_created_at: datetime | None) -> ReviewItem:
    return ReviewItem(
        mark_id=row["mark_id"],
        window_id=row["window_id"],
        student_id=row["student_id"],
        student_name=row["student_name"],
        roll_number=row["roll_number"],
        room_id=row["room_id"],
        room_number=row["room_number"],
        floor=row["floor"],
        marked_at=row["marked_at"],
        score=float(row["score"]) if row["score"] is not None else None,
        attempt=row["attempt"],
        attempts_tonight=attempts_tonight,
        reasons=[reason_out(code) for code in row["reasons"] or []],
        scorers=scorers_of(row["scores"]),
        fingerprint_created_at=fingerprint_created_at,
        frames_available=row["frames_path"] is not None,
    )


async def awaiting(pool: asyncpg.Pool, window_id: UUID) -> list[ReviewItem]:
    return [
        _review_item(
            row,
            attempts_tonight=row["attempts_tonight"],
            fingerprint_created_at=row["fingerprint_created_at"],
        )
        for row in await review_q.awaiting_review(pool, window_id)
    ]


async def current_window_id(pool: asyncpg.Pool) -> UUID | None:
    window = await windows_q.current(pool, datetime.now(UTC))
    return window["id"] if window is not None else None


async def mark_detail(pool: asyncpg.Pool, mark_id: UUID) -> MarkDetailOut:
    row = await review_q.get_mark(pool, mark_id)
    if row is None:
        raise AppError(code="NOT_FOUND", status_code=404, message="Mark not found")
    attempts_tonight = await pool.fetchval(
        "select count(*) from attendance_marks where window_id = $1 and student_id = $2",
        row["window_id"],
        row["student_id"],
    )
    fingerprint_created_at = await pool.fetchval(
        "select created_at from room_fingerprints where room_id = $1 order by version desc limit 1",
        row["room_id"],
    )
    item = _review_item(row, attempts_tonight=attempts_tonight, fingerprint_created_at=fingerprint_created_at)
    earlier = [
        AttemptOut(
            mark_id=a["mark_id"],
            verdict=a["verdict"],
            reasons=[reason_out(code) for code in a["reasons"] or []],
            marked_at=a["marked_at"],
            attempt=a["attempt"],
        )
        for a in await review_q.earlier_attempts(pool, row["window_id"], row["student_id"], mark_id)
    ]
    decisions = [
        DecisionOut(
            decision=d["decision"],
            status=d["status"],
            reviewed_by=d["reviewed_by"],
            note=d["note"],
            reviewed_at=d["reviewed_at"],
        )
        for d in await review_q.reviews_for_mark(pool, mark_id)
    ]
    status = await review_q.student_status(pool, row["window_id"], row["student_id"])
    return MarkDetailOut(
        **item.model_dump(),
        verdict=row["verdict"],
        earlier_attempts=earlier,
        decisions=decisions,
        effective_status=status["status"] if status else "NOT_MARKED",
    )


async def _publish(redis: Redis, room_id: UUID, mark_id: UUID, verdict: str) -> None:
    await redis.publish(
        keys.MARK_RECORDED_CHANNEL,
        json.dumps({"room_id": str(room_id), "verdict": verdict, "mark_id": str(mark_id)}),
    )


async def _decision_result(pool: asyncpg.Pool, mark: asyncpg.Record) -> MarkDecisionOut:
    status = await review_q.student_status(pool, mark["window_id"], mark["student_id"])
    return MarkDecisionOut(
        mark_id=mark["mark_id"],
        student_id=mark["student_id"],
        status=status["status"] if status else "NOT_MARKED",
        decided_how=status["decided_how"] if status else None,
    )


async def review(
    pool: asyncpg.Pool, redis: Redis, mark_id: UUID, body: ReviewDecisionIn, warden: Warden
) -> MarkDecisionOut:
    """Approve or decline a mark in review. Only one decision is allowed per mark."""
    if body.decision == "DECLINED" and (body.note is None or len(body.note.strip()) < MIN_NOTE_LENGTH):
        raise AppError(
            code="NOTE_REQUIRED", status_code=422, message="A decline needs a note of at least 10 characters"
        )
    found = await review_q.get_mark(pool, mark_id)
    if found is None:
        raise AppError(code="NOT_FOUND", status_code=404, message="Mark not found")
    actor = actor_of(warden)
    async with pool.acquire() as conn:
        async with conn.transaction():
            locked = await review_q.lock_mark(conn, mark_id)
            if locked["verdict"] != "NEEDS_REVIEW":
                raise AppError(
                    code="NOT_AWAITING_REVIEW", status_code=409, message="This mark is not waiting for review"
                )
            if await conn.fetchval("select exists (select 1 from reviews where mark_id = $1)", mark_id):
                raise AppError(code="ALREADY_DECIDED", status_code=409, message="This mark already has a decision")
            await review_q.insert_review(
                conn, mark_id=mark_id, decision=body.decision, status=None, reviewed_by=actor, note=body.note
            )
            await audit.write(
                conn,
                actor=actor,
                action="review.decided",
                target_id=str(mark_id),
                payload={"decision": body.decision, "note": body.note, "student_id": str(found["student_id"])},
            )
    await _publish(redis, found["room_id"], mark_id, "NEEDS_REVIEW")
    return await _decision_result(pool, found)


async def override(
    pool: asyncpg.Pool, redis: Redis, mark_id: UUID, body: OverrideIn, warden: Warden
) -> MarkDecisionOut:
    """Set a student's status for a window, whatever the marks say.

    A later override replaces an earlier one. Both stay in the audit log.
    """
    found = await review_q.get_mark(pool, mark_id)
    if found is None:
        raise AppError(code="NOT_FOUND", status_code=404, message="Mark not found")
    actor = actor_of(warden)
    async with pool.acquire() as conn:
        async with conn.transaction():
            await review_q.lock_mark(conn, mark_id)
            await review_q.insert_review(
                conn, mark_id=mark_id, decision="OVERRIDDEN", status=body.status, reviewed_by=actor, note=body.note
            )
            await audit.write(
                conn,
                actor=actor,
                action="mark.overridden",
                target_id=str(mark_id),
                payload={"status": body.status, "note": body.note, "student_id": str(found["student_id"])},
            )
    verdict = found["verdict"]
    await _publish(redis, found["room_id"], mark_id, verdict)
    return await _decision_result(pool, found)


async def manual_mark(pool: asyncpg.Pool, redis: Redis, body: ManualMarkIn, warden: Warden) -> ManualMarkOut:
    """Record presence by hand.

    Allowed from opening until 24 hours after close. After that, only an admin can record it.
    """
    student = await review_q.active_enrolled_student(pool, body.student_id)
    if student is None:
        raise AppError(code="NOT_FOUND", status_code=404, message="Enrolled student not found")
    actor = actor_of(warden)
    now = datetime.now(UTC)
    async with pool.acquire() as conn:
        async with conn.transaction():
            window = await review_q.lock_window(conn, body.window_id)
            if window is None:
                raise AppError(code="NOT_FOUND", status_code=404, message="Window not found")
            if window["state"] == "off":
                raise AppError(code="WINDOW_OFF", status_code=409, message="Tonight is an off night")
            if now < window["opens_at"]:
                raise AppError(code="WINDOW_NOT_OPEN", status_code=409, message="The window has not opened yet")
            after_close = now > window["closes_at"]
            if now > window["closes_at"] + MANUAL_GRACE and warden.role != "admin":
                raise AppError(
                    code="MANUAL_WINDOW_CLOSED",
                    status_code=403,
                    message="More than 24 hours have passed since close. Ask an admin to record this.",
                )
            status = await review_q.student_status(conn, body.window_id, body.student_id)
            if status is not None and status["status"] == "PRESENT":
                raise AppError(code="ALREADY_PRESENT", status_code=409, message="This student is already present")
            attempt = await review_q.next_attempt(conn, body.window_id, body.student_id)
            mark_id = await review_q.insert_manual_mark(
                conn, window_id=body.window_id, student_id=body.student_id, attempt=attempt
            )
            await review_q.insert_review(
                conn, mark_id=mark_id, decision="MANUAL", status=None, reviewed_by=actor, note=body.note
            )
            await audit.write(
                conn,
                actor=actor,
                action="attendance.manual",
                target_id=str(mark_id),
                payload={
                    "student_id": str(body.student_id),
                    "window_id": str(body.window_id),
                    "note": body.note,
                    "after_close": after_close,
                },
            )
    await _publish(redis, student["room_id"], mark_id, "MANUAL")
    return ManualMarkOut(
        mark_id=mark_id,
        student_id=body.student_id,
        window_id=body.window_id,
        status="PRESENT",
    )
