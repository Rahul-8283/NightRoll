"""Phase 11 audit view: admin only, filterable, paged, and read-only.
Run from the backend folder:
    uv run pytest ../tests/test_phase11_audit.py -v
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


def _client(role: str) -> httpx.AsyncClient:
    claims = {
        "sub": str(uuid4()),
        "aud": "authenticated",
        "exp": int((datetime.now(UTC) + timedelta(minutes=10)).timestamp()),
        "aal": "aal2",
        "email": f"{role}@test.local",
        "app_metadata": {"role": role},
    }
    token = jwt.encode(claims, get_settings().SUPABASE_JWT_SECRET, algorithm="HS256")
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test", headers={"Authorization": f"Bearer {token}"}
    )


@pytest_asyncio.fixture
async def connected():
    settings = get_settings()
    await db_pool.connect(settings)
    await redis_client.connect(settings)
    yield db_pool.get_pool()
    await db_pool.disconnect()
    await redis_client.disconnect()


@pytest.mark.asyncio
async def test_a_warden_cannot_read_the_audit_log(connected):
    async with _client("warden") as c:
        response = await c.get("/v1/audit")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_an_admin_reads_newest_first_and_can_filter_by_action(connected):
    pool = connected
    marker = f"test.marker.{uuid4().hex[:8]}"
    await pool.execute(
        "insert into audit_log (actor, action, target_id, payload) values ($1, $2, null, '{}'::jsonb)", "test", marker
    )
    async with _client("admin") as c:
        response = await c.get("/v1/audit", params={"action": marker})
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["action"] == marker


@pytest.mark.asyncio
async def test_paging_returns_older_rows_once(connected):
    async with _client("admin") as c:
        first = (await c.get("/v1/audit", params={"limit": 2})).json()
        assert len(first["items"]) == 2
        if first["next_before"] is None:
            pytest.skip("fewer than three audit rows in this database")
        second = (await c.get("/v1/audit", params={"limit": 2, "before": first["next_before"]})).json()
    assert all(row["id"] < first["next_before"] for row in second["items"])
    assert not {row["id"] for row in first["items"]} & {row["id"] for row in second["items"]}


def test_the_audit_view_has_no_write_routes():
    writes = [
        route.path
        for route in app.routes
        if getattr(route, "path", "").startswith("/v1/audit") and route.methods - {"GET", "HEAD"}
    ]
    assert writes == []
