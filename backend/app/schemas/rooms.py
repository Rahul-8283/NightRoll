"""Response shapes for room endpoints. No embedding or public key ever appears here."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field

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
    bssid: str = Field(pattern=r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")
    rssi: float = Field(ge=-127, le=0, description="Signal strength in dBm")
    band: Literal["2.4GHz", "5GHz", "6GHz"]


class RoomScanObservation(ApiModel):
    networks: list[WifiNetworkScan] = Field(max_length=300)


class SubmitRoomScansRequest(ApiModel):
    scans: list[RoomScanObservation] = Field(max_length=10)


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
