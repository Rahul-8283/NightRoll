from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.db.queries import students as students_q
from app.deps import CurrentWarden, DbPool
from app.schemas.students import StudentOut

router = APIRouter(prefix="/v1/students", tags=["students"])


@router.get("", response_model=list[StudentOut])
async def list_students(
    pool: DbPool,
    _: CurrentWarden,
    room_id: UUID | None = None,
    floor: int | None = Query(default=None, ge=0),
) -> list[StudentOut]:
    rows = await students_q.list_students(pool, room_id=room_id, floor=floor)
    return [StudentOut(**dict(row)) for row in rows]
