"""Phase 12 operational state in Redis: the scheduler heartbeat and job records. Run from the backend folder:
uv run pytest ../tests/test_phase12_ops.py -v
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from app.config import get_settings  # noqa: E402
from app.redis import client as redis_client  # noqa: E402
from app.redis import keys  # noqa: E402
from app.services import ops  # noqa: E402


@pytest_asyncio.fixture
async def redis():
    await redis_client.connect(get_settings())
    yield redis_client.get_client()
    await redis_client.disconnect()


@pytest.mark.asyncio
async def test_a_fresh_heartbeat_is_ok_and_one_older_than_a_minute_is_stale(redis):
    key = f"test:heartbeat:{uuid4().hex}"
    assert await ops.scheduler_heartbeat_age(redis, key) is None
    assert not ops.heartbeat_is_fresh(None)

    await redis.set(key, datetime.now(UTC).isoformat(), ex=60)
    age = await ops.scheduler_heartbeat_age(redis, key)
    assert age is not None and age < 5
    assert ops.heartbeat_is_fresh(age)

    await redis.set(key, (datetime.now(UTC) - timedelta(seconds=90)).isoformat(), ex=60)
    age = await ops.scheduler_heartbeat_age(redis, key)
    assert 85 < age < 100
    assert not ops.heartbeat_is_fresh(age)
    await redis.delete(key)


@pytest.mark.asyncio
async def test_the_heartbeat_outlives_the_stale_limit_so_the_last_sighting_can_be_shown(redis, monkeypatch):
    key = f"test:heartbeat:{uuid4().hex}"
    monkeypatch.setattr(keys, "SCHEDULER_HEARTBEAT", key)
    await ops.write_heartbeat(redis, datetime.now(UTC))
    assert await redis.ttl(key) > ops.HEARTBEAT_STALE_SECONDS * 10
    await redis.delete(key)


@pytest.mark.asyncio
async def test_a_job_record_keeps_when_it_ran_and_what_it_did(redis):
    job = f"test-{uuid4().hex}"
    assert await ops.last_job(redis, job) is None
    await ops.record_job(redis, job, removed=3)
    record = await ops.last_job(redis, job)
    assert record["removed"] == 3
    assert datetime.fromisoformat(record["at"]) <= datetime.now(UTC)
    await redis.delete(keys.job_record_key(job))
