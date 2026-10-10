"""The backend's call to the face worker's /verify (Phase 9 section 2).

The worker only answers numbers. A worker that cannot be reached is a 503, never a pass.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import UUID

import httpx

from app.config import Settings
from app.errors import AppError
from app.services.verification.scorers import FrameMeasure

# Test seam: tests replace this with an httpx.MockTransport. Never set in production code.
TRANSPORT: httpx.AsyncBaseTransport | None = None


class FaceUnavailable(AppError):
    def __init__(self, reason: str) -> None:
        super().__init__(
            code="FACE_UNAVAILABLE",
            status_code=503,
            message=f"The face check is not available right now ({reason}). Use the ground-floor scanner.",
        )


@dataclass(frozen=True)
class FaceVerification:
    frames: list[FrameMeasure]
    antispoof_available: bool
    frames_path: str | None


async def verify_frames(
    settings: Settings,
    *,
    student_id: UUID,
    window_id: UUID,
    mark_id: UUID,
    frames: list[bytes],
    hashes: list[str],
    tags: list[str],
) -> FaceVerification | None:
    """Return the worker's per-frame measures, or None if the student has no enrolled face."""
    files = [("frames", (f"{i}.jpg", raw, "image/jpeg")) for i, raw in enumerate(frames)]
    data = {
        "student_id": str(student_id),
        "window_id": str(window_id),
        "mark_id": str(mark_id),
        "frame_hashes": json.dumps(hashes),
    }
    try:
        async with httpx.AsyncClient(timeout=settings.FACE_WORKER_TIMEOUT_SECONDS, transport=TRANSPORT) as client:
            resp = await client.post(
                f"{settings.FACE_WORKER_URL.rstrip('/')}/verify",
                headers={"Authorization": f"Bearer {settings.FACE_WORKER_TOKEN}"},
                data=data,
                files=files,
            )
    except httpx.HTTPError as exc:
        raise FaceUnavailable("the face service did not answer") from exc

    if resp.status_code == 404:
        return None
    if resp.status_code != 200:
        raise FaceUnavailable(f"the face service returned HTTP {resp.status_code}")

    body = resp.json()
    measures = [
        FrameMeasure(
            index=item["index"],
            tag=tags[item["index"]],
            usable=item["usable"],
            similarity=item["similarity"],
            antispoof=item["antispoof"],
            yaw=item["yaw"],
        )
        for item in body["frame_results"]
    ]
    return FaceVerification(
        frames=measures,
        antispoof_available=bool(body["antispoof_available"]),
        frames_path=body.get("frames_path"),
    )
