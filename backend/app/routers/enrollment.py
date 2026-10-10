"""Endpoints for student enrollment codes and enrollment completion."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.deps import CurrentWarden, DbPool, RedisClient
from app.schemas.enrollment import CreateEnrollmentCodeRequest, EnrollmentCodeResponse
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
