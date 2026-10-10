"""Shapes for the signed marking submission (Phase 7 section 6) and its response (Phase 8 section 13).

Every model rejects unknown fields. These are only read after the signature gate has passed, so a
field the phone did not sign never reaches the decision.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field

from app.schemas.common import ApiModel

SHA256_HEX = r"^[0-9a-f]{64}$"
MAC = r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$"
Band = Literal["2.4GHz", "5GHz", "6GHz"]
ChallengeAction = Literal["blink", "turn_left", "turn_right", "smile"]
FrameTag = Literal["blink", "turn_left", "turn_right", "smile", "neutral"]


class ChallengeRecord(ApiModel):
    action: ChallengeAction
    started_ms: int = Field(ge=0)
    detected_ms: int = Field(ge=0)


class FrameRecord(ApiModel):
    index: int = Field(ge=0, le=4)
    sha256: str = Field(pattern=SHA256_HEX)
    tag: FrameTag


class ConnectedNetwork(ApiModel):
    bssid: str = Field(pattern=MAC)
    rssi: int = Field(ge=-127, le=0)
    band: Band


class ScannedNetwork(ApiModel):
    bssid: str = Field(pattern=MAC)
    rssi: int = Field(ge=-127, le=0)
    band: Band


class WifiRecord(ApiModel):
    connected: ConnectedNetwork
    scan_age_ms: int = Field(ge=0)
    scan: list[ScannedNetwork] = Field(max_length=300)


class EnvironmentRecord(ApiModel):
    vpn: bool
    proxy: bool
    mock_location: bool
    developer_options: bool
    on_wifi: bool


class SubmissionPayload(ApiModel):
    v: int
    student_id: UUID
    window_id: UUID
    nonce: str = Field(min_length=16, max_length=128)
    client_time: str = Field(max_length=40)
    challenge: list[ChallengeRecord] = Field(min_length=2, max_length=2)
    frames: list[FrameRecord] = Field(min_length=1, max_length=5)
    wifi: WifiRecord
    environment: EnvironmentRecord
    app_version: str = Field(max_length=32)


class ReasonOut(ApiModel):
    code: str
    message: str


class VerifyOut(ApiModel):
    mark_id: UUID | None
    verdict: Literal["PRESENT", "NEEDS_REVIEW", "REJECTED"]
    score: float | None
    reasons: list[ReasonOut]
    retry_allowed: bool
    attempts_left: int
    fallback: Literal["NONE", "GROUND_FLOOR_SCANNER"]
