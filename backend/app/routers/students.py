from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.config import Settings, get_settings
from app.db.queries import enrollment as enrollment_q
from app.db.queries import students as students_q
from app.deps import CurrentWarden, DbPool
from app.errors import AppError
from app.schemas.enrollment import StudentEnrollmentStatus, WithdrawStudentResponse
from app.schemas.students import StudentOut
from app.services import enrollment as enrollment_svc

router = APIRouter(prefix="/v1/students", tags=["students"])


@router.get("", response_model=list[StudentOut])
async def list_students(
    pool: DbPool,
    _: CurrentWarden,
    room_id: UUID | None = None,
    floor: int | None = Query(default=None, ge=0),
) -> list[StudentOut]:
    rows = await students_q.list_students(pool, room_id=room_id, floor=floor)
    return [StudentOut(**dict(row)) for row in rows]


@router.get("/{student_id}/enrollment", response_model=StudentEnrollmentStatus)
async def get_student_enrollment(
    student_id: UUID,
    pool: DbPool,
    _: CurrentWarden,
) -> StudentEnrollmentStatus:
    row = await enrollment_q.get_student_enrollment_details(pool, student_id)
    if row is None:
        raise AppError(code="NOT_FOUND", status_code=404, message="Student not found")

    return StudentEnrollmentStatus(
        student_id=row["student_id"],
        roll_number=row["roll_number"],
        name=row["name"],
        room_id=row["room_id"],
        room_number=row["room_number"],
        enrolled=bool(row["enrolled_at"] is not None),
        enrolled_at=row["enrolled_at"],
        consent_at=row["consent_at"],
        consent_version=row["consent_version"],
        face_enrolled=bool(row["face_enrolled"]),
        device_enrolled=bool(row["device_enrolled"]),
        device_security_level=row["device_security_level"],
        room_fingerprint_enrolled=bool(row["room_fingerprint_version"] is not None),
        room_fingerprint_version=row["room_fingerprint_version"],
    )


@router.post("/{student_id}/withdraw", response_model=WithdrawStudentResponse)
async def withdraw_student(
    student_id: UUID,
    pool: DbPool,
    warden: CurrentWarden,
    settings: Annotated[Settings, Depends(get_settings)],
) -> WithdrawStudentResponse:
    await enrollment_svc.withdraw_student_consent(
        pool,
        settings,
        student_id=student_id,
        actor_id=warden.user_id,
    )
    return WithdrawStudentResponse(withdrawn=True, student_id=student_id)
