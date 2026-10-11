"""Runs a submission through the gates, scores it, and records the attempt (Phase 8 and Phase 9).

Order for every submission:
1. The signature gate. Nothing else is believed before it passes.
2. Idempotency: a repeat of a submission that has already been decided gets the stored response.
3. An existing PRESENT mark for this window is returned as it is.
4. Rate limit: one new submission per student per 20 seconds.
5. The remaining gates, stopping at the first failure.
6. Scoring and the verdict rules, for submissions that passed every gate.
7. The attempt is recorded, the retry rule is applied, and a mark_recorded event is published.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import asdict
from datetime import UTC, datetime

import asyncpg

from app import ratelimit
from app.db.queries import verification as verification_q
from app.errors import AppError
from app.logging import log_event, short_hash
from app.redis import keys
from app.schemas.verify import VerifyOut
from app.services import audit, nonces
from app.services.verification import gates
from app.services.verification.reasons import reason
from app.services.verification.runner import GateRecord, Submission, run_gates
from app.services.verification.scoring import score_submission

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
    submission.mark_id = uuid.uuid4()
    payload = submission.payload

    existing = await verification_q.present_mark(submission.pool, payload.window_id, payload.student_id)
    if existing is not None:
        total, rejected = await verification_q.attempt_counts(submission.pool, payload.window_id, payload.student_id)
        response = VerifyOut(
            mark_id=existing["id"],
            verdict="PRESENT",
            score=float(existing["score"]) if existing["score"] is not None else None,
            reasons=[],
            retry_allowed=False,
            attempts_left=max(0, MAX_ATTEMPTS_PER_WINDOW - rejected),
            fallback="NONE",
        )
        await _store(submission, submission_id, response, submission.window)
        return response

    rate_key = keys.submit_rate_key(payload.student_id)
    if not await submission.redis.set(rate_key, "1", nx=True, ex=RATE_LIMIT_SECONDS):
        raise ratelimit.too_many(
            max(1, await submission.redis.ttl(rate_key)),
            f"Wait {RATE_LIMIT_SECONDS} seconds between attempts.",
        )

    try:
        records = records + await run_gates(REMAINING_GATES, submission)
        if not records[-1].passed:
            return await _record(
                submission,
                submission_id,
                records,
                verdict="REJECTED",
                codes=[records[-1].code],
                score=None,
                outcome=None,
            )
        outcome = await score_submission(submission)
    except AppError:
        # Google or the face service was unavailable: nothing was decided, so the student may retry at once.
        await submission.redis.delete(rate_key)
        raise

    return await _record(
        submission,
        submission_id,
        records,
        verdict=outcome.verdict.verdict,
        codes=list(outcome.verdict.reasons),
        score=outcome.verdict.score,
        outcome=outcome,
    )


async def _record(
    submission: Submission,
    submission_id: str,
    records: list[GateRecord],
    *,
    verdict: str,
    codes: list[str],
    score: float | None,
    outcome,
) -> VerifyOut:
    payload = submission.payload
    student_id = payload.student_id
    window = submission.window
    window_id = window["id"] if window is not None else payload.window_id

    total, rejected = await verification_q.attempt_counts(submission.pool, window_id, student_id)
    rejected_after = rejected + (1 if verdict == "REJECTED" else 0)
    attempts_left = max(0, MAX_ATTEMPTS_PER_WINDOW - rejected_after)
    retry_allowed = verdict == "REJECTED" and attempts_left > 0 and window is not None

    mark_id = None
    if await verification_q.window_exists(submission.pool, window_id):
        breakdown = {
            "submission_id": submission_id,
            "gates": [asdict(record) for record in records],
            "scorers": [asdict(result) for result in outcome.scorers.values()] if outcome else [],
            "rule": outcome.verdict.rule if outcome else None,
            "warnings": submission.warnings,
            "timings_ms": outcome.timings_ms if outcome else {},
        }
        try:
            async with submission.pool.acquire() as conn:
                async with conn.transaction():
                    mark_id = await verification_q.insert_attempt(
                        conn,
                        window_id=window_id,
                        student_id=student_id,
                        verdict=verdict,
                        reasons=codes,
                        scores=json.dumps(breakdown),
                        attempt=total + 1,
                        score=score,
                        frames_path=outcome.frames_path if outcome else None,
                        mark_id=submission.mark_id,
                    )
                    await audit.write(
                        conn,
                        actor=str(student_id),
                        action="attendance.attempt",
                        target_id=str(mark_id),
                        payload={"verdict": verdict, "reasons": codes, "attempt": total + 1},
                    )
        except asyncpg.UniqueViolationError:
            # A second PRESENT in the same window: the existing mark is the answer.
            existing = await verification_q.present_mark(submission.pool, window_id, student_id)
            if existing is None:
                raise
            response = VerifyOut(
                mark_id=existing["id"],
                verdict="PRESENT",
                score=float(existing["score"]) if existing["score"] is not None else None,
                reasons=[],
                retry_allowed=False,
                attempts_left=attempts_left,
                fallback="NONE",
            )
            await _store(submission, submission_id, response, window)
            return response

    if retry_allowed:
        await nonces.reissue(submission.redis, window_id, student_id, window["closes_at"])

    if mark_id is not None:
        event = {
            "room_id": submission.room.room_id if submission.room else None,
            "verdict": verdict,
            "mark_id": str(mark_id),
        }
        await submission.redis.publish(keys.MARK_RECORDED_CHANNEL, json.dumps(event))

    log_event(
        logger,
        logging.INFO,
        "attendance attempt decided",
        student=short_hash(str(student_id)),
        verdict=verdict,
        reasons=codes,
        attempt=total + 1,
        warnings=len(submission.warnings),
        **(outcome.timings_ms if outcome else {}),
    )

    response = VerifyOut(
        mark_id=mark_id,
        verdict=verdict,
        score=score,
        reasons=[{"code": code, "message": reason(code).message} for code in codes] if verdict != "PRESENT" else [],
        retry_allowed=retry_allowed,
        attempts_left=attempts_left,
        fallback="NONE" if retry_allowed or verdict != "REJECTED" else "GROUND_FLOOR_SCANNER",
    )
    await _store(submission, submission_id, response, window)
    return response


async def _unattributed(submission: Submission, failed: GateRecord) -> VerifyOut:
    """The signature did not check out, so the sender is not proven to be any student."""
    day = datetime.now(UTC).date().isoformat()
    await ratelimit.record(
        submission.redis, "signature-failures", submission.client_ip or "unknown", ratelimit.SIGNATURE_WINDOW_SECONDS
    )
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
