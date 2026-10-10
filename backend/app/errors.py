"""One error shape for every response the API returns.

{
  "error": {
    "code": "VALIDATION_FAILED",
    "message": "Human-readable summary",
    "details": [{"field": "closes_at", "issue": "must be after opens_at"}],
    "request_id": "..."
  }
}
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

error_logger = logging.getLogger("nightroll.error")


class AppError(Exception):
    """Raise this for any expected failure. `code` is a stable, machine-readable name."""

    def __init__(self, code: str, status_code: int, message: str, details: list[dict] | None = None) -> None:
        self.code = code
        self.status_code = status_code
        self.message = message
        self.details = details or []
        super().__init__(message)


def _body(request: Request, code: str, message: str, details: list[dict]) -> dict:
    request_id = getattr(request.state, "request_id", None)
    return {"error": {"code": code, "message": message, "details": details, "request_id": request_id}}


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=_body(request, exc.code, exc.message, exc.details))


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        {"field": ".".join(str(part) for part in err["loc"][1:]) or str(err["loc"][-1]), "issue": err["msg"]}
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content=_body(request, "VALIDATION_FAILED", "Request failed validation", details),
    )


_HTTP_CODES = {401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND", 429: "RATE_LIMITED"}


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = _HTTP_CODES.get(exc.status_code, "HTTP_ERROR")
    return JSONResponse(status_code=exc.status_code, content=_body(request, code, str(exc.detail), []))


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Full detail goes to the log only; the response never leaks internals.
    error_logger.exception("unhandled exception", exc_info=exc)
    return JSONResponse(status_code=500, content=_body(request, "INTERNAL_ERROR", "Something went wrong", []))


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
