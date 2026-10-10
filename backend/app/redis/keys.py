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


def submission_key(submission_id: str) -> str:
    return f"submission:{submission_id}"


def submission_lock_key(submission_id: str) -> str:
    return f"submission:lock:{submission_id}"


def submit_rate_key(student_id: UUID | str) -> str:
    return f"ratelimit:submit:{student_id}"


def unattributed_counter_key(day: str) -> str:
    return f"verify:unattributed:{day}"


MARK_RECORDED_CHANNEL = "attendance:mark_recorded"
