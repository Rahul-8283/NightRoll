"""Request and response shapes for reviews, overrides, manual marks and the student status view."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.schemas.common import ApiModel
from app.schemas.dashboard import ReasonOut, ScorerOut

Decision = Literal["APPROVED", "DECLINED", "OVERRIDDEN", "MANUAL"]
DecidedHow = Literal["override", "manual", "automatic", "approved", "declined"]
EffectiveStatus = Literal["PRESENT", "ABSENT", "PENDING", "NOT_MARKED", "OFF"]


class ReviewItem(ApiModel):
    mark_id: UUID
    window_id: UUID
    student_id: UUID
    student_name: str
    roll_number: str
    room_id: UUID
    room_number: str
    floor: int
    marked_at: datetime
    score: float | None
    attempt: int
    attempts_tonight: int
    reasons: list[ReasonOut]
    scorers: list[ScorerOut]
    fingerprint_created_at: datetime | None
    frames_available: bool


class AttemptOut(ApiModel):
    mark_id: UUID
    verdict: str
    reasons: list[ReasonOut]
    marked_at: datetime
    attempt: int


class DecisionOut(ApiModel):
    decision: Decision
    status: str | None
    reviewed_by: str
    note: str | None
    reviewed_at: datetime


class MarkDetailOut(ReviewItem):
    verdict: str
    earlier_attempts: list[AttemptOut]
    decisions: list[DecisionOut]
    effective_status: EffectiveStatus


class ReviewDecisionIn(ApiModel):
    decision: Literal["APPROVED", "DECLINED"]
    note: str | None = Field(default=None, max_length=500)


class OverrideIn(ApiModel):
    status: Literal["PRESENT", "ABSENT"]
    note: str = Field(min_length=10, max_length=500)


class ManualMarkIn(ApiModel):
    student_id: UUID
    window_id: UUID
    note: str = Field(min_length=10, max_length=500)


class MarkDecisionOut(ApiModel):
    mark_id: UUID
    student_id: UUID
    status: EffectiveStatus
    decided_how: DecidedHow | None


class ManualMarkOut(ApiModel):
    mark_id: UUID
    student_id: UUID
    window_id: UUID
    status: EffectiveStatus
