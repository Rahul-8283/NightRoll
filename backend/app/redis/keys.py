from __future__ import annotations

from uuid import UUID

WINDOW_CURRENT = "window:current"
SCHEDULER_HEARTBEAT = "scheduler:heartbeat"


def nonce_key(window_id: UUID | str, student_id: UUID | str) -> str:
    return f"nonce:{window_id}:{student_id}"


def window_state_key(window_id: UUID | str) -> str:
    return f"window:{window_id}:state"


def window_lock_key(window_id: UUID | str, job: str) -> str:
    return f"lock:window:{window_id}:{job}"
