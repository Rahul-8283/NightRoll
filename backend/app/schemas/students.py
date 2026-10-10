"""Response shapes for student endpoints. No embedding or public key ever appears here."""

from __future__ import annotations

from uuid import UUID

from app.schemas.common import ApiModel


class StudentOut(ApiModel):
    id: UUID
    roll_number: str
    name: str
    room_id: UUID
    room_number: str
    floor: int
    active: bool
    enrolled: bool


class ChangeRoomRequest(ApiModel):
    room_id: UUID


class ChangeRoomResponse(ApiModel):
    student_id: UUID
    room_id: UUID
    room_number: str
