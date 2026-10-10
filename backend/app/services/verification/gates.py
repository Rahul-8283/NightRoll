"""The six hard gates, in the order they run (Phase 8 section 3).

Each gate reads what earlier gates have already proven and returns a GateCheck. Adding a gate means
adding one function here and one line in ORDERED_GATES.
"""

from __future__ import annotations

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
