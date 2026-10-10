"""CSV export of attendance by date range, floor or room (Phase 11 section 6)."""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.deps import CurrentWarden, DbPool
from app.services import exports as exports_svc

router = APIRouter(prefix="/v1/exports", tags=["exports"])


@router.get("/attendance")
async def export_attendance(
    pool: DbPool,
    warden: CurrentWarden,
    date_from: Annotated[date, Query(alias="from")],
    date_to: Annotated[date, Query(alias="to")],
    floor: Annotated[int | None, Query(ge=0)] = None,
    room: UUID | None = None,
) -> StreamingResponse:
    exports_svc.check_range(date_from, date_to)
    filename = f"nightroll-attendance-{date_from.isoformat()}-to-{date_to.isoformat()}.csv"
    return StreamingResponse(
        exports_svc.stream(pool, warden, date_from=date_from, date_to=date_to, floor=floor, room_id=room),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
