"""The read-only audit view for admins (Phase 11 section 7)."""

from __future__ import annotations

import json
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from app.db.queries import audit as audit_q
from app.deps import AdminWarden, DbPool
from app.schemas.reviews import AuditPageOut, AuditRowOut

router = APIRouter(prefix="/v1/audit", tags=["audit"])


def _payload(value):
    """The database driver returns jsonb as text. The API returns it as an object."""
    return json.loads(value) if isinstance(value, str) else value


@router.get("", response_model=AuditPageOut)
async def audit_page(
    pool: DbPool,
    _: AdminWarden,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    actor: Annotated[str | None, Query(max_length=200)] = None,
    action: Annotated[str | None, Query(max_length=80)] = None,
    before: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AuditPageOut:
    """Newest first. Pass next_before back as `before` to load the next page."""
    rows = await audit_q.page(
        pool,
        date_from=date_from,
        date_to=date_to,
        actor=actor or None,
        action=action or None,
        before=before,
        limit=limit,
    )
    items = [AuditRowOut(**{**dict(row), "payload": _payload(row["payload"])}) for row in rows]
    next_before = items[-1].id if len(items) == limit else None
    return AuditPageOut(items=items, next_before=next_before)
