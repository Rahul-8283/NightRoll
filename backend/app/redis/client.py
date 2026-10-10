"""The Redis client, connecting to hosted Upstash over TLS.

`Settings` already refuses a non-`rediss://` URL, so this module trusts the
URL it is given. A small connect timeout and retry limit keep a slow or
unreachable Upstash endpoint from hanging a request.
"""

from __future__ import annotations

from redis.asyncio import Redis
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff

from app.config import Settings

_client: Redis | None = None


async def connect(settings: Settings) -> Redis:
    global _client
    _client = Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
        retry_on_timeout=True,
        retry=Retry(ExponentialBackoff(base=0.1, cap=1.0), retries=3),
        health_check_interval=30,
    )
    return _client


async def disconnect() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def get_client() -> Redis:
    if _client is None:
        raise RuntimeError("redis client is not initialised; app startup must call redis.client.connect() first")
    return _client


async def ping() -> bool:
    try:
        return bool(await get_client().ping())
    except Exception:
        return False
