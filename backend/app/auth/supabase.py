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

from app import ratelimit
from app.config import Settings, get_settings
from app.errors import AppError
from app.redis import client as redis_client

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


def extract_token(request: Request) -> str:
    header = request.headers.get("authorization") or request.headers.get("Authorization")
    if not header or not header.lower().startswith("bearer "):
        raise _unauthorized("Missing or invalid Authorization header")
    return header.split(" ", 1)[1].strip()


_jwks_clients: dict[str, jwt.PyJWKClient] = {}


def _jwks_client(settings: Settings) -> jwt.PyJWKClient:
    """One cached client per project. The public keys are fetched once and reused, never on every request."""
    url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
    if url not in _jwks_clients:
        _jwks_clients[url] = jwt.PyJWKClient(url, cache_keys=True, lifespan=3600)
    return _jwks_clients[url]


def verify_token(token: str, settings: Settings) -> dict:
    """Check a Supabase access token. New projects sign with an asymmetric key (ES256/RS256), checked against
    the project's public keys. Older projects sign with the shared JWT secret (HS256)."""
    try:
        algorithm = jwt.get_unverified_header(token).get("alg")
        if algorithm == "HS256":
            key, algorithms = settings.SUPABASE_JWT_SECRET, ["HS256"]
        elif algorithm in ("ES256", "RS256"):
            key, algorithms = _jwks_client(settings).get_signing_key_from_jwt(token).key, [algorithm]
        else:
            raise _unauthorized("Invalid token")
        return jwt.decode(token, key, algorithms=algorithms, audience=AUDIENCE)
    except jwt.ExpiredSignatureError as exc:
        raise _unauthorized("Token has expired") from exc
    except (jwt.InvalidTokenError, jwt.PyJWKClientError) as exc:
        raise _unauthorized("Invalid token") from exc


def warden_from_claims(claims: dict, settings: Settings) -> Warden:
    role = (claims.get("app_metadata") or {}).get("role")
    if role not in ("warden", "admin"):
        raise _forbidden("FORBIDDEN", "This account has no warden or admin role")

    if settings.REQUIRE_MFA and claims.get("aal") != "aal2":
        raise _forbidden("MFA_REQUIRED", "Complete multi-factor authentication to continue")

    return Warden(user_id=claims["sub"], email=claims.get("email"), role=role)


def authenticate_token(token: str, settings: Settings) -> tuple[Warden, dict]:
    claims = verify_token(token, settings)
    return warden_from_claims(claims, settings), claims


async def current_warden(request: Request, settings: Annotated[Settings, Depends(get_settings)]) -> Warden:
    warden, _ = authenticate_token(extract_token(request), settings)
    await ratelimit.enforce(redis_client.get_client(), "warden", warden.user_id, ratelimit.WARDEN_PER_MINUTE, 60)
    return warden


async def require_admin(warden: Annotated[Warden, Depends(current_warden)]) -> Warden:
    if warden.role != "admin":
        raise _forbidden("FORBIDDEN", "This action requires an admin account")
    return warden
