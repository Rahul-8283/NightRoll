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


class WifiNetworkScan(ApiModel):
    bssid: str
    rssi: float
    band: str  # '2.4GHz' or '5GHz'


class RoomScanObservation(ApiModel):
    networks: list[WifiNetworkScan]


class SubmitRoomScansRequest(ApiModel):
    scans: list[RoomScanObservation]


class RoomFingerprintResponse(ApiModel):
    id: UUID
    room_id: UUID
    version: int
    pattern: dict
    ap_count: int
    created_at: str
    age_seconds: int
    reset_pending: bool


class FingerprintResetResponse(ApiModel):
    reset_pending: bool
    room_id: UUID
