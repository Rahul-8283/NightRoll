"""Student identity for attendance requests.

Stub until Phase 8 replaces it with device signature verification. It reads the same
`X-Student-Id` header the Phase 4 app always sends, but trusts it outright instead of
checking `X-Timestamp` and `X-Signature`, and only when APP_ENV is local.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request

from app.config import Settings, get_settings
from app.errors import AppError


def current_student_stub(request: Request, settings: Annotated[Settings, Depends(get_settings)]) -> UUID:
    if settings.APP_ENV != "local":
        raise AppError(code="NOT_FOUND", status_code=404, message="Not found")
    try:
        return UUID(request.headers.get("x-student-id", ""))
    except ValueError as exc:
        raise AppError(code="UNAUTHORIZED", status_code=401, message="Device signature required") from exc
