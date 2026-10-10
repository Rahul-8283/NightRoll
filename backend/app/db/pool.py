"""The asyncpg connection pool, opened at startup and closed at shutdown.

Statement caching is off (`statement_cache_size=0`). Supabase's pooled
connection in transaction mode does not support server-side prepared
statements; keeping the cache off means the pool works the same way whether
`DATABASE_URL` points at the direct connection or the pooled one.
"""

from __future__ import annotations

import asyncpg

from app.config import Settings

_pool: asyncpg.Pool | None = None


async def connect(settings: Settings) -> asyncpg.Pool:
    global _pool
    _pool = await asyncpg.create_pool(
        dsn=settings.DATABASE_URL,
        min_size=1,
        max_size=10,
        statement_cache_size=0,
        timeout=10,
        command_timeout=10,
    )
    return _pool


async def disconnect() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("database pool is not initialised; app startup must call db.pool.connect() first")
    return _pool


async def ping() -> bool:
    try:
        async with get_pool().acquire() as conn:
            return await conn.fetchval("select 1") == 1
    except Exception:
        return False
