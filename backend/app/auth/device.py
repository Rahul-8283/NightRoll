"""Student identity and device signature verification for student requests."""

from __future__ import annotations

import base64
import hashlib
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import load_der_public_key
from fastapi import Depends, Request

from app.config import Settings, get_settings
from app.db import pool as db_pool
from app.errors import AppError


async def current_student_device(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> UUID:
    raw_student_id = request.headers.get("x-student-id")
    if not raw_student_id:
        raise AppError(code="UNAUTHORIZED", status_code=401, message="Missing X-Student-Id header")

    try:
        student_id = UUID(raw_student_id)
    except ValueError as exc:
        raise AppError(code="UNAUTHORIZED", status_code=401, message="Invalid X-Student-Id") from exc

    sig_header = request.headers.get("x-signature")
    ts_header = request.headers.get("x-timestamp")

    if not sig_header or not ts_header:
        if settings.APP_ENV == "local":
            return student_id
        raise AppError(code="UNAUTHORIZED", status_code=401, message="Device signature required")

    # Check timestamp freshness (60 seconds)
    try:
        ts = int(ts_header)
        now_ts = int(datetime.now(UTC).timestamp())
        if abs(now_ts - ts) > 60:
            raise AppError(code="UNAUTHORIZED", status_code=401, message="Timestamp skew exceeded (max 60s)")
    except ValueError as exc:
        raise AppError(code="UNAUTHORIZED", status_code=401, message="Invalid X-Timestamp header") from exc

    # Fetch active device public key from database
    pool = db_pool.get_pool()
    row = await pool.fetchrow(
        "select public_key from devices where student_id = $1 and active = true order by enrolled_at desc limit 1",
        student_id,
    )
    if row is None:
        raise AppError(code="UNAUTHORIZED", status_code=401, message="No active device found for this student")

    body_bytes = await request.body()
    body_hash = hashlib.sha256(body_bytes).hexdigest()
    path_with_query = request.url.path
    if request.url.query:
        path_with_query = f"{path_with_query}?{request.url.query}"

    to_sign = f"{request.method.upper()}\n{path_with_query}\n{ts_header}\n{body_hash}"

    try:
        sig_bytes = base64.b64decode(sig_header)
        pub_key = load_der_public_key(row["public_key"])
        if not isinstance(pub_key, ec.EllipticCurvePublicKey):
            raise ValueError("Not an EC key")
        pub_key.verify(sig_bytes, to_sign.encode("utf-8"), ec.ECDSA(hashes.SHA256()))
    except Exception as exc:
        raise AppError(code="UNAUTHORIZED", status_code=401, message="Invalid device signature") from exc

    return student_id


# Maintain stub alias for backwards compatibility
current_student_stub = current_student_device
