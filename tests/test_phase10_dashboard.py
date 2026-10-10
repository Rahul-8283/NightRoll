"""Phase 10 backend checks: the dashboard reads and their sign-in rules, run against the real database and Redis.
Run from the backend folder:
    uv run pytest ../tests/test_phase10_dashboard.py -v
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
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
from app.main import app  # noqa: E402
from app.redis import client as redis_client  # noqa: E402


def _token(role: str = "warden", aal: str = "aal2") -> str:
    now = datetime.now(UTC)
    claims = {
        "sub": str(uuid4()),
        "aud": "authenticated",
        "exp": int((now + timedelta(minutes=10)).timestamp()),
        "aal": aal,
        "app_metadata": {"role": role},
    }
    return jwt.encode(claims, get_settings().SUPABASE_JWT_SECRET, algorithm="HS256")


def _client(token: str | None = None) -> httpx.AsyncClient:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers=headers)


@pytest_asyncio.fixture
async def connected():
    settings = get_settings()
    await db_pool.connect(settings)
    await redis_client.connect(settings)
    yield
    await db_pool.disconnect()
    await redis_client.disconnect()


@pytest.mark.asyncio
async def test_tonight_requires_a_token(connected):
    async with _client() as c:
        response = await c.get("/v1/attendance/tonight")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_tonight_refuses_a_role_that_is_not_warden(connected):
    async with _client(_token(role="student")) as c:
        response = await c.get("/v1/attendance/tonight")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_tonight_refuses_a_session_without_the_authenticator_code(connected):
    async with _client(_token(aal="aal1")) as c:
        response = await c.get("/v1/attendance/tonight")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_tonight_returns_totals_rooms_and_recent_for_a_warden(connected):
    async with _client(_token()) as c:
        response = await c.get("/v1/attendance/tonight")
    assert response.status_code == 200
    body = response.json()
    assert set(body) >= {"window", "totals", "rooms", "recent"}
    assert set(body["totals"]) == {"enrolled", "present", "pending_review", "not_marked", "rejected"}
    assert body["totals"]["not_marked"] >= 0
    for room in body["rooms"]:
        assert set(room) >= {"room_id", "number", "floor", "present", "total", "pending_review", "rejected"}


@pytest.mark.asyncio
async def test_room_tonight_carries_enrollment_fields_for_each_student(connected):
    async with _client(_token()) as c:
        rooms = (await c.get("/v1/rooms")).json()
        assert rooms, "seed the rooms before running this test"
        response = await c.get(f"/v1/rooms/{rooms[0]['id']}/tonight")
    assert response.status_code == 200
    for student in response.json()["students"]:
        assert isinstance(student["face_enrolled"], bool)
        assert isinstance(student["device_enrolled"], bool)
        assert "device_security_level" in student


@pytest.mark.asyncio
async def test_unknown_room_is_not_found(connected):
    async with _client(_token()) as c:
        response = await c.get(f"/v1/rooms/{uuid4()}/tonight")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_window_history_lists_past_nights(connected):
    async with _client(_token()) as c:
        response = await c.get("/v1/windows/history")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
