"""Phase 12 request IDs: the proxy's ID is kept, logged, returned and passed to the face worker.
No database needed. Run from the backend folder:
    uv run pytest ../tests/test_phase12_request_id.py -v
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from app.config import get_settings  # noqa: E402
from app.logging import JsonFormatter, request_headers, request_id_var  # noqa: E402
from app.main import app  # noqa: E402
from app.services.verification import face  # noqa: E402


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_a_proxy_request_id_is_returned_and_appears_in_the_error_body():
    async with _client() as c:
        response = await c.get("/v1/does-not-exist", headers={"X-Request-ID": "from-nginx-0123456789"})
    assert response.headers["x-request-id"] == "from-nginx-0123456789"
    assert response.json()["error"]["request_id"] == "from-nginx-0123456789"


@pytest.mark.asyncio
@pytest.mark.parametrize("odd", ["has spaces in it", "x" * 100, "tiny", "<script>alert(1)</script>"])
async def test_an_odd_request_id_is_replaced(odd):
    async with _client() as c:
        response = await c.get("/v1/does-not-exist", headers={"X-Request-ID": odd})
    assert response.headers["x-request-id"] != odd
    assert len(response.headers["x-request-id"]) == 32


def test_request_headers_are_empty_outside_a_request_and_carry_the_id_inside_one():
    assert request_headers() == {}
    token = request_id_var.set("abc123def456")
    try:
        assert request_headers() == {"X-Request-ID": "abc123def456"}
    finally:
        request_id_var.reset(token)


def test_every_log_line_carries_the_request_id_and_a_timestamp():
    record = logging.LogRecord("nightroll.test", logging.INFO, __file__, 1, "hello", None, None)
    token = request_id_var.set("abc123def456")
    try:
        line = json.loads(JsonFormatter().format(record))
    finally:
        request_id_var.reset(token)
    assert line["request_id"] == "abc123def456"
    assert line["ts"].endswith("+00:00")


@pytest.mark.asyncio
async def test_the_face_worker_call_carries_the_request_id():
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.headers)
        return httpx.Response(404)

    face.TRANSPORT = httpx.MockTransport(handler)
    token = request_id_var.set("abc123def456")
    try:
        result = await face.verify_frames(
            get_settings(),
            student_id=uuid4(),
            window_id=uuid4(),
            mark_id=uuid4(),
            frames=[b"x"],
            hashes=["0" * 64],
            tags=["neutral"],
        )
    finally:
        request_id_var.reset(token)
        face.TRANSPORT = None
    assert result is None
    assert seen["x-request-id"] == "abc123def456"
    assert seen["authorization"].startswith("Bearer ")
