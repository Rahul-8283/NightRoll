from __future__ import annotations

from app.schemas.common import ApiModel

ServiceStatus = str  # "ok" | "degraded"


class HealthOut(ApiModel):
    status: ServiceStatus
    db: ServiceStatus
    redis: ServiceStatus
    scheduler: ServiceStatus
    scheduler_age_seconds: float | None = None
    version: str
