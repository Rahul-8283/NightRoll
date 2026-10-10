"""Pydantic schemas for Face Worker API requests and responses."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check payload."""

    ready: bool
    model_version: str
    antispoof_available: bool
    last_cleanup: datetime | None = None


class EnrollmentResponse(BaseModel):
    """Response returned upon successful student face enrollment."""

    model_version: str
    frames_used: int


class HeadPose(BaseModel):
    """Estimated head orientation angles in degrees."""

    pitch: float = Field(description="Nod angle (up/down)")
    yaw: float = Field(description="Turn angle (left/right)")
    roll: float = Field(description="Tilt angle (ear to shoulder)")


class FrameIssue(BaseModel):
    """Describes a quality or validation defect detected in a frame."""

    frame_index: int
    code: str = Field(
        description="Issue code: BAD_IMAGE, NO_FACE, MULTIPLE_FACES, FACE_TOO_SMALL, TOO_BLURRY, BAD_LIGHTING, BAD_POSE"
    )
    detail: str


class FrameResult(BaseModel):
    """What the worker measured for one frame, in the order the frames were sent."""

    index: int
    usable: bool
    issues: list[str]
    similarity: float | None = Field(description="Cosine similarity to the enrolled embedding, if usable")
    antispoof: float | None = Field(description="Real-face score 0 to 1, if usable and the model is loaded")
    yaw: float | None = Field(description="Head turn in degrees, if a face was found")
    pitch: float | None = None
    roll: float | None = None


class VerifyResponse(BaseModel):
    """Verification results consumed by backend scoring and fusion (Phase 9)."""

    usable_frames: int
    best_similarity: float
    median_similarity: float
    antispoof_median: float
    antispoof_scores: list[float]
    antispoof_available: bool
    head_poses: list[HeadPose]
    frame_issues: list[FrameIssue]
    frame_results: list[FrameResult]
    frames_path: str | None
    model_version: str


class Base64Frame(BaseModel):
    """Optional JSON wrapper for base64 encoded frame input."""

    index: int
    data: str  # Base64 string
    sha256: str | None = None
    tag: str | None = None  # e.g., 'neutral', 'turn_left', 'turn_right'


class VerifyJSONRequest(BaseModel):
    """Verification request schema when delivered via JSON instead of multipart."""

    student_id: UUID
    window_id: UUID
    mark_id: UUID
    frames: list[Base64Frame]
    frame_hashes: list[str]


class FrameLinksRequest(BaseModel):
    """One mark's frame folder, as stored by the backend: frames/{window_id}/{mark_id}."""

    folder: str = Field(pattern=r"^frames/[0-9a-fA-F-]{36}/[0-9a-fA-F-]{36}$")


class FrameLink(BaseModel):
    name: str
    url: str


class FrameLinksResponse(BaseModel):
    """Short-lived links to view a mark's frames. The worker signs them and never returns the bytes."""

    expires_in_seconds: int
    links: list[FrameLink]

