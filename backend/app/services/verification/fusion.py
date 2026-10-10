"""Fusion and verdict rules (Phase 9 sections 7 and 8).

The weighted sum is not enough on its own: a strong Wi-Fi match must not carry a face that does not
match. So two floors run first, then the cutoffs.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings
from app.services.verification.scorers import ScorerResult


@dataclass(frozen=True)
class Verdict:
    verdict: str
    score: float
    reasons: tuple[str, ...]
    rule: str


def fuse(results: dict[str, ScorerResult], settings: Settings) -> Verdict:
    weights = {
        "face": settings.WEIGHT_FACE,
        "fingerprint": settings.WEIGHT_FINGERPRINT,
        "liveness": settings.WEIGHT_LIVENESS,
        "own_ap": settings.WEIGHT_OWN_AP,
        "ap_agreement": settings.WEIGHT_AP_AGREEMENT,
    }
    score = round(sum(weights[name] * results[name].score for name in weights), 3)

    if results["face"].score == 0.0:
        return Verdict("REJECTED", score, ("FACE_MISMATCH",), "face floor")
    if results["liveness"].score == 0.0:
        return Verdict("REJECTED", score, ("LIVENESS_FAILED",), "liveness floor")

    reasons = tuple(result.reason for result in results.values() if result.reason)

    # A room with no learned Wi-Fi pattern cannot be confirmed by the Wi-Fi signals, so it goes to review
    # rather than being presented as confirmed (Phase 9 task 4.1).
    if score >= settings.THRESHOLD_PRESENT and "FINGERPRINT_MISSING" not in reasons:
        return Verdict("PRESENT", score, (), "present cutoff")
    if score >= settings.THRESHOLD_PRESENT:
        return Verdict("NEEDS_REVIEW", score, reasons, "no room fingerprint, review cap")
    if score >= settings.THRESHOLD_REVIEW:
        return Verdict("NEEDS_REVIEW", score, reasons, "review cutoff")

    lowest = min(results.values(), key=lambda result: result.score)
    causes = ("LOW_SCORE", lowest.reason) if lowest.reason else ("LOW_SCORE",)
    return Verdict("REJECTED", score, causes, "below review cutoff")
