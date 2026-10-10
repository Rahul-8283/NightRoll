"""Assembles the warden dashboard's views from the database.

The live feed and the polling fallback both use these functions, so they cannot disagree.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

import asyncpg

from app.db.queries import dashboard as dash_q
from app.db.queries import windows as windows_q
from app.schemas.dashboard import (
    MarkDetail,
    ReasonOut,
    RecentMark,
    RoomCount,
    RoomStudentStatus,
    RoomTonightOut,
    RoomUpdateEvent,
    ScorerOut,
    TonightOut,
    Totals,
    WindowBrief,
    WindowHistoryOut,
)
from app.services.verification.reasons import reason

RECENT_LIMIT = 20
NOT_CONFIRMED = "Your attendance could not be confirmed from here."


def _reason_out(code: str) -> ReasonOut:
    # Old marks may carry a code that is no longer in the catalogue; never fail the page for it.
    try:
        return ReasonOut(code=code, message=reason(code).message)
    except KeyError:
        return ReasonOut(code=code, message=NOT_CONFIRMED)


def _window(row) -> WindowBrief | None:
    if row is None:
        return None
    return WindowBrief(
        id=row["id"], night=row["night"], opens_at=row["opens_at"], closes_at=row["closes_at"], state=row["state"]
    )


def _recent(row) -> RecentMark:
    return RecentMark(
        mark_id=row["mark_id"],
        verdict=row["verdict"],
        reasons=[_reason_out(code) for code in row["reasons"] or []],
        marked_at=row["marked_at"],
        room_number=row["room_number"],
        student_name=row["student_name"],
        score=float(row["score"]) if row["score"] is not None else None,
    )


async def _current_window(pool: asyncpg.Pool):
    return await windows_q.current(pool, datetime.now(UTC))


async def tonight(pool: asyncpg.Pool) -> TonightOut:
    window = await _current_window(pool)
    window_id = window["id"] if window is not None else None
    counts = await dash_q.room_counts(pool, window_id)
    rooms = [
        RoomCount(
            room_id=row["room_id"],
            number=row["number"],
            floor=row["floor"],
            present=row["present"],
            total=row["total"],
            pending_review=row["pending_review"],
            rejected=row["rejected"],
        )
        for row in counts
    ]
    enrolled = sum(room.total for room in rooms)
    present = sum(room.present for room in rooms)
    pending = sum(room.pending_review for room in rooms)
    recent = [_recent(row) for row in await dash_q.recent_marks(pool, window_id, RECENT_LIMIT)] if window_id else []
    return TonightOut(
        window=_window(window),
        totals=Totals(
            enrolled=enrolled,
            present=present,
            pending_review=pending,
            not_marked=max(0, enrolled - present - pending),
            rejected=sum(room.rejected for room in rooms),
        ),
        rooms=rooms,
        recent=recent,
    )


async def room_update(pool: asyncpg.Pool, room_id: UUID, mark_id: UUID | None) -> RoomUpdateEvent | None:
    """The counts for one room after a mark, plus that mark, for the live feed."""
    window = await _current_window(pool)
    if window is None:
        return None
    rows = await dash_q.room_counts(pool, window["id"])
    row = next((r for r in rows if r["room_id"] == room_id), None)
    if row is None:
        return None
    last = None
    if mark_id is not None:
        mark = await dash_q.mark_summary(pool, mark_id)
        if mark is not None:
            last = _recent(mark)
    return RoomUpdateEvent(
        room_id=room_id,
        present=row["present"],
        total=row["total"],
        pending_review=row["pending_review"],
        rejected=row["rejected"],
        last=last,
    )


async def room_tonight(pool: asyncpg.Pool, room_id: UUID, room_row) -> RoomTonightOut:
    window = await _current_window(pool)
    window_id = window["id"] if window is not None else None
    students = []
    for row in await dash_q.room_students_with_marks(pool, room_id, window_id):
        mark = None
        if row["mark_id"] is not None:
            scores = row["scores"] if isinstance(row["scores"], dict) else json.loads(row["scores"] or "{}")
            mark = MarkDetail(
                mark_id=row["mark_id"],
                verdict=row["verdict"],
                score=float(row["score"]) if row["score"] is not None else None,
                reasons=[_reason_out(code) for code in row["reasons"] or []],
                marked_at=row["marked_at"],
                attempt=row["attempt"],
                scorers=[ScorerOut(**item) for item in scores.get("scorers", [])],
            )
        students.append(
            RoomStudentStatus(
                student_id=row["student_id"],
                roll_number=row["roll_number"],
                name=row["name"],
                active=row["active"],
                enrolled=row["enrolled"],
                mark=mark,
            )
        )
    return RoomTonightOut(
        room_id=room_id,
        number=room_row["number"],
        floor=room_row["floor"],
        window=_window(window),
        students=students,
    )


async def window_history(pool: asyncpg.Pool, limit: int) -> list[WindowHistoryOut]:
    return [
        WindowHistoryOut(
            id=row["id"],
            night=row["night"],
            opens_at=row["opens_at"],
            closes_at=row["closes_at"],
            state=row["state"],
            present=row["present"],
            enrolled=row["enrolled"],
        )
        for row in await dash_q.window_history(pool, limit)
    ]
