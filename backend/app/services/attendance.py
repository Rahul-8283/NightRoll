from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.db.queries import reviews as review_q
from app.db.queries import students as students_q
from app.db.queries import windows as windows_q
from app.errors import AppError
from app.services import nonces

CHALLENGE = ["blink", "turn_left"]


async def _outcome(pool: asyncpg.Pool, window_id: UUID, student_id: UUID) -> dict[str, Any]:
    """The student's effective status in this window, after any warden review (Phase 11 section 8)."""
    row = await review_q.student_status(pool, window_id, student_id)
    if row is None:
        return {}
    return {"outcome": row["status"], "decided_how": row["decided_how"]}


def _decided_state(window_id: UUID, outcome: dict[str, Any]) -> dict[str, Any] | None:
    """A state the warden has settled for the student, or None when the student may still act."""
    if outcome.get("outcome") == "PRESENT":
        return {"state": "marked", "window_id": window_id, **outcome}
    if outcome.get("outcome") == "ABSENT" and outcome.get("decided_how") in ("declined", "override"):
        return {"state": "absent", "window_id": window_id, **outcome}
    if outcome.get("outcome") == "PENDING":
        return {"state": "pending", "window_id": window_id, **outcome}
    return None


async def student_status(pool: asyncpg.Pool, redis: Redis, student_id: UUID) -> dict[str, Any]:
    if await students_q.get_active_enrolled(pool, student_id) is None:
        raise AppError(code="NOT_ENROLLED", status_code=403, message="This student is not enrolled")

    window = await windows_q.open_window(pool)
    if window is not None:
        window_id = window["id"]
        outcome = await _outcome(pool, window_id, student_id)
        settled = _decided_state(window_id, outcome)
        if settled is not None:
            return settled

        status, nonce, challenge = await nonces.peek(redis, window_id, student_id)
        if status == "missing":
            await nonces.issue(redis, window_id, [student_id], window["closes_at"])
            status, nonce, challenge = await nonces.peek(redis, window_id, student_id)
        if status == "ok":
            return {
                "state": "open",
                "window_id": window_id,
                "nonce": nonce,
                "closes_at": window["closes_at"],
                "challenge": challenge or CHALLENGE,
                **outcome,
            }
        return {"state": "pending", "window_id": window_id, **outcome}

    tonight = await windows_q.current(pool, datetime.now(UTC))
    if tonight is not None and tonight["state"] == "closed":
        outcome = await _outcome(pool, tonight["id"], student_id)
        settled = _decided_state(tonight["id"], outcome)
        if settled is not None:
            return settled

    upcoming = await windows_q.next_upcoming(pool, datetime.now(UTC))
    if upcoming is None:
        return {"state": "closed"}
    if upcoming["state"] == "off":
        return {"state": "off"}
    return {"state": "scheduled", "opens_at": upcoming["opens_at"]}
