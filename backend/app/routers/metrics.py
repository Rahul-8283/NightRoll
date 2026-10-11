"""GET /v1/metrics in Prometheus text format (Phase 12, task 6.2).

Allowed for an admin's token, or for a caller on the internal network that reaches the API directly (a Prometheus
scraper inside the Compose network). A request that came through the reverse proxy always arrives from the proxy's
address, so being "internal" says nothing about the person behind it: through the proxy only an admin token works.
"""

from __future__ import annotations

import ipaddress
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse
from redis.exceptions import RedisError

from app import metrics
from app.auth.supabase import authenticate_token, extract_token
from app.config import Settings, get_settings
from app.errors import AppError
from app.redis import client as redis_client
from app.services import ops
from app.services.verification.network import parse_trusted_proxies

router = APIRouter(tags=["metrics"])

CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"


def _is_internal(peer: str | None) -> bool:
    try:
        address = ipaddress.ip_address(peer or "")
    except ValueError:
        return False
    return address.is_private or address.is_loopback


def _allowed(request: Request, settings: Settings) -> None:
    peer = request.client.host if request.client else None
    if peer not in parse_trusted_proxies(settings.TRUSTED_PROXY_IPS) and _is_internal(peer):
        return
    warden, _ = authenticate_token(extract_token(request), settings)
    if warden.role != "admin":
        raise AppError(code="FORBIDDEN", status_code=403, message="Metrics need an admin account")


async def _scheduler_heartbeat_age() -> None:
    try:
        age = await ops.scheduler_heartbeat_age(redis_client.get_client())
    except (RedisError, OSError, ValueError):
        age = None
    metrics.scheduler_heartbeat_age.set(-1.0 if age is None else round(age, 1))


metrics.add_collector(_scheduler_heartbeat_age)


@router.get("/v1/metrics", response_class=PlainTextResponse)
async def read_metrics(request: Request, settings: Annotated[Settings, Depends(get_settings)]) -> PlainTextResponse:
    _allowed(request, settings)
    return PlainTextResponse(await metrics.render(), media_type=CONTENT_TYPE)
