"""The submission context and the gate runner (Phase 8 section 1).

A gate is an async function that takes the submission and returns a GateCheck. The runner calls them in
order, stops at the first failure, and records how long each one took.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.config import Settings
from app.schemas.verify import SubmissionPayload
from app.services.verification.network import RoomNetwork

logger = logging.getLogger("nightroll.verify")


@dataclass
class Submission:
    settings: Settings
    pool: asyncpg.Pool
    redis: Redis
    client_ip: str | None
    payload_bytes: bytes
    signature: str
    integrity_token: str
    integrity_error: str | None
    frames: list[bytes]
    claimed_student_id: UUID | None = None
    payload: SubmissionPayload | None = None
    payload_hash: str = ""
    device_key: bytes | None = None
    window: Any | None = None
    room: RoomNetwork | None = None
    mark_id: UUID | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class GateCheck:
    passed: bool
    code: str | None = None
    detail: str = ""
    warning: str | None = None

    @staticmethod
    def ok(warning: str | None = None) -> GateCheck:
        return GateCheck(passed=True, warning=warning)

    @staticmethod
    def fail(code: str, detail: str) -> GateCheck:
        return GateCheck(passed=False, code=code, detail=detail)


@dataclass(frozen=True)
class GateRecord:
    name: str
    passed: bool
    code: str | None
    detail: str
    ms: float


Gate = Callable[[Submission], Awaitable[GateCheck]]


async def run_gates(gates: Sequence[tuple[str, Gate]], submission: Submission) -> list[GateRecord]:
    """Run gates in order. The last record is the failure, if any; the rest passed."""
    records: list[GateRecord] = []
    for name, gate in gates:
        started = time.perf_counter()
        check = await gate(submission)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        if check.warning:
            submission.warnings.append(check.warning)
        records.append(GateRecord(name, check.passed, check.code, check.detail, elapsed_ms))
        logger.info(
            "gate %s %s in %.2f ms",
            name,
            "passed" if check.passed else f"failed ({check.code})",
            elapsed_ms,
        )
        if not check.passed:
            break
    return records
