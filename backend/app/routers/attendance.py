from __future__ import annotations

from fastapi import APIRouter

from app.deps import CurrentStudent, DbPool, RedisClient
from app.schemas.attendance import NonceStatusOut
from app.services import attendance as attendance_service

router = APIRouter(prefix="/v1/attendance", tags=["attendance"])


@router.get("/nonce", response_model=NonceStatusOut, response_model_exclude_none=True)
async def nonce_status(student_id: CurrentStudent, pool: DbPool, redis: RedisClient) -> NonceStatusOut:
    return NonceStatusOut(**await attendance_service.student_status(pool, redis, student_id))
