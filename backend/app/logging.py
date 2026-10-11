"""JSON logs, a request ID on every request, and redaction of sensitive fields.

Never log: authorization headers, signatures, integrity tokens, embeddings,
frames, or nonces. Student IDs are logged as a short hash, never raw.

The request ID comes from nginx (`X-Request-ID`) when it is a sane value, so one ID follows a request from
nginx through the API to the face worker. Every log line written while a request is handled carries it.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REDACT_KEYS = {"authorization", "signature", "integrity_token", "embedding", "frames", "nonce"}
REDACTED = "[redacted]"

request_logger = logging.getLogger("nightroll.request")

REQUEST_ID_HEADER = "X-Request-ID"
_SANE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def request_id_for(header_value: str | None) -> str:
    """Keep a proxy-supplied ID when it is plain and short, so a client cannot push odd text into the logs."""
    if header_value and _SANE_REQUEST_ID.match(header_value):
        return header_value
    return uuid.uuid4().hex


def current_request_id() -> str | None:
    return request_id_var.get()


def request_headers() -> dict[str, str]:
    """The header that carries this request's ID to another service, or nothing outside a request."""
    request_id = request_id_var.get()
    return {REQUEST_ID_HEADER: request_id} if request_id else {}


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: (REDACTED if k.lower() in REDACT_KEYS else redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def short_hash(value: str) -> str:
    """A short, non-reversible stand-in for a student ID in logs."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


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
        extra_fields = getattr(record, "extra_fields", None)
        if extra_fields:
            payload.update(redact(extra_fields))
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "info") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())


def log_event(logger: logging.Logger, level: int, message: str, **fields: Any) -> None:
    logger.log(level, message, extra={"extra_fields": fields})


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request_id_for(request.headers.get(REQUEST_ID_HEADER))
        request.state.request_id = request_id
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        try:
            response: Response = await call_next(request)
        finally:
            request_id_var.reset(token)
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers[REQUEST_ID_HEADER] = request_id
        log_event(
            request_logger,
            logging.INFO,
            "request",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            latency_ms=latency_ms,
        )
        return response
