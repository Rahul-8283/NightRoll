from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import AwareDatetime

from app.schemas.common import ApiModel


class WindowIn(ApiModel):
    night: date
    opens_at: AwareDatetime
    closes_at: AwareDatetime
    off: bool = False


class WindowOut(ApiModel):
    id: UUID
    night: date
    opens_at: datetime
    closes_at: datetime
    state: str
