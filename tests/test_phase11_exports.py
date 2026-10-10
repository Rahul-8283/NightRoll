"""Phase 11 export: the 31-day limit, the formula guard, the columns and the audit row.
Run from the backend folder:
    uv run pytest ../tests/test_phase11_exports.py -v
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
from app.services.exports import COLUMNS, safe_cell  # noqa: E402


def _client() -> httpx.AsyncClient:
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
async def connected():
    settings = get_settings()
    await db_pool.connect(settings)
    await redis_client.connect(settings)
    yield db_pool.get_pool()
    await db_pool.disconnect()
    await redis_client.disconnect()


@pytest.mark.parametrize("value", ['=HYPERLINK("http://x")', "+1+1", "-2+3", "@SUM(A1)", "\tcmd", "\rcmd"])
def test_cells_starting_with_formula_characters_are_neutralised(value):
    assert safe_cell(value) == "'" + value


def test_ordinary_cells_are_left_alone():
    assert safe_cell("Asha Verma") == "Asha Verma"
    assert safe_cell(None) == ""
    assert safe_cell(3) == "3"


@pytest.mark.asyncio
async def test_a_range_longer_than_31_days_is_refused(connected):
    async with _client() as c:
        response = await c.get("/v1/exports/attendance", params={"from": "2030-01-01", "to": "2030-02-15"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "RANGE_TOO_LONG"


@pytest.mark.asyncio
async def test_a_reversed_range_is_refused(connected):
    async with _client() as c:
        response = await c.get("/v1/exports/attendance", params={"from": "2030-02-02", "to": "2030-02-01"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_the_csv_has_the_agreed_columns_and_no_scores(connected):
    async with _client() as c:
        response = await c.get("/v1/exports/attendance", params={"from": "2030-01-01", "to": "2030-01-31"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    header = response.text.splitlines()[0].split(",")
    assert header == COLUMNS
    for forbidden in ("score", "reason", "scorer", "bssid", "subnet", "embedding"):
        assert not any(forbidden in column for column in header)


@pytest.mark.asyncio
async def test_every_export_is_audited_with_its_filters(connected):
    pool = connected
    async with _client() as c:
        await c.get("/v1/exports/attendance", params={"from": "2030-03-01", "to": "2030-03-07", "floor": 1})
    row = await pool.fetchrow("select payload from audit_log where action = 'export.created' order by id desc limit 1")
    assert row is not None
    assert row["payload"]["from"] == "2030-03-01"
    assert row["payload"]["floor"] == 1
