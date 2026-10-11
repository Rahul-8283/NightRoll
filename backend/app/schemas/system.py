"""Response shapes for the admin System page and the alert banner (Phase 12, tasks 6.4 and 6.5)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from app.schemas.common import ApiModel
from app.schemas.dashboard import WindowBrief

Health = Literal["ok", "degraded", "down"]
Severity = Literal["critical", "warning"]


class AlertOut(ApiModel):
    code: str
    severity: Severity
    message: str


class AlertsOut(ApiModel):
    alerts: list[AlertOut]


class ServiceOut(ApiModel):
    status: Health
    detail: str | None = None


class FaceWorkerOut(ServiceOut):
    ready: bool = False
    antispoof_available: bool = False
    model_version: str | None = None
    latency_ms: float | None = None


class SchedulerOut(ServiceOut):
    last_heartbeat: datetime | None = None
    age_seconds: float | None = None


class JobOut(ApiModel):
    name: str
    last_run: datetime | None = None
    detail: str | None = None


class GateFailureOut(ApiModel):
    reason: str
    message: str
    count: int


class TonightStatsOut(ApiModel):
    attempts: int
    verdicts: dict[str, int]
    gate_failures: list[GateFailureOut]
    rejection_rate_5m: float | None = None
    attempts_5m: int = 0


class LatencyOut(ApiModel):
    """Milliseconds since the API last started. None until a request has been timed."""

    requests_p50_ms: float | None = None
    requests_p95_ms: float | None = None
    verify_p95_ms: float | None = None
    face_worker_p95_ms: float | None = None


class SystemOut(ApiModel):
    generated_at: datetime
    app_env: str
    version: str
    relaxed_settings: list[str]
    database: ServiceOut
    redis: ServiceOut
    face_worker: FaceWorkerOut
    scheduler: SchedulerOut
    window: WindowBrief | None
    tonight: TonightStatsOut
    latency: LatencyOut
    websocket_connections: int
    jobs: list[JobOut]
    alerts: list[AlertOut]
