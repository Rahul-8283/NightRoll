"""Reason codes and the plain sentence shown to the student for each.

The messages never say which subnet, router, or threshold was expected. A code that is not in this
table is a programming error and is rejected at import time, so the set stays fixed.
"""

from __future__ import annotations

from dataclasses import dataclass

GATE_FAILURE_CODES = (
    "DEVICE_NOT_ENROLLED",
    "SIGNATURE_INVALID",
    "PAYLOAD_INVALID",
    "OUTSIDE_WINDOW",
    "NONCE_INVALID",
    "INTEGRITY_FAILED",
    "ENVIRONMENT_FLAGGED",
    "NETWORK_MISMATCH",
)

# Reserved for the scoring phase; never produced by a gate.
SCORING_CODES = ("SCORING_PENDING",)

_MESSAGES: dict[str, str] = {
    "DEVICE_NOT_ENROLLED": "This phone is not registered for your attendance. Use the ground-floor scanner.",
    "SIGNATURE_INVALID": "We could not verify this phone. Try again, or use the ground-floor scanner.",
    "PAYLOAD_INVALID": "Your phone sent an incomplete request. Update the app and try again.",
    "OUTSIDE_WINDOW": "Attendance is not open right now.",
    "NONCE_INVALID": "This check has expired or was already used. Try again.",
    "INTEGRITY_FAILED": "This phone or app could not be verified. Use the ground-floor scanner.",
    "ENVIRONMENT_FLAGGED": "Turn off your VPN, proxy and mock location, then try again.",
    "NETWORK_MISMATCH": "Request did not come from your room network.",
    "SCORING_PENDING": "Your attendance is waiting to be checked.",
}


@dataclass(frozen=True)
class Reason:
    code: str
    message: str


def reason(code: str) -> Reason:
    return Reason(code=code, message=_MESSAGES[code])


for _code in GATE_FAILURE_CODES + SCORING_CODES:
    assert _code in _MESSAGES, f"missing message for reason code {_code}"
