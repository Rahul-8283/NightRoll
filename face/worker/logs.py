"""JSON logs to standard output, with the request ID nginx assigned (Phase 12, task 6.1).

The backend sends the ID in `X-Request-ID`, so one ID follows a request from nginx through the API to this
worker. A request ID is kept only when it is plain and short. Request bodies, frames and embeddings are never
logged, and the path is logged as its route (`/students/{student_id}/embedding`), never with the student's ID.
"""

from __future__ import annotations

import json
import logging
import re
import sys
import time
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

REQUEST_ID_HEADER = b"x-request-id"
_SANE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
request_logger = logging.getLogger("worker.request")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = request_id_var.get()
        if request_id:
            payload["request_id"] = request_id
        payload.update(getattr(record, "fields", {}))
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())


class RequestContextMiddleware:
    """Reads or makes the request ID, puts it in every log line of the request, and logs one line per request."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = dict(scope["headers"]).get(REQUEST_ID_HEADER, b"").decode("latin-1")
        request_id = incoming if _SANE_REQUEST_ID.match(incoming) else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        status = 500
        started = time.perf_counter()

        async def send_with_id(message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message.setdefault("headers", []).append((REQUEST_ID_HEADER, request_id.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            path = getattr(scope.get("route"), "path", None) or "unmatched"
            # Docker polls /health every few seconds; a healthy answer is not worth a line.
            if not (path == "/health" and status == 200):
                request_logger.info(
                    "request",
                    extra={
                        "fields": {
                            "method": scope["method"],
                            "path": path,
                            "status": status,
                            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                        }
                    },
                )
            request_id_var.reset(token)
