from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.db.queries import rooms as rooms_q
from app.deps import CurrentStudent, CurrentWarden, DbPool
from app.errors import AppError
from app.schemas.dashboard import RoomTonightOut
from app.schemas.rooms import (
    AccessPointOut,
    FingerprintResetResponse,
    RoomDetailOut,
    RoomFingerprintResponse,
    RoomOut,
    RoomStudentOut,
    SubmitRoomScansRequest,
)
from app.services import dashboard as dashboard_service
from app.services import fingerprint as fingerprint_svc

router = APIRouter(prefix="/v1/rooms", tags=["rooms"])


@router.get("", response_model=list[RoomOut])
async def list_rooms(pool: DbPool, _: CurrentWarden) -> list[RoomOut]:
    return [RoomOut(**dict(row)) for row in await rooms_q.list_rooms(pool)]


@router.get("/{room_id}", response_model=RoomDetailOut)
async def get_room(room_id: UUID, pool: DbPool, _: CurrentWarden) -> RoomDetailOut:
    room = await rooms_q.get_room(pool, room_id)
    if room is None:
        raise AppError(code="NOT_FOUND", status_code=404, message="Room not found")

    access_points = await rooms_q.list_access_points(pool, room_id)
    students = await rooms_q.list_students_in_room(pool, room_id)
    return RoomDetailOut(
        id=room["id"],
        number=room["number"],
        floor=room["floor"],
        subnet=room["subnet"],
        access_points=[AccessPointOut(**dict(row)) for row in access_points],
        students=[RoomStudentOut(**dict(row)) for row in students],
    )


@router.get("/{room_id}/tonight", response_model=RoomTonightOut)
async def room_tonight_endpoint(room_id: UUID, pool: DbPool, _: CurrentWarden) -> RoomTonightOut:
    room = await rooms_q.get_room(pool, room_id)
    if room is None:
        raise AppError(code="NOT_FOUND", status_code=404, message="Room not found")
    return await dashboard_service.room_tonight(pool, room_id, room)


@router.post("/{room_id}/fingerprint", response_model=RoomFingerprintResponse)
async def submit_room_fingerprint_endpoint(
    room_id: UUID,
    payload: SubmitRoomScansRequest,
    pool: DbPool,
    student_id: CurrentStudent,
) -> RoomFingerprintResponse:
    result = await fingerprint_svc.submit_room_fingerprint(
        pool,
        room_id=room_id,
        student_id=student_id,
        payload=payload,
    )
    return RoomFingerprintResponse(**result)


@router.post("/{room_id}/fingerprint/reset", response_model=FingerprintResetResponse)
async def reset_room_fingerprint_endpoint(
    room_id: UUID,
    pool: DbPool,
    warden: CurrentWarden,
) -> FingerprintResetResponse:
    result = await fingerprint_svc.reset_room_fingerprint(
        pool,
        room_id=room_id,
        actor_id=warden.user_id,
    )
    return FingerprintResetResponse(**result)


@router.get("/{room_id}/fingerprint", response_model=RoomFingerprintResponse)
async def get_room_fingerprint_endpoint(
    room_id: UUID,
    pool: DbPool,
    _: CurrentWarden,
) -> RoomFingerprintResponse:
    result = await fingerprint_svc.get_room_fingerprint_status(pool, room_id)
    return RoomFingerprintResponse(**result)
