"""The live feed for the warden dashboard: WS /v1/ws/rooms (Phase 10 section 8).

A browser cannot set headers on a WebSocket, so the first message carries the access token. Every
update comes from Redis, so it reaches every connected dashboard, even if the API runs as more than one
process.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app import metrics
from app.auth.supabase import authenticate_token
from app.config import get_settings
from app.db import pool as db_pool
from app.errors import AppError
from app.redis import client as redis_client
from app.redis import keys
from app.services import dashboard as dashboard_service

router = APIRouter(tags=["live"])
logger = logging.getLogger("nightroll.live")

AUTH_TIMEOUT_SECONDS = 5.0
PING_INTERVAL_SECONDS = 20.0
CLOSE_UNAUTHORIZED = 4401
CLOSE_FORBIDDEN = 4403
CHANNELS = (keys.MARK_RECORDED_CHANNEL, keys.WINDOW_STATE_CHANNEL, keys.ENROLLMENT_CHANNEL)


class _Dropped(Exception):
    """The connection should close: the client stopped answering or its token expired."""


async def _authenticate(websocket: WebSocket) -> float:
    """Read the first message, check the token, and return its expiry as a Unix time."""
    raw = await asyncio.wait_for(websocket.receive_text(), timeout=AUTH_TIMEOUT_SECONDS)
    message = json.loads(raw)
    if message.get("type") != "auth" or not isinstance(message.get("token"), str):
        raise AppError(code="UNAUTHORIZED", status_code=401, message="The first message must carry the token")
    _, claims = authenticate_token(message["token"], get_settings())
    return float(claims["exp"])


async def _forward(websocket: WebSocket, send_lock: asyncio.Lock, pubsub) -> None:
    pool = db_pool.get_pool()
    async for message in pubsub.listen():
        if message.get("type") != "message":
            continue
        event = json.loads(message["data"])
        if message["channel"] == keys.MARK_RECORDED_CHANNEL:
            room_id = UUID(event["room_id"]) if event.get("room_id") else None
            if room_id is None:
                continue
            mark_id = UUID(event["mark_id"]) if event.get("mark_id") else None
            update = await dashboard_service.room_update(pool, room_id, mark_id)
            if update is None:
                continue
            payload = update.model_dump(mode="json")
        else:
            payload = event
        async with send_lock:
            await websocket.send_json(payload)


async def _receive(websocket: WebSocket, state: dict) -> None:
    while True:
        message = json.loads(await websocket.receive_text())
        if message.get("type") == "pong":
            state["last_pong"] = time.monotonic()


async def _ping(websocket: WebSocket, send_lock: asyncio.Lock, state: dict) -> None:
    while True:
        await asyncio.sleep(PING_INTERVAL_SECONDS)
        if time.monotonic() - state["last_pong"] > 2 * PING_INTERVAL_SECONDS:
            raise _Dropped("no pong")
        async with send_lock:
            await websocket.send_json({"type": "ping"})


async def _expire_at(expires_at: float) -> None:
    await asyncio.sleep(max(0.0, expires_at - time.time()))
    raise _Dropped("token expired")


@router.websocket("/v1/ws/rooms")
async def live_rooms(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        expires_at = await _authenticate(websocket)
    except AppError as exc:
        code = CLOSE_FORBIDDEN if exc.status_code == 403 else CLOSE_UNAUTHORIZED
        await websocket.close(code=code, reason=exc.message[:120])
        return
    except (TimeoutError, ValueError, KeyError, WebSocketDisconnect):
        await websocket.close(code=CLOSE_UNAUTHORIZED, reason="No valid token received")
        return

    metrics.websocket_connections.inc()
    try:
        await _serve(websocket, expires_at)
    finally:
        metrics.websocket_connections.dec()


async def _serve(websocket: WebSocket, expires_at: float) -> None:
    pool = db_pool.get_pool()
    redis = redis_client.get_client()
    send_lock = asyncio.Lock()
    state = {"last_pong": time.monotonic()}

    snapshot = await dashboard_service.tonight(pool)
    async with send_lock:
        await websocket.send_json({"type": "snapshot", **snapshot.model_dump(mode="json")})

    pubsub = redis.pubsub()
    await pubsub.subscribe(*CHANNELS)
    tasks = [
        asyncio.create_task(_forward(websocket, send_lock, pubsub)),
        asyncio.create_task(_receive(websocket, state)),
        asyncio.create_task(_ping(websocket, send_lock, state)),
        asyncio.create_task(_expire_at(expires_at)),
    ]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            task.cancel()
        await pubsub.unsubscribe(*CHANNELS)
        await pubsub.aclose()
        try:
            await websocket.close()
        except RuntimeError:
            pass
