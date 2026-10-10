"""Phase 11 frame viewing: the reason rule, the removed-frames case and the audit row.
The face worker is replaced by a mock at the HTTP layer. Run from the backend folder:
    uv run pytest ../tests/test_phase11_frames.py -v
"""

from __future__ import annotations

import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import jwt
import pytest
import pytest_asyncio

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from phase11_support import enrol_for_test, restore_enrolment  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import pool as db_pool  # noqa: E402
from app.main import app  # noqa: E402
from app.redis import client as redis_client  # noqa: E402
from app.services import frames as frames_svc  # noqa: E402


def _token() -> str:
    claims = {
        "sub": str(uuid4()),
        "aud": "authenticated",
        "exp": int((datetime.now(UTC) + timedelta(minutes=10)).timestamp()),
        "aal": "aal2",
        "email": "warden@test.local",
        "app_metadata": {"role": "warden"},
    }
    return jwt.encode(claims, get_settings().SUPABASE_JWT_SECRET, algorithm="HS256")


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {_token()}"},
    )


@pytest_asyncio.fixture
async def mark():
    settings = get_settings()
    await db_pool.connect(settings)
    await redis_client.connect(settings)
    pool = db_pool.get_pool()
    student = await enrol_for_test(pool)
    now = datetime.now(UTC)
    window_id = await pool.fetchval(
        "insert into attendance_windows (night, opens_at, closes_at, state) values ($1, $2, $3, 'open') returning id",
        date(2092, 1, 1) + timedelta(days=uuid4().int % 3000),
        now - timedelta(minutes=5),
        now + timedelta(hours=1),
    )
    mark_id = await pool.fetchval(
        """
        insert into attendance_marks (window_id, student_id, verdict, reasons, attempt, frames_path)
        values ($1, $2, 'NEEDS_REVIEW', '{}', 1, $3) returning id
        """,
        window_id,
        student["id"],
        f"frames/{window_id}/{uuid4()}/",
    )
    yield {"pool": pool, "mark_id": mark_id, "window_id": window_id}
    await pool.execute("delete from attendance_marks where window_id = $1", window_id)
    await pool.execute("delete from attendance_windows where id = $1", window_id)
    await restore_enrolment(pool, student)
    await db_pool.disconnect()
    await redis_client.disconnect()
    frames_svc.TRANSPORT = None


def _worker(status: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        if status != 200:
            return httpx.Response(status)
        return httpx.Response(
            200,
            json={
                "expires_in_seconds": 60,
                "links": [{"name": "0.jpg", "url": "https://signed.example/0.jpg?token=x"}],
            },
        )

    frames_svc.TRANSPORT = httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_viewing_frames_needs_a_written_reason(mark):
    _worker()
    async with _client() as c:
        response = await c.post(f"/v1/attendance/marks/{mark['mark_id']}/frames/view", json={"reason": "why"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_viewing_frames_returns_short_lived_links_and_audits_the_reason(mark):
    _worker()
    async with _client() as c:
        response = await c.post(
            f"/v1/attendance/marks/{mark['mark_id']}/frames/view",
            json={"reason": "Student says the photo was taken by a friend"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["expires_in_seconds"] == 60
    assert body["links"][0]["url"].startswith("https://signed.example/")
    rows = await mark["pool"].fetch("select action, payload from audit_log where target_id = $1", str(mark["mark_id"]))
    assert "frames.viewed" in [row["action"] for row in rows]


@pytest.mark.asyncio
async def test_removed_frames_are_reported_plainly(mark):
    await mark["pool"].execute("update attendance_marks set frames_path = null where id = $1", mark["mark_id"])
    _worker()
    async with _client() as c:
        response = await c.post(
            f"/v1/attendance/marks/{mark['mark_id']}/frames/view",
            json={"reason": "Student says the photo was taken by a friend"},
        )
    assert response.status_code == 410
    assert response.json()["error"]["message"] == "Frames are removed after 24 hours"


@pytest.mark.asyncio
async def test_face_worker_failure_is_a_clear_error(mark):
    _worker(status=500)
    async with _client() as c:
        response = await c.post(
            f"/v1/attendance/marks/{mark['mark_id']}/frames/view",
            json={"reason": "Student says the photo was taken by a friend"},
        )
    assert response.status_code == 503
