"""Verify the warden's Supabase Auth access token and expose it as a dependency.

The dashboard logs in with Supabase Auth and sends the access token as
`Authorization: Bearer <token>`. Supabase signs it with the project's JWT
secret (HS256); this module verifies that signature, the expiry, and the
audience, then checks the role carried in `app_metadata.role`.

Student requests are not authenticated here. They are authenticated by
device signature, starting in Phase 8.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, Request

from app.config import Settings, get_settings
from app.errors import AppError

AUDIENCE = "authenticated"


@dataclass(frozen=True)
class Warden:
    user_id: str
    email: str | None
    role: str


def _unauthorized(message: str) -> AppError:
    return AppError(code="UNAUTHORIZED", status_code=401, message=message)


def _forbidden(code: str, message: str) -> AppError:
    return AppError(code=code, status_code=403, message=message)


def _extract_token(request: Request) -> str:
    header = request.headers.get("authorization") or request.headers.get("Authorization")
    if not header or not header.lower().startswith("bearer "):
        raise _unauthorized("Missing or invalid Authorization header")
    return header.split(" ", 1)[1].strip()


def verify_token(token: str, settings: Settings) -> dict:
    try:
        return jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience=AUDIENCE,
        )
    except jwt.ExpiredSignatureError as exc:
        raise _unauthorized("Token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise _unauthorized("Invalid token") from exc


async def current_warden(request: Request, settings: Annotated[Settings, Depends(get_settings)]) -> Warden:
    token = _extract_token(request)
    claims = verify_token(token, settings)

    role = (claims.get("app_metadata") or {}).get("role")
    if role not in ("warden", "admin"):
        raise _forbidden("FORBIDDEN", "This account has no warden or admin role")

    if settings.REQUIRE_MFA and claims.get("aal") != "aal2":
        raise _forbidden("MFA_REQUIRED", "Complete multi-factor authentication to continue")

    return Warden(user_id=claims["sub"], email=claims.get("email"), role=role)


async def require_admin(warden: Annotated[Warden, Depends(current_warden)]) -> Warden:
    if warden.role != "admin":
        raise _forbidden("FORBIDDEN", "This action requires an admin account")
    return warden
