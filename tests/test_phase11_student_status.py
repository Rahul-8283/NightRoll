"""Phase 11 section 8: a warden's decision reaches the student's status, and a declined student gets no new nonce.
Run from the backend folder:
    uv run pytest ../tests/test_phase11_student_status.py -v
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

from app.config import get_settings  # noqa: E402
from app.db import pool as db_pool  # noqa: E402
from app.db.queries import windows as windows_q  # noqa: E402
from app.main import app  # noqa: E402
from app.redis import client as redis_client  # noqa: E402
from app.services import attendance as attendance_svc  # noqa: E402


def _warden() -> httpx.AsyncClient:
    claims = {
        "sub": str(uuid4()),
        "aud": "authenticated",
        "exp": int((datetime.now(UTC) + timedelta(minutes=10)).timestamp()),
        "aal": "aal2",
        "email": "warden@test.local",
        "app_metadata": {"role": "warden"},
    }
    token = jwt.encode(claims, get_settings().SUPABASE_JWT_SECRET, algorithm="HS256")
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test", headers={"Authorization": f"Bearer {token}"}
    )


@pytest_asyncio.fixture
async def world():
    settings = get_settings()
    await db_pool.connect(settings)
    await redis_client.connect(settings)
    pool = db_pool.get_pool()
    student = await pool.fetchrow(
        "select id from students where active and enrolled_at is not null order by roll_number limit 1"
    )
    now = datetime.now(UTC)
    window_id = await pool.fetchval(
        "insert into attendance_windows (night, opens_at, closes_at, state) values ($1, $2, $3, 'open') returning id",
        date(2093, 1, 1) + timedelta(days=uuid4().int % 3000),
        now - timedelta(minutes=5),
        now + timedelta(hours=1),
    )
    yield {"pool": pool, "redis": redis_client.get_client(), "student": student, "window_id": window_id}
    await pool.execute(
        "delete from reviews where mark_id in (select id from attendance_marks where window_id = $1)", window_id
    )
    await pool.execute("delete from attendance_marks where window_id = $1", window_id)
    await pool.execute("delete from attendance_windows where id = $1", window_id)
    await db_pool.disconnect()
    await redis_client.disconnect()


async def _review_mark(pool, window_id, student_id) -> str:
    return str(
        await pool.fetchval(
            """
            insert into attendance_marks (window_id, student_id, verdict, reasons, attempt)
            values ($1, $2, 'NEEDS_REVIEW', '{}', 1) returning id
            """,
            window_id,
            student_id,
        )
    )


@pytest.mark.asyncio
async def test_a_declined_student_is_told_and_gets_no_new_nonce(world):
    open_now = await windows_q.open_window(world["pool"])
    if open_now is None or open_now["id"] != world["window_id"]:
        pytest.skip("another window is open in this database; this check needs ours to be the open one")
    mark = await _review_mark(world["pool"], world["window_id"], world["student"]["id"])
    async with _warden() as c:
        await c.post(
            f"/v1/attendance/marks/{mark}/review",
            json={"decision": "DECLINED", "note": "Face did not match on any frame"},
        )
    status = await attendance_svc.student_status(world["pool"], world["redis"], world["student"]["id"])
    assert status["state"] == "absent"
    assert status["decided_how"] == "declined"
    assert "nonce" not in status


@pytest.mark.asyncio
async def test_an_approved_student_is_told_it_was_approved(world):
    open_now = await windows_q.open_window(world["pool"])
    if open_now is None or open_now["id"] != world["window_id"]:
        pytest.skip("another window is open in this database; this check needs ours to be the open one")
    mark = await _review_mark(world["pool"], world["window_id"], world["student"]["id"])
    async with _warden() as c:
        await c.post(f"/v1/attendance/marks/{mark}/review", json={"decision": "APPROVED"})
    status = await attendance_svc.student_status(world["pool"], world["redis"], world["student"]["id"])
    assert status["state"] == "marked"
    assert status["decided_how"] == "approved"
