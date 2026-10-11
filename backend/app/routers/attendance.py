from __future__ import annotations

import hashlib
import json
import re
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from starlette.datastructures import UploadFile

from app import ratelimit
from app.config import Settings, get_settings
from app.deps import CurrentStudent, CurrentWarden, DbPool, RedisClient
from app.errors import AppError
from app.schemas.attendance import NonceStatusOut
from app.schemas.dashboard import TonightOut
from app.schemas.verify import VerifyOut
from app.services import attendance as attendance_service
from app.services import dashboard as dashboard_service
from app.services.verification import service as verification_service
from app.services.verification.network import client_address, parse_trusted_proxies
from app.services.verification.runner import Submission

router = APIRouter(prefix="/v1/attendance", tags=["attendance"])

MAX_PAYLOAD_BYTES = 64 * 1024
MAX_FRAME_BYTES = 1024 * 1024
MAX_FRAMES = 5
_FRAME_FIELD = re.compile(r"^frame_(\d+)$")


@router.get("/tonight", response_model=TonightOut)
async def tonight(pool: DbPool, _: CurrentWarden) -> TonightOut:
    return await dashboard_service.tonight(pool)


@router.get("/nonce", response_model=NonceStatusOut, response_model_exclude_none=True)
async def nonce_status(student_id: CurrentStudent, pool: DbPool, redis: RedisClient) -> NonceStatusOut:
    await ratelimit.enforce(redis, "nonce", str(student_id), ratelimit.NONCE_PER_MINUTE, 60)
    return NonceStatusOut(**await attendance_service.student_status(pool, redis, student_id))


def _claimed_student(payload_bytes: bytes) -> UUID | None:
    """Read student_id only to find the device key. Nothing else in the payload is trusted yet."""
    try:
        raw = json.loads(payload_bytes).get("student_id")
        return UUID(raw) if isinstance(raw, str) else None
    except (ValueError, AttributeError):
        return None


async def _frames(form) -> list[bytes]:
    indexed: dict[int, UploadFile] = {}
    for key, value in form.multi_items():
        match = _FRAME_FIELD.match(key)
        if match is None:
            continue
        if not isinstance(value, UploadFile):
            raise AppError(code="PAYLOAD_INVALID", status_code=422, message=f"{key} must be an image file")
        indexed[int(match.group(1))] = value
    if len(indexed) > MAX_FRAMES:
        raise AppError(code="TOO_MANY_FRAMES", status_code=422, message=f"At most {MAX_FRAMES} frames are accepted")
    if sorted(indexed) != list(range(len(indexed))):
        raise AppError(code="PAYLOAD_INVALID", status_code=422, message="frames must be numbered from 0")

    frames: list[bytes] = []
    for index in range(len(indexed)):
        body = await indexed[index].read(MAX_FRAME_BYTES + 1)
        if len(body) > MAX_FRAME_BYTES:
            raise AppError(
                code="FRAME_TOO_LARGE", status_code=413, message=f"Each frame must be at most {MAX_FRAME_BYTES} bytes"
            )
        frames.append(body)
    return frames


@router.post("/verify", response_model=VerifyOut)
async def verify_attendance(
    request: Request,
    pool: DbPool,
    redis: RedisClient,
    settings: Annotated[Settings, Depends(get_settings)],
) -> VerifyOut:
    trusted = parse_trusted_proxies(settings.TRUSTED_PROXY_IPS)
    await ratelimit.blocked(
        redis,
        "signature-failures",
        client_address(request, trusted) or "unknown",
        ratelimit.SIGNATURE_FAILURES_PER_MINUTE,
    )
    form = await request.form()

    payload_field = form.get("payload")
    if not isinstance(payload_field, str):
        raise AppError(code="PAYLOAD_INVALID", status_code=422, message="payload is required")
    payload_bytes = payload_field.encode("utf-8")
    if len(payload_bytes) > MAX_PAYLOAD_BYTES:
        raise AppError(code="PAYLOAD_TOO_LARGE", status_code=413, message="payload is too large")

    signature = form.get("signature")
    if not isinstance(signature, str) or not signature:
        raise AppError(code="PAYLOAD_INVALID", status_code=422, message="signature is required")

    integrity_token = form.get("integrity_token")
    integrity_error = form.get("integrity_error")
    submission = Submission(
        settings=settings,
        pool=pool,
        redis=redis,
        client_ip=client_address(request, trusted),
        payload_bytes=payload_bytes,
        signature=signature,
        integrity_token=integrity_token if isinstance(integrity_token, str) else "",
        integrity_error=integrity_error if isinstance(integrity_error, str) else None,
        frames=await _frames(form),
        claimed_student_id=_claimed_student(payload_bytes),
        payload_hash=hashlib.sha256(payload_bytes).hexdigest(),
    )
    return await verification_service.submit(submission)
