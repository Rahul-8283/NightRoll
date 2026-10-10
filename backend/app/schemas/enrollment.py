from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateEnrollmentCodeRequest(BaseModel):
    student_id: UUID


class EnrollmentCodeResponse(BaseModel):
    code: str
    student_id: UUID
    expires_at: datetime


class StudentEnrollmentStatus(BaseModel):
    student_id: UUID
    roll_number: str
    name: str
    room_id: UUID
    room_number: str
    enrolled: bool
    enrolled_at: datetime | None = None
    consent_at: datetime | None = None
    consent_version: str | None = None
    face_enrolled: bool
    device_enrolled: bool
    device_security_level: str | None = None
    room_fingerprint_enrolled: bool
    room_fingerprint_version: int | None = None


class WithdrawStudentResponse(BaseModel):
    withdrawn: bool
    student_id: UUID
