from __future__ import annotations

from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import Depends
from redis.asyncio import Redis

from app.auth.device import current_student_stub
from app.auth.supabase import Warden, current_warden, require_admin
from app.db import pool as db_pool
from app.redis import client as redis_client


def get_db() -> asyncpg.Pool:
    return db_pool.get_pool()


def get_redis() -> Redis:
    return redis_client.get_client()


DbPool = Annotated[asyncpg.Pool, Depends(get_db)]
RedisClient = Annotated[Redis, Depends(get_redis)]
CurrentWarden = Annotated[Warden, Depends(current_warden)]
AdminWarden = Annotated[Warden, Depends(require_admin)]
CurrentStudent = Annotated[UUID, Depends(current_student_stub)]
