"""Authentication dependency for internal Face Worker endpoints."""

from __future__ import annotations

import secrets
from fastapi import Header, HTTPException, status
from worker.config import settings


async def verify_service_token(authorization: str | None = Header(default=None)) -> None:
    """Validate Bearer token against configured FACE_WORKER_TOKEN."""
    expected_token = settings.FACE_WORKER_TOKEN

    # If configured with a token, enforce it strictly
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.removeprefix("Bearer ").strip()

    if not expected_token or not secrets.compare_digest(token, expected_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid face worker service token",
            headers={"WWW-Authenticate": "Bearer"},
        )
