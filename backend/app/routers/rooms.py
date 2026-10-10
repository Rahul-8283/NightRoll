from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.db.queries import rooms as rooms_q
from app.deps import CurrentWarden, DbPool
from app.errors import AppError
from app.schemas.rooms import AccessPointOut, RoomDetailOut, RoomOut, RoomStudentOut

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
