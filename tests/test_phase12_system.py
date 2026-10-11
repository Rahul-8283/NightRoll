"""Phase 12 System page and alerts. Run from the backend folder:
uv run pytest ../tests/test_phase12_system.py -v
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

from phase11_support import purge_test_windows  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import pool as db_pool  # noqa: E402
from app.main import app  # noqa: E402
from app.redis import client as redis_client  # noqa: E402
from app.services import system as system_service  # noqa: E402
from app.services.system import FaceHealth, build_alerts  # noqa: E402

UP = FaceHealth(reachable=True, ready=True, antispoof_available=True)
FRESH = 5.0


def _codes(**overrides) -> list[str]:
    arguments = {"window_open": True, "face": UP, "heartbeat_age": FRESH, "attempts_5m": 0, "rejected_5m": 0}
    arguments.update(overrides)
    return [alert.code for alert in build_alerts(**arguments)]


def test_a_healthy_system_raises_nothing():
    assert _codes() == []


def test_the_face_worker_being_down_matters_only_while_attendance_is_open():
    down = FaceHealth(reachable=False)
    assert _codes(face=down) == ["FACE_WORKER_DOWN"]
    assert _codes(face=down, window_open=False) == []


def test_a_face_worker_that_answers_but_has_no_model_counts_as_down_during_a_window():
    assert _codes(face=FaceHealth(reachable=True, ready=False)) == ["FACE_WORKER_DOWN"]


def test_a_stale_or_missing_scheduler_heartbeat_raises_an_alert():
    assert _codes(heartbeat_age=61) == ["SCHEDULER_STALE"]
    assert _codes(heartbeat_age=None) == ["SCHEDULER_STALE"]
    assert _codes(heartbeat_age=60) == []


def test_a_rejection_rate_over_twenty_percent_raises_a_warning_once_there_are_enough_attempts():
    assert _codes(attempts_5m=10, rejected_5m=3) == ["HIGH_REJECTION_RATE"]
    assert _codes(attempts_5m=10, rejected_5m=2) == []
    assert _codes(attempts_5m=4, rejected_5m=4) == []


def test_alerts_carry_a_severity_and_a_plain_message():
    alerts = build_alerts(
        window_open=True,
        face=FaceHealth(reachable=False),
        heartbeat_age=None,
        attempts_5m=10,
        rejected_5m=5,
    )
    assert {alert.severity for alert in alerts} == {"critical", "warning"}
    assert all(len(alert.message) > 20 for alert in alerts)


def _token(role: str) -> str:
    claims = {
        "sub": str(uuid4()),
        "aud": "authenticated",
        "exp": int((datetime.now(UTC) + timedelta(minutes=10)).timestamp()),
        "aal": "aal2",
        "email": f"{role}@test.local",
        "app_metadata": {"role": role},
    }
    return jwt.encode(claims, get_settings().SUPABASE_JWT_SECRET, algorithm="HS256")


def _client(role: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {_token(role)}"},
    )


@pytest_asyncio.fixture
async def world():
    settings = get_settings()
    await db_pool.connect(settings)
    await redis_client.connect(settings)
    pool = db_pool.get_pool()
    await purge_test_windows(pool)
    system_service._face_cache = None
    yield pool
    system_service._face_cache = None
    await purge_test_windows(pool)
    await db_pool.disconnect()
    await redis_client.disconnect()


async def _open_window(pool) -> None:
    now = datetime.now(UTC)
    await pool.execute(
        "insert into attendance_windows (night, opens_at, closes_at, state) values ($1, $2, $3, 'open')",
        date(2090, 1, 1) + timedelta(days=uuid4().int % 3000),
        now - timedelta(minutes=5),
        now + timedelta(hours=1),
    )


@pytest.mark.asyncio
async def test_any_warden_can_read_alerts_but_only_an_admin_can_read_the_system_page(world):
    async with _client("warden") as c:
        assert (await c.get("/v1/alerts")).status_code == 200
        assert (await c.get("/v1/system")).status_code == 403
    async with _client("admin") as c:
        assert (await c.get("/v1/system")).status_code == 200


@pytest.mark.asyncio
async def test_the_system_page_reports_health_counts_latency_jobs_and_alerts(world):
    async with _client("admin") as c:
        body = (await c.get("/v1/system")).json()
    assert body["database"]["status"] == "ok"
    assert body["redis"]["status"] == "ok"
    assert set(body["tonight"]["verdicts"]) == {"PRESENT", "NEEDS_REVIEW", "REJECTED"}
    assert {job["name"] for job in body["jobs"]} == {"Frame cleanup", "Enrollment code cleanup", "Room health"}
    assert set(body["latency"]) == {"requests_p50_ms", "requests_p95_ms", "verify_p95_ms", "face_worker_p95_ms"}
    assert body["scheduler"]["status"] in {"ok", "degraded", "down"}
    assert isinstance(body["alerts"], list)
    assert "face_worker" in body and "websocket_connections" in body


@pytest.mark.asyncio
async def test_stopping_the_face_worker_during_an_open_window_raises_the_alert(world, monkeypatch):
    await _open_window(world)

    async def worker_down(settings):
        return FaceHealth(reachable=False)

    monkeypatch.setattr(system_service, "face_health", worker_down)
    async with _client("warden") as c:
        codes = [alert["code"] for alert in (await c.get("/v1/alerts")).json()["alerts"]]
    assert "FACE_WORKER_DOWN" in codes

    async with _client("admin") as c:
        system = (await c.get("/v1/system")).json()
    assert system["face_worker"]["status"] == "down"
    assert "FACE_WORKER_DOWN" in [alert["code"] for alert in system["alerts"]]


@pytest.mark.asyncio
async def test_the_face_worker_answer_is_kept_for_a_few_seconds(world, monkeypatch):
    calls = []

    class Counting(httpx.AsyncClient):
        async def get(self, *args, **kwargs):
            calls.append(args)
            return httpx.Response(200, json={"ready": True, "antispoof_available": True, "model_version": "x"})

    monkeypatch.setattr(system_service.httpx, "AsyncClient", Counting)
    settings = get_settings()
    first = await system_service.face_health(settings)
    second = await system_service.face_health(settings)
    assert first is second and first.ready
    assert len(calls) == 1
