"""Viewing the captured frames for a disputed mark.

The backend never downloads or stores frames. It writes the audit row first, then asks the face worker for
short-lived links and passes them on.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
import httpx

from app.auth.supabase import Warden
from app.config import Settings
from app.db.queries import reviews as review_q
from app.errors import AppError
from app.logging import request_headers
from app.services import audit
from app.services.review import actor_of

# Test seam: tests replace this with an httpx.MockTransport. Never set in production code.
TRANSPORT: httpx.AsyncBaseTransport | None = None


async def view_frames(
    pool: asyncpg.Pool,
    settings: Settings,
    mark_id: UUID,
    reason: str,
    warden: Warden,
) -> dict:
    mark = await review_q.get_mark(pool, mark_id)
    if mark is None:
        raise AppError(code="NOT_FOUND", status_code=404, message="Mark not found")
    if mark["frames_path"] is None:
        raise AppError(code="FRAMES_REMOVED", status_code=410, message="Frames are removed after 24 hours")

    actor = actor_of(warden)
    async with pool.acquire() as conn:
        async with conn.transaction():
            await audit.write(
                conn,
                actor=actor,
                action="frames.viewed",
                target_id=str(mark_id),
                payload={"reason": reason, "student_id": str(mark["student_id"])},
            )

    folder = mark["frames_path"].rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=settings.FACE_WORKER_TIMEOUT_SECONDS, transport=TRANSPORT) as client:
            response = await client.post(
                f"{settings.FACE_WORKER_URL.rstrip('/')}/frames/links",
                headers={"Authorization": f"Bearer {settings.FACE_WORKER_TOKEN}", **request_headers()},
                json={"folder": folder},
            )
    except httpx.HTTPError as exc:
        raise AppError(
            code="FACE_WORKER_UNAVAILABLE", status_code=503, message="The face worker is unreachable"
        ) from exc
    if response.status_code == 404:
        raise AppError(code="FRAMES_REMOVED", status_code=410, message="Frames are removed after 24 hours")
    if response.status_code != 200:
        raise AppError(code="FACE_WORKER_ERROR", status_code=503, message="The face worker could not return the frames")

    body = response.json()
    return {"mark_id": mark_id, "expires_in_seconds": body["expires_in_seconds"], "links": body["links"]}
