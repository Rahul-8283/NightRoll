from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.config import Settings, get_settings
from app.db.queries import enrollment as enrollment_q
from app.db.queries import rooms as rooms_q
from app.db.queries import students as students_q
from app.deps import CurrentWarden, DbPool, RedisClient
from app.errors import AppError
from app.schemas.enrollment import StudentEnrollmentStatus, WithdrawStudentResponse
from app.schemas.students import ChangeRoomRequest, ChangeRoomResponse, StudentOut
from app.services import audit
from app.services import enrollment as enrollment_svc

router = APIRouter(prefix="/v1/students", tags=["students"])


@router.get("", response_model=list[StudentOut])
async def list_students(
    pool: DbPool,
    _: CurrentWarden,
    room_id: UUID | None = None,
    floor: int | None = Query(default=None, ge=0),
    q: str | None = Query(default=None, max_length=60),
) -> list[StudentOut]:
    rows = await students_q.list_students(pool, room_id=room_id, floor=floor, search=q)
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


@router.patch("/{student_id}/room", response_model=ChangeRoomResponse)
async def change_student_room(
    student_id: UUID,
    body: ChangeRoomRequest,
    pool: DbPool,
    warden: CurrentWarden,
) -> ChangeRoomResponse:
    room = await rooms_q.get_room(pool, body.room_id)
    if room is None:
        raise AppError(code="NOT_FOUND", status_code=404, message="Room not found")
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await students_q.set_student_room(conn, student_id, body.room_id)
            if row is None:
                raise AppError(code="NOT_FOUND", status_code=404, message="Student not found")
            await audit.write(
                conn,
                actor=warden.user_id,
                action="student.room_changed",
                target_id=str(student_id),
                payload={"room_id": str(body.room_id)},
            )
    return ChangeRoomResponse(student_id=student_id, room_id=body.room_id, room_number=room["number"])


@router.post("/{student_id}/withdraw", response_model=WithdrawStudentResponse)
async def withdraw_student(
    student_id: UUID,
    pool: DbPool,
    redis: RedisClient,
    warden: CurrentWarden,
    settings: Annotated[Settings, Depends(get_settings)],
) -> WithdrawStudentResponse:
    await enrollment_svc.withdraw_student_consent(
        pool,
        redis,
        settings,
        student_id=student_id,
        actor_id=warden.user_id,
    )
    return WithdrawStudentResponse(withdrawn=True, student_id=student_id)
