"""The six hard gates, in the order they run (Phase 8 section 3).

Each gate reads what earlier gates have already proven and returns a GateCheck. Adding a gate means
adding one function here and one line in ORDERED_GATES.
"""

from __future__ import annotations

import time

from app.services.verification import integrity
from app.services.verification.runner import GateCheck, Submission


async def environment_gate(submission: Submission) -> GateCheck:
    """Gate 5: the phone's own report. Supporting evidence only; the network gate is the real block."""
    env = submission.payload.environment
    flags = [
        name for name, bad in (("vpn", env.vpn), ("proxy", env.proxy), ("mock_location", env.mock_location)) if bad
    ]
    if not env.on_wifi:
        flags.append("not_on_wifi")
    if flags:
        return GateCheck.fail("ENVIRONMENT_FLAGGED", f"flagged: {', '.join(flags)}")
    return GateCheck.ok()


def _integrity_failure(submission: Submission, detail: str) -> GateCheck:
    if submission.settings.PLAY_INTEGRITY_ENFORCE:
        return GateCheck.fail("INTEGRITY_FAILED", detail)
    return GateCheck.ok(warning=f"INTEGRITY_NOT_ENFORCED: {detail}")


async def integrity_gate(submission: Submission) -> GateCheck:
    """Gate 4: the token is genuine, for this app, and bound to this exact payload.

    An unreachable Google raises IntegrityUnavailable, which becomes a 503. It never passes the gate.
    """
    if submission.integrity_error or not submission.integrity_token:
        return _integrity_failure(submission, f"no token ({submission.integrity_error or 'missing'})")

    verdict = await integrity.decode_token(submission.settings, submission.integrity_token)
    if verdict is None:
        return _integrity_failure(submission, "Google rejected the token")

    detail, warning = integrity.check_verdict(
        verdict,
        expected_package=submission.settings.PLAY_INTEGRITY_PACKAGE_NAME,
        payload_hash=submission.payload_hash,
        now_ms=int(time.time() * 1000),
    )
    if detail:
        return _integrity_failure(submission, detail)
    return GateCheck.ok(warning=warning)
