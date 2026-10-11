"""Phase 12 metrics: the Prometheus text, who may read it, and what it never contains. Run from the backend folder:
uv run pytest ../tests/test_phase12_metrics.py -v
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

from app import metrics  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import pool as db_pool  # noqa: E402
from app.main import app  # noqa: E402
from app.redis import client as redis_client  # noqa: E402


def test_a_counter_renders_with_help_type_and_labels():
    counter = metrics.Counter("demo_total", "A demo.", ("kind",))
    counter.inc("a")
    counter.inc("a")
    counter.inc("b", amount=3)
    assert list(counter.samples()) == ['demo_total{kind="a"} 2', 'demo_total{kind="b"} 3']


def test_label_values_are_escaped():
    counter = metrics.Counter("demo_total", "A demo.", ("kind",))
    counter.inc('say "hi"\nnow')
    assert list(counter.samples()) == ['demo_total{kind="say \\"hi\\"\\nnow"} 1']


def test_a_histogram_renders_cumulative_buckets_sum_and_count():
    histogram = metrics.Histogram("lat_seconds", "Latency.", ("route",), buckets=(0.1, 1.0))
    for seconds in (0.05, 0.5, 2.0):
        histogram.observe(seconds, "/x")
    lines = list(histogram.samples())
    assert 'lat_seconds_bucket{route="/x",le="0.1"} 1' in lines
    assert 'lat_seconds_bucket{route="/x",le="1"} 2' in lines
    assert 'lat_seconds_bucket{route="/x",le="+Inf"} 3' in lines
    assert 'lat_seconds_count{route="/x"} 3' in lines
    assert any(line.startswith('lat_seconds_sum{route="/x"} 2.55') for line in lines)


def test_quantiles_are_estimated_from_the_buckets():
    histogram = metrics.Histogram("lat_seconds", "Latency.", buckets=(0.1, 0.2, 0.4))
    assert histogram.quantile(0.5) is None
    for _ in range(90):
        histogram.observe(0.05)
    for _ in range(10):
        histogram.observe(0.3)
    assert histogram.quantile(0.5) <= 0.1
    assert 0.2 < histogram.quantile(0.95) <= 0.4


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


def _client(peer: str, token: str | None = None) -> httpx.AsyncClient:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, client=(peer, 5000)), base_url="http://test", headers=headers
    )


@pytest_asyncio.fixture
async def connected():
    settings = get_settings()
    await db_pool.connect(settings)
    await redis_client.connect(settings)
    yield
    await db_pool.disconnect()
    await redis_client.disconnect()


@pytest.mark.asyncio
async def test_an_admin_can_read_metrics_and_they_include_the_route_template_not_the_path(connected):
    async with _client("8.8.8.8", _token("admin")) as c:
        await c.get(f"/v1/rooms/{uuid4()}")  # a path with an ID in it
        response = await c.get("/v1/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    body = response.text
    assert "# TYPE nightroll_http_requests_total counter" in body
    assert "nightroll_scheduler_heartbeat_age_seconds" in body
    assert 'route="/v1/rooms/{room_id}"' in body


@pytest.mark.asyncio
async def test_a_warden_and_an_anonymous_outsider_are_refused(connected):
    async with _client("8.8.8.8", _token("warden")) as c:
        assert (await c.get("/v1/metrics")).status_code == 403
    async with _client("8.8.8.8") as c:
        assert (await c.get("/v1/metrics")).status_code == 401


@pytest.mark.asyncio
async def test_a_caller_on_the_internal_network_needs_no_token_unless_it_is_the_proxy(connected):
    async with _client("10.1.2.3") as c:
        assert (await c.get("/v1/metrics")).status_code == 200
    # The reverse proxy is also a private address, but everyone on the internet arrives through it.
    proxy = get_settings().TRUSTED_PROXY_IPS.split(",")[0].strip()
    async with _client(proxy) as c:
        assert (await c.get("/v1/metrics")).status_code == 401
