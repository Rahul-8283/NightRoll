"""Device-signature authentication for student requests.

A student request carries X-Student-Id, X-Timestamp and X-Signature. The signature is ECDSA P-256
over "<METHOD>\\n<path with query>\\n<X-Timestamp>\\n<SHA-256 hex of the body>", made with the student's
active device key in the Android Keystore (docs/TRD.md section 9.4).
"""

from __future__ import annotations

import base64
import hashlib
from datetime import UTC, datetime
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import load_der_public_key
from fastapi import Request

from app import ratelimit
from app.config import get_settings
from app.db import pool as db_pool
from app.errors import AppError
from app.redis import client as redis_client
from app.services.verification.network import client_address, parse_trusted_proxies

MAX_CLOCK_SKEW_SECONDS = 60


def _unauthorized(message: str) -> AppError:
    return AppError(code="UNAUTHORIZED", status_code=401, message=message)


def _caller(request: Request) -> str:
    settings = get_settings()
    return client_address(request, parse_trusted_proxies(settings.TRUSTED_PROXY_IPS)) or "unknown"


async def current_device(request: Request) -> UUID:
    """Authenticate a student request. An address that keeps failing the signature check is slowed down."""
    caller = _caller(request)
    redis = redis_client.get_client()
    await ratelimit.blocked(redis, "signature-failures", caller, ratelimit.SIGNATURE_FAILURES_PER_MINUTE)
    try:
        return await _authenticate(request)
    except AppError as exc:
        if exc.status_code == 401:
            await ratelimit.record(redis, "signature-failures", caller, ratelimit.SIGNATURE_WINDOW_SECONDS)
        raise


async def _authenticate(request: Request) -> UUID:
    raw_student_id = request.headers.get("x-student-id")
    sig_header = request.headers.get("x-signature")
    ts_header = request.headers.get("x-timestamp")
    if not raw_student_id or not sig_header or not ts_header:
        raise _unauthorized("Device signature headers are required")

    try:
        student_id = UUID(raw_student_id)
        ts = int(ts_header)
    except ValueError as exc:
        raise _unauthorized("Invalid X-Student-Id or X-Timestamp header") from exc

    if abs(int(datetime.now(UTC).timestamp()) - ts) > MAX_CLOCK_SKEW_SECONDS:
        raise _unauthorized(f"Timestamp is more than {MAX_CLOCK_SKEW_SECONDS} seconds from server time")

    row = await db_pool.get_pool().fetchrow(
        "select public_key from devices where student_id = $1 and active = true order by enrolled_at desc limit 1",
        student_id,
    )
    if row is None:
        raise _unauthorized("No active device found for this student")

    body_hash = hashlib.sha256(await request.body()).hexdigest()
    path_with_query = request.url.path + (f"?{request.url.query}" if request.url.query else "")
    to_sign = f"{request.method.upper()}\n{path_with_query}\n{ts_header}\n{body_hash}"

    try:
        public_key = load_der_public_key(row["public_key"])
        if not isinstance(public_key, ec.EllipticCurvePublicKey):
            raise ValueError("device key is not an EC key")
        public_key.verify(base64.b64decode(sig_header), to_sign.encode("utf-8"), ec.ECDSA(hashes.SHA256()))
    except (InvalidSignature, ValueError, TypeError) as exc:
        raise _unauthorized("Invalid device signature") from exc

    return student_id
