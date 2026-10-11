"""Phase 12 rate limits, run against the real Redis. Run from the backend folder:
uv run pytest ../tests/test_phase12_ratelimit.py -v
"""

from __future__ import annotations

import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import jwt
import pytest
import pytest_asyncio

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from app import ratelimit  # noqa: E402
from app.auth.device import current_device  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import pool as db_pool  # noqa: E402
from app.main import app  # noqa: E402
from app.redis import client as redis_client  # noqa: E402
from app.services import enrollment as enrollment_svc  # noqa: E402


def _token() -> str:
    now = datetime.now(UTC)
    claims = {
        "sub": str(uuid4()),
        "aud": "authenticated",
        "exp": int((now + timedelta(minutes=10)).timestamp()),
        "aal": "aal2",
        "email": "warden@test.local",
        "app_metadata": {"role": "warden"},
    }
    return jwt.encode(claims, get_settings().SUPABASE_JWT_SECRET, algorithm="HS256")


def _client(**headers) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers=headers)


@pytest_asyncio.fixture
async def redis():
    settings = get_settings()
    await db_pool.connect(settings)
    await redis_client.connect(settings)
    yield redis_client.get_client()
    await db_pool.disconnect()
    await redis_client.disconnect()


@pytest.mark.asyncio
async def test_enforce_allows_up_to_the_limit_then_refuses_with_retry_after(redis):
    subject = uuid4().hex
    for _ in range(3):
        await ratelimit.enforce(redis, "test", subject, 3, 60)
    with pytest.raises(ratelimit.AppError) as caught:
        await ratelimit.enforce(redis, "test", subject, 3, 60)
    assert caught.value.status_code == 429
    assert 1 <= int(caught.value.headers["Retry-After"]) <= 60
    await redis.delete(f"ratelimit:test:{subject}")


@pytest.mark.asyncio
async def test_the_window_expires_so_a_limited_subject_can_try_again(redis):
    subject = uuid4().hex
    await ratelimit.enforce(redis, "test", subject, 1, 1)
    with pytest.raises(ratelimit.AppError):
        await ratelimit.enforce(redis, "test", subject, 1, 1)
    time.sleep(1.2)
    await ratelimit.enforce(redis, "test", subject, 1, 1)
    await redis.delete(f"ratelimit:test:{subject}")


@pytest.mark.asyncio
async def test_a_warden_over_the_limit_gets_429_with_retry_after(redis, monkeypatch):
    monkeypatch.setattr(ratelimit, "WARDEN_PER_MINUTE", 3)
    async with _client(Authorization=f"Bearer {_token()}") as c:
        statuses = [(await c.get("/v1/rooms")).status_code for _ in range(3)]
        limited = await c.get("/v1/rooms")
    assert 429 not in statuses
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "RATE_LIMITED"
    assert int(limited.headers["retry-after"]) >= 1


@pytest.mark.asyncio
async def test_export_is_limited_per_warden(redis, monkeypatch):
    monkeypatch.setattr(ratelimit, "EXPORT_PER_HOUR", 2)
    today = datetime.now(UTC).date().isoformat()
    params = {"from": today, "to": today}
    async with _client(Authorization=f"Bearer {_token()}") as c:
        first = [(await c.get("/v1/exports/attendance", params=params)).status_code for _ in range(2)]
        limited = await c.get("/v1/exports/attendance", params=params)
    assert 429 not in first
    assert limited.status_code == 429
    assert int(limited.headers["retry-after"]) > 60


@pytest.mark.asyncio
async def test_nonce_requests_are_limited_per_student(redis, monkeypatch):
    student = uuid4()
    monkeypatch.setitem(app.dependency_overrides, current_device, lambda: student)
    async with _client() as c:
        statuses = [(await c.get("/v1/attendance/nonce")).status_code for _ in range(ratelimit.NONCE_PER_MINUTE)]
        limited = await c.get("/v1/attendance/nonce")
    await redis.delete(f"ratelimit:nonce:{student}")
    assert 429 not in statuses
    assert limited.status_code == 429
    assert int(limited.headers["retry-after"]) >= 1


@pytest.mark.asyncio
async def test_an_address_that_keeps_failing_signature_checks_is_slowed_down(redis, monkeypatch):
    monkeypatch.setattr(ratelimit, "SIGNATURE_FAILURES_PER_MINUTE", 3)
    address = f"203.0.113.{uuid4().int % 250 + 1}"
    headers = {
        "x-forwarded-for": address,
        "x-student-id": str(uuid4()),
        "x-timestamp": str(int(time.time())),
        "x-signature": "AAAA",
    }
    # The test client connects from 127.0.0.1, a trusted proxy in the local settings, so the header is believed.
    assert "127.0.0.1" in get_settings().TRUSTED_PROXY_IPS
    async with _client(**headers) as c:
        failures = [(await c.get("/v1/attendance/nonce")).status_code for _ in range(3)]
        limited = await c.get("/v1/attendance/nonce")
    await redis.delete(f"ratelimit:signature-failures:{address}")
    assert failures == [401, 401, 401]
    assert limited.status_code == 429
    assert int(limited.headers["retry-after"]) >= 1


@pytest.mark.asyncio
async def test_five_failed_enrollment_codes_lock_entry_for_fifteen_minutes(redis):
    student = uuid4()
    for _ in range(enrollment_svc.MAX_FAILED_ATTEMPTS):
        await enrollment_svc.record_failed_attempt(redis, student)
    assert await enrollment_svc.is_student_locked_out(redis, student)
    ttl = await redis.ttl(f"enrollment:locked:{student}")
    assert 0 < ttl <= enrollment_svc.LOCKOUT_WINDOW_SECONDS
    await enrollment_svc.clear_lockout(redis, student)
    error = enrollment_svc._locked(ttl)
    assert (error.status_code, error.code) == (429, "CODE_LOCKED")
    assert int(error.headers["Retry-After"]) == ttl
