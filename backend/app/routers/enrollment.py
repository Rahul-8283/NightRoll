"""Endpoints for student enrollment codes and enrollment completion."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.config import Settings, get_settings
from app.deps import CurrentWarden, DbPool, RedisClient
from app.schemas.enrollment import (
    CreateEnrollmentCodeRequest,
    EnrollmentCodeResponse,
    EnrollmentSuccessResponse,
)
from app.services import enrollment as enrollment_svc

router = APIRouter(prefix="/v1", tags=["enrollment"])


@router.post("/enrollment-codes", response_model=EnrollmentCodeResponse)
async def create_enrollment_code(
    payload: CreateEnrollmentCodeRequest,
    pool: DbPool,
    redis: RedisClient,
    warden: CurrentWarden,
) -> EnrollmentCodeResponse:
    warden_uuid = None
    try:
        warden_uuid = UUID(warden.user_id)
    except Exception:
        pass

    code, expires_at = await enrollment_svc.issue_enrollment_code(
        pool,
        redis,
        student_id=payload.student_id,
        warden_id=warden_uuid,
    )
    return EnrollmentCodeResponse(
        code=code,
        student_id=payload.student_id,
        expires_at=expires_at,
    )


@router.post("/enrollments", response_model=EnrollmentSuccessResponse)
async def enroll_student(
    pool: DbPool,
    redis: RedisClient,
    settings: Annotated[Settings, Depends(get_settings)],
    code: str = Form(...),  # noqa: B008
    roll_number: str = Form(...),  # noqa: B008
    public_key: str = Form(...),  # noqa: B008
    key_security_level: str = Form(...),  # noqa: B008
    consent_version: str = Form(...),  # noqa: B008
    frames: list[UploadFile] = File(...),  # noqa: B008
) -> EnrollmentSuccessResponse:
    frames_data: list[tuple[str, bytes, str]] = []
    for f in frames:
        content = await f.read()
        frames_data.append((f.filename or "frame.jpg", content, f.content_type or "image/jpeg"))

    result = await enrollment_svc.complete_student_enrollment(
        pool,
        redis,
        settings,
        code=code,
        roll_number=roll_number,
        public_key_b64=public_key,
        key_security_level=key_security_level,
        consent_version=consent_version,
        frames=frames_data,
    )
    return EnrollmentSuccessResponse(**result)
