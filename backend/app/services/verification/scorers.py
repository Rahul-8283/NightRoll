"""The five scorers (Phase 9 sections 2 to 6).

Each scorer takes already-verified inputs and returns a score from 0 to 1, a reason code when the signal
is weak, and a plain detail for the warden. They have no side effects and read no clock, so the same
inputs always give the same score. Every threshold comes from Settings.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from app.config import Settings


@dataclass(frozen=True)
class ScorerResult:
    name: str
    score: float
    reason: str | None
    detail: str


@dataclass(frozen=True)
class FrameMeasure:
    index: int
    tag: str
    usable: bool
    similarity: float | None
    antispoof: float | None
    yaw: float | None


@dataclass(frozen=True)
class ChallengeStep:
    action: str
    started_ms: int
    detected_ms: int


MIN_ACTION_MS = 200
MIN_SHARED_FOR_RANK = 3
MIN_STRONG_SCORE = 0.5


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _linear(value: float, low: float, high: float) -> float:
    """0 at or below `low`, 1 at or above `high`, straight line between."""
    return _clamp((value - low) / (high - low))


def face_score(frames: Iterable[FrameMeasure], settings: Settings) -> ScorerResult:
    """Only the two frames tagged neutral are matched: they face the camera."""
    neutral = [f for f in frames if f.tag == "neutral" and f.usable and f.similarity is not None]
    if not neutral:
        return ScorerResult("face", 0.0, "FACE_MISMATCH", "no usable neutral frame to match")
    best = max(f.similarity for f in neutral)
    score = _linear(best, settings.FACE_SIM_LOW, settings.FACE_SIM_HIGH)
    reason = "FACE_MISMATCH" if score == 0.0 else None
    return ScorerResult("face", round(score, 4), reason, f"best similarity {best:.3f} over {len(neutral)} frame(s)")


def liveness_score(
    challenge: Iterable[ChallengeStep],
    frames: Iterable[FrameMeasure],
    antispoof_available: bool,
    settings: Settings,
) -> ScorerResult:
    """1 only when all three checks hold: plausible timing, a real face, and the requested head turns."""
    failures: list[str] = []
    steps = list(challenge)
    frames = list(frames)

    previous_detected = None
    for step in steps:
        if step.detected_ms - step.started_ms < MIN_ACTION_MS:
            failures.append(f"{step.action} completed too quickly")
        if previous_detected is not None and step.started_ms < previous_detected:
            failures.append("challenge steps overlap")
        previous_detected = step.detected_ms

    if not antispoof_available:
        failures.append("anti-spoof model unavailable")
    else:
        live = [f.antispoof for f in frames if f.usable and f.antispoof is not None]
        median = sorted(live)[len(live) // 2] if live else 0.0
        if not live or median < settings.ANTISPOOF_MIN:
            failures.append(f"anti-spoof median {median:.2f} below {settings.ANTISPOOF_MIN}")

    for frame in frames:
        if frame.tag not in ("turn_left", "turn_right"):
            continue
        if not frame.usable or frame.yaw is None:
            failures.append(f"{frame.tag} frame shows no face")
            continue
        sign = settings.HEAD_TURN_LEFT_SIGN if frame.tag == "turn_left" else -settings.HEAD_TURN_LEFT_SIGN
        if sign * frame.yaw < settings.HEAD_TURN_MIN_DEG:
            failures.append(f"{frame.tag} frame shows yaw {frame.yaw:.1f}")

    if failures:
        return ScorerResult("liveness", 0.0, "LIVENESS_FAILED", "; ".join(failures))
    return ScorerResult("liveness", 1.0, None, "challenge timing, anti-spoof and head turns all passed")


def _ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        average = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = average
        i = j + 1
    return ranks


def _spearman(xs: list[float], ys: list[float]) -> float:
    rx, ry = _ranks(xs), _ranks(ys)
    n = len(rx)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
    vx = sum((a - mx) ** 2 for a in rx)
    vy = sum((b - my) ** 2 for b in ry)
    if vx == 0 or vy == 0:
        return 0.0
    return cov / (vx * vy) ** 0.5


def fingerprint_score(
    scan: Mapping[str, int],
    scan_age_ms: int,
    pattern: Mapping[str, Any] | None,
    scan_count: int,
    room_map_bssids: set[str],
    settings: Settings,
) -> ScorerResult:
    """How closely tonight's Wi-Fi matches the room's learned pattern. Several routers, not one."""
    if pattern is None:
        return ScorerResult("fingerprint", 0.5, "FINGERPRINT_MISSING", "this room has no Wi-Fi fingerprint yet")

    bssids = pattern.get("bssids", {})
    own = {b for b, v in bssids.items() if v.get("label") == "own"}
    own_present = 1.0 if any(b in scan for b in own) else 0.0
    if own_present == 0.0:
        return ScorerResult("fingerprint", 0.0, "WIFI_PATTERN_MISMATCH", "the room's own router was not seen")

    expected = [b for b, v in bssids.items() if v.get("label") == "hostel" and v.get("count", 0) >= scan_count / 2]
    missing = [b for b in expected if b not in scan]
    if expected:
        neighbour_ratio = (len(expected) - len(missing)) / len(expected)
    else:
        neighbour_ratio = 0.5
    neighbour_part = _linear(neighbour_ratio, settings.FP_NEIGHBOUR_LOW, settings.FP_NEIGHBOUR_HIGH)

    shared = [b for b in scan if b in bssids]
    if len(shared) < MIN_SHARED_FOR_RANK:
        rank_part = 0.5
    else:
        rho = _spearman([float(scan[b]) for b in shared], [float(bssids[b]["median_rssi"]) for b in shared])
        rank_part = max(0.0, rho)

    unknown = [b for b in scan if b not in bssids and b not in room_map_bssids]
    penalty = min(
        settings.FP_UNKNOWN_CAP,
        max(0, len(unknown) - settings.FP_UNKNOWN_FREE) * settings.FP_UNKNOWN_STEP,
    )

    score = own_present * (0.4 * neighbour_part + 0.4 * rank_part + 0.2 * (1 - penalty))
    score = _clamp(score)
    notes = [f"{len(missing)} of {len(expected)} expected neighbour(s) missing", f"{len(unknown)} unknown network(s)"]
    if scan_age_ms > settings.SCAN_STALE_MS:
        score *= 0.5
        notes.append("scan is stale, score halved")
    score = round(score, 4)
    reason = "WIFI_PATTERN_MISMATCH" if score < MIN_STRONG_SCORE else None
    return ScorerResult("fingerprint", score, reason, "; ".join(notes))


def own_ap_score(scan: Mapping[str, int], own_bssids: set[str], settings: Settings) -> ScorerResult:
    """The room's own router, at the strongest level seen tonight."""
    seen = [rssi for bssid, rssi in scan.items() if bssid in own_bssids]
    if not seen:
        return ScorerResult("own_ap", 0.0, "WIFI_PATTERN_MISMATCH", "the room's own router was not seen")
    strongest = max(seen)
    score = round(_linear(strongest, settings.OWN_AP_RSSI_LOW, settings.OWN_AP_RSSI_HIGH), 4)
    reason = "WIFI_PATTERN_MISMATCH" if score < MIN_STRONG_SCORE else None
    return ScorerResult("own_ap", score, reason, f"strongest own router at {strongest} dBm")


def ap_agreement_score(measured_by_ap: int | None, phone_rssi: int, settings: Settings) -> ScorerResult:
    """The router's own reading of the phone, compared with the phone's report. Unavailable in subnet mode."""
    if measured_by_ap is None:
        return ScorerResult("ap_agreement", 0.5, "AP_UNAVAILABLE", "no access point reading for this network mode")
    difference = abs(measured_by_ap - phone_rssi)
    score = round(1 - _linear(difference, settings.AP_AGREEMENT_FULL_DB, settings.AP_AGREEMENT_ZERO_DB), 4)
    reason = "WIFI_PATTERN_MISMATCH" if score < MIN_STRONG_SCORE else None
    return ScorerResult("ap_agreement", score, reason, f"access point and phone differ by {difference} dB")
