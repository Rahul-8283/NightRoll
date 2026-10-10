"""Runs a submission through the gates and records the attempt (Phase 8 sections 2, 11, 12 and 13).

Order for every submission:
1. The signature gate. Nothing else is believed before it passes.
2. Idempotency: a repeat of a submission that has already been decided gets the stored response.
3. Rate limit: one new submission per student per 20 seconds.
4. The remaining gates, stopping at the first failure.
5. The attempt is recorded, and a retry is prepared if the rules allow one.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict
from datetime import UTC, datetime

from app.db.queries import verification as verification_q
from app.errors import AppError
from app.logging import log_event, short_hash
from app.redis import keys
from app.schemas.verify import VerifyOut
from app.services import audit, nonces
from app.services.verification import gates
from app.services.verification.reasons import reason
from app.services.verification.runner import GateRecord, Submission, run_gates

logger = logging.getLogger("nightroll.verify")

MAX_ATTEMPTS_PER_WINDOW = 3
RATE_LIMIT_SECONDS = 20
LOCK_SECONDS = 30
WAIT_FOR_CONCURRENT_SECONDS = 5.0
UNKNOWN_WINDOW_TTL_SECONDS = 86400

SIGNATURE_GATES = [("signature", gates.signature_gate)]
REMAINING_GATES = [
    ("window", gates.window_gate),
    ("nonce", gates.nonce_gate),
    ("integrity", gates.integrity_gate),
    ("environment", gates.environment_gate),
    ("network", gates.network_gate),
]


async def submit(submission: Submission) -> VerifyOut:
    records = await run_gates(SIGNATURE_GATES, submission)
    if not records[-1].passed:
        return await _unattributed(submission, records[-1])

    submission_id = submission.payload_hash
    stored = await _stored(submission, submission_id)
    if stored is not None:
        return stored

    if not await submission.redis.set(keys.submission_lock_key(submission_id), "1", nx=True, ex=LOCK_SECONDS):
        concurrent = await _wait_for_stored(submission, submission_id)
        if concurrent is None:
            raise AppError(
                code="SUBMISSION_IN_PROGRESS",
                status_code=409,
                message="This submission is still being checked. Wait a moment and try again.",
            )
        return concurrent

    try:
        stored = await _stored(submission, submission_id)
        if stored is not None:
            return stored
        return await _decide_new(submission, submission_id, records)
    finally:
        await submission.redis.delete(keys.submission_lock_key(submission_id))


async def _decide_new(submission: Submission, submission_id: str, records: list[GateRecord]) -> VerifyOut:
    rate_key = keys.submit_rate_key(submission.payload.student_id)
    if not await submission.redis.set(rate_key, "1", nx=True, ex=RATE_LIMIT_SECONDS):
        raise AppError(
            code="RATE_LIMITED",
            status_code=429,
            message=f"Wait {RATE_LIMIT_SECONDS} seconds between attempts.",
        )

    try:
        records = records + await run_gates(REMAINING_GATES, submission)
    except AppError:
        # Google or its credentials were unavailable: nothing was decided, so the student may retry at once.
        await submission.redis.delete(rate_key)
        raise

    return await _record_and_respond(submission, submission_id, records)


async def _record_and_respond(submission: Submission, submission_id: str, records: list[GateRecord]) -> VerifyOut:
    payload = submission.payload
    student_id = payload.student_id
    window = submission.window
    window_id = window["id"] if window is not None else payload.window_id
    failed = records[-1] if not records[-1].passed else None

    if failed is None:
        verdict = "NEEDS_REVIEW"
        reasons = [reason("SCORING_PENDING")]
    else:
        verdict = "REJECTED"
        reasons = [reason(failed.code)]

    total, rejected = await verification_q.attempt_counts(submission.pool, window_id, student_id)
    rejected_after = rejected + (1 if verdict == "REJECTED" else 0)
    attempts_left = max(0, MAX_ATTEMPTS_PER_WINDOW - rejected_after)
    retry_allowed = verdict == "REJECTED" and attempts_left > 0 and window is not None

    mark_id = None
    if await verification_q.window_exists(submission.pool, window_id):
        scores = json.dumps(
            {
                "submission_id": submission_id,
                "gates": [asdict(record) for record in records],
                "warnings": submission.warnings,
            }
        )
        async with submission.pool.acquire() as conn:
            async with conn.transaction():
                mark_id = await verification_q.insert_attempt(
                    conn,
                    window_id=window_id,
                    student_id=student_id,
                    verdict=verdict,
                    reasons=[r.code for r in reasons],
                    scores=scores,
                    attempt=total + 1,
                )
                await audit.write(
                    conn,
                    actor=str(student_id),
                    action="attendance.attempt",
                    target_id=str(mark_id),
                    payload={"verdict": verdict, "reason": reasons[0].code, "attempt": total + 1},
                )

    if retry_allowed:
        await nonces.reissue(submission.redis, window_id, student_id, window["closes_at"])

    log_event(
        logger,
        logging.INFO,
        "attendance attempt decided",
        student=short_hash(str(student_id)),
        verdict=verdict,
        reason=reasons[0].code,
        attempt=total + 1,
        warnings=len(submission.warnings),
    )

    response = VerifyOut(
        mark_id=mark_id,
        verdict=verdict,
        score=None,
        reasons=[{"code": r.code, "message": r.message} for r in reasons],
        retry_allowed=retry_allowed,
        attempts_left=attempts_left if verdict == "REJECTED" else MAX_ATTEMPTS_PER_WINDOW - rejected,
        fallback="NONE" if retry_allowed or verdict != "REJECTED" else "GROUND_FLOOR_SCANNER",
    )
    await _store(submission, submission_id, response, window)
    return response


async def _unattributed(submission: Submission, failed: GateRecord) -> VerifyOut:
    """The signature did not check out, so the sender is not proven to be any student."""
    day = datetime.now(UTC).date().isoformat()
    await submission.redis.incr(keys.unattributed_counter_key(day))
    await submission.redis.expire(keys.unattributed_counter_key(day), 2 * 86400)
    logger.warning(
        "unattributed attendance attempt",
        extra={"extra_fields": {"client": submission.client_ip, "gate": failed.name, "code": failed.code}},
    )
    return VerifyOut(
        mark_id=None,
        verdict="REJECTED",
        score=None,
        reasons=[{"code": r.code, "message": r.message} for r in [reason(failed.code)]],
        retry_allowed=False,
        attempts_left=0,
        fallback="GROUND_FLOOR_SCANNER",
    )


async def _stored(submission: Submission, submission_id: str) -> VerifyOut | None:
    raw = await submission.redis.get(keys.submission_key(submission_id))
    return VerifyOut.model_validate_json(raw) if raw else None


async def _wait_for_stored(submission: Submission, submission_id: str) -> VerifyOut | None:
    deadline = asyncio.get_running_loop().time() + WAIT_FOR_CONCURRENT_SECONDS
    while asyncio.get_running_loop().time() < deadline:
        await asyncio.sleep(0.2)
        stored = await _stored(submission, submission_id)
        if stored is not None:
            return stored
    return None


async def _store(submission: Submission, submission_id: str, response: VerifyOut, window) -> None:
    ttl = UNKNOWN_WINDOW_TTL_SECONDS
    if window is not None:
        remaining = int((window["closes_at"] - datetime.now(UTC)).total_seconds())
        ttl = max(60, remaining)
    await submission.redis.set(keys.submission_key(submission_id), response.model_dump_json(), ex=ttl)
