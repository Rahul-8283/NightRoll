from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.db.queries import attendance as attendance_q
from app.db.queries import students as students_q
from app.db.queries import windows as windows_q
from app.errors import AppError
from app.services import nonces

CHALLENGE = ["blink", "turn_left"]


async def student_status(pool: asyncpg.Pool, redis: Redis, student_id: UUID) -> dict[str, Any]:
    if await students_q.get_active_enrolled(pool, student_id) is None:
        raise AppError(code="NOT_ENROLLED", status_code=403, message="This student is not enrolled")

    window = await windows_q.open_window(pool)
    if window is not None:
        window_id = window["id"]
        if await attendance_q.has_present_mark(pool, window_id, student_id):
            return {"state": "marked", "window_id": window_id}

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
            }
        return {"state": "pending", "window_id": window_id}

    upcoming = await windows_q.next_upcoming(pool, datetime.now(UTC))
    if upcoming is None:
        return {"state": "closed"}
    if upcoming["state"] == "off":
        return {"state": "off"}
    return {"state": "scheduled", "opens_at": upcoming["opens_at"]}
