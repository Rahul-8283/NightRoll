"""Response shapes for room endpoints. No embedding or public key ever appears here."""

from __future__ import annotations

from uuid import UUID

from app.schemas.common import ApiModel


class RoomOut(ApiModel):
    id: UUID
    number: str
    floor: int
    student_count: int


class AccessPointOut(ApiModel):
    bssid: str
    band: str | None


class RoomStudentOut(ApiModel):
    id: UUID
    roll_number: str
    name: str
    active: bool
    enrolled: bool


class RoomDetailOut(ApiModel):
    id: UUID
    number: str
    floor: int
    subnet: str | None
    access_points: list[AccessPointOut]
    students: list[RoomStudentOut]
