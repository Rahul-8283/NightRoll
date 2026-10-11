"""Phase 12 housekeeping jobs, run against the real database and Redis. Run from the backend folder:
uv run pytest ../tests/test_phase12_housekeeping.py -v
"""

from __future__ import annotations

import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from phase11_support import enrol_for_test, purge_test_windows, restore_enrolment  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import pool as db_pool  # noqa: E402
from app.redis import client as redis_client  # noqa: E402
from app.services import housekeeping, ops  # noqa: E402
from app.services import windows as windows_service  # noqa: E402


@pytest_asyncio.fixture
async def world():
    settings = get_settings()
    await db_pool.connect(settings)
    await redis_client.connect(settings)
    pool = db_pool.get_pool()
    student = await enrol_for_test(pool)
    yield {"pool": pool, "redis": redis_client.get_client(), "student": student}
    await purge_test_windows(pool)
    await restore_enrolment(pool, student)
    await db_pool.disconnect()
    await redis_client.disconnect()


async def _code(pool, student_id, *, used_ago=None, expires_in):
    code_hash = f"test-{uuid4().hex}"
    now = datetime.now(UTC)
    await pool.execute(
        "insert into enrollment_codes (code_hash, student_id, expires_at, used_at) values ($1, $2, $3, $4)",
        code_hash,
        student_id,
        now + expires_in,
        None if used_ago is None else now - used_ago,
    )
    return code_hash


@pytest.mark.asyncio
async def test_codes_spent_more_than_a_day_ago_are_removed_and_recent_or_live_ones_stay(world):
    pool, student_id = world["pool"], world["student"]["id"]
    old_used = await _code(pool, student_id, used_ago=timedelta(days=2), expires_in=timedelta(days=-2))
    old_expired = await _code(pool, student_id, expires_in=timedelta(days=-3))
    recent_used = await _code(pool, student_id, used_ago=timedelta(minutes=5), expires_in=timedelta(minutes=10))
    recent_expired = await _code(pool, student_id, expires_in=timedelta(hours=-2))
    live = await _code(pool, student_id, expires_in=timedelta(minutes=10))

    removed = await housekeeping.clear_spent_enrollment_codes(pool, world["redis"])

    rows = await pool.fetch("select code_hash from enrollment_codes where code_hash like 'test-%'")
    left = {r["code_hash"] for r in rows}
        r["code_hash"] for r in await pool.fetch("select code_hash from enrollment_codes where code_hash like 'test-%'")
    }
    assert removed >= 2
    assert left == {recent_used, recent_expired, live}
    assert old_used not in left and old_expired not in left
    await pool.execute("delete from enrollment_codes where code_hash like 'test-%'")

    record = await ops.last_job(world["redis"], housekeeping.CODE_CLEANUP_JOB)
    assert record["removed"] == removed


async def _window(pool, state):
    now = datetime.now(UTC)
    return await pool.fetchval(
        "insert into attendance_windows (night, opens_at, closes_at, state) values ($1, $2, $3, $4) returning id",
        date(2095, 1, 1) + timedelta(days=uuid4().int % 3000),
        now - timedelta(hours=1),
        now - timedelta(minutes=1),
        state,
    )


@pytest.mark.asyncio
async def test_room_health_is_recorded_for_a_window(world):
    window_id = await _window(world["pool"], "closed")
    flags = await housekeeping.snapshot_room_health(world["pool"], world["redis"], window_id)
    record = await ops.last_job(world["redis"], housekeeping.ROOM_HEALTH_JOB)
    assert record["window_id"] == str(window_id)
    assert record["flagged"] == flags


@pytest.mark.asyncio
async def test_closing_a_window_records_room_health(world):
    window_id = await _window(world["pool"], "open")
    assert await windows_service.close_window(world["pool"], world["redis"], window_id, "test")
    record = await ops.last_job(world["redis"], housekeeping.ROOM_HEALTH_JOB)
    assert record["window_id"] == str(window_id)


@pytest.mark.asyncio
async def test_a_failing_health_record_does_not_stop_a_window_from_closing(world, monkeypatch):
    async def broken(*args, **kwargs):
        raise RuntimeError("redis hiccup")

    monkeypatch.setattr(housekeeping, "snapshot_room_health", broken)
    window_id = await _window(world["pool"], "open")
    assert await windows_service.close_window(world["pool"], world["redis"], window_id, "test")
    state = await world["pool"].fetchval("select state from attendance_windows where id = $1", window_id)
    assert state == "closed"
