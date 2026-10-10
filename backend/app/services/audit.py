"""Write one row to the append-only audit log.

Runs inside the caller's transaction (pass the same `conn` the caller is
already using, inside its own `async with conn.transaction():` block), so an
action and its audit row succeed or fail together.
"""

from __future__ import annotations

import json
from typing import Any

import asyncpg

from app.logging import redact


async def write(
    conn: asyncpg.Connection,
    *,
    actor: str,
    action: str,
    target_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    safe_payload = redact(payload) if payload else None
    await conn.execute(
        "insert into audit_log (actor, action, target_id, payload) values ($1, $2, $3, $4::jsonb)",
        actor,
        action,
        target_id,
        json.dumps(safe_payload) if safe_payload is not None else None,
    )
