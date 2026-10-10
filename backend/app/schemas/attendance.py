from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.schemas.common import ApiModel


class NonceStatusOut(ApiModel):
    state: str
    window_id: UUID | None = None
    opens_at: datetime | None = None
    closes_at: datetime | None = None
    nonce: str | None = None
    challenge: list[str] | None = None
