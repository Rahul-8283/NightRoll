from __future__ import annotations

from app.schemas.common import ApiModel

ServiceStatus = str  # "ok" | "degraded"


class HealthOut(ApiModel):
    status: ServiceStatus
    db: ServiceStatus
    redis: ServiceStatus
    scheduler: ServiceStatus
    version: str
