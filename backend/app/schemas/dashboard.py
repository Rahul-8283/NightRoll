"""Response shapes for the warden dashboard's read views and live snapshot."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from app.schemas.common import ApiModel


class WindowBrief(ApiModel):
    id: UUID
    night: date
    opens_at: datetime
    closes_at: datetime
    state: str


class ReasonOut(ApiModel):
    code: str
    message: str


class RoomCount(ApiModel):
    room_id: UUID
    number: str
    floor: int
    present: int
    total: int
    pending_review: int
    absent: int = 0
    rejected: int
    health: list[str] = []


class RecentMark(ApiModel):
    mark_id: UUID
    verdict: str
    reasons: list[ReasonOut]
    marked_at: datetime
    room_number: str
    student_name: str
    score: float | None


class Totals(ApiModel):
    enrolled: int
    present: int
    pending_review: int
    not_marked: int
    absent: int = 0
    rejected: int


class TonightOut(ApiModel):
    window: WindowBrief | None
    totals: Totals
    rooms: list[RoomCount]
    recent: list[RecentMark]


class RoomUpdateEvent(ApiModel):
    type: Literal["room_update"] = "room_update"
    room_id: UUID
    present: int
    total: int
    pending_review: int
    rejected: int
    health: list[str] = []
    last: RecentMark | None


class ScorerOut(ApiModel):
    name: str
    score: float
    reason: str | None
    detail: str


class MarkDetail(ApiModel):
    mark_id: UUID
    verdict: str
    score: float | None
    reasons: list[ReasonOut]
    marked_at: datetime
    attempt: int
    scorers: list[ScorerOut]


class RoomStudentStatus(ApiModel):
    student_id: UUID
    roll_number: str
    name: str
    active: bool
    enrolled: bool
    face_enrolled: bool
    device_enrolled: bool
    device_security_level: str | None = None
    mark: MarkDetail | None


class RoomTonightOut(ApiModel):
    room_id: UUID
    number: str
    floor: int
    window: WindowBrief | None
    students: list[RoomStudentStatus]
    health: list[str] = []


class WindowHistoryOut(ApiModel):
    id: UUID
    night: date
    opens_at: datetime
    closes_at: datetime
    state: str
    present: int
    enrolled: int
