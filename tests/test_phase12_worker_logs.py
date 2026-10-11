"""Phase 12 face worker logging: one JSON line per request, carrying the request ID, without student IDs.
No models or database needed. Run from the backend folder:
    uv run pytest ../tests/test_phase12_worker_logs.py -v
"""

from __future__ import annotations

import io
import json
import logging
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

FACE = Path(__file__).resolve().parent.parent / "face"
sys.path.insert(0, str(FACE))

from worker.logs import JsonFormatter, RequestContextMiddleware, request_logger  # noqa: E402


@pytest.fixture
def client():
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    inner = logging.getLogger("worker.test")

    @app.get("/health")
    def health():
        return {"ready": True}

    @app.delete("/students/{student_id}/embedding")
    def delete(student_id: str):
        inner.info("deleting")
        return {"deleted": True}

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger("worker")
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    request_logger.propagate = True
    yield TestClient(app), stream
    root.removeHandler(handler)


def _lines(stream: io.StringIO) -> list[dict]:
    return [json.loads(line) for line in stream.getvalue().splitlines() if line]


def test_the_proxy_request_id_is_kept_echoed_and_on_every_line(client):
    http, stream = client
    student = uuid4()
    response = http.delete(f"/students/{student}/embedding", headers={"X-Request-ID": "abc123def456"})
    assert response.headers["x-request-id"] == "abc123def456"
    lines = _lines(stream)
    assert [line["message"] for line in lines] == ["deleting", "request"]
    assert {line["request_id"] for line in lines} == {"abc123def456"}


def test_the_path_is_logged_as_its_route_never_with_the_student_id(client):
    http, stream = client
    student = uuid4()
    http.delete(f"/students/{student}/embedding")
    request_line = _lines(stream)[-1]
    assert request_line["path"] == "/students/{student_id}/embedding"
    assert str(student) not in stream.getvalue()
    assert request_line["status"] == 200
    assert request_line["latency_ms"] >= 0


@pytest.mark.parametrize("odd", ["has spaces in it", "x" * 200, "short", "line\tbreak"])
def test_an_odd_request_id_is_replaced_by_a_fresh_one(client, odd):
    http, _ = client
    response = http.get("/health", headers={"X-Request-ID": odd})
    assert response.headers["x-request-id"] != odd
    assert len(response.headers["x-request-id"]) == 32


def test_a_healthy_health_check_is_not_logged(client):
    http, stream = client
    http.get("/health")
    assert _lines(stream) == []
