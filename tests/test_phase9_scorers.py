"""Phase 9 scorers and fusion on recorded inputs. No database, Redis or face worker needed.

Run from the backend folder:
    uv run pytest ../tests/test_phase9_scorers.py -q
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from app.config import get_settings  # noqa: E402
from app.services.verification import scorers  # noqa: E402
from app.services.verification.fusion import fuse  # noqa: E402
from app.services.verification.scorers import ChallengeStep, FrameMeasure, ScorerResult  # noqa: E402

S = get_settings()
OWN = "aa:bb:cc:00:01:01"
OWN2 = "aa:bb:cc:00:01:05"
NEIGHBOUR = "aa:bb:cc:00:02:01"
NEIGHBOUR2 = "aa:bb:cc:00:02:05"
ROOM_MAP = {OWN, OWN2, NEIGHBOUR, NEIGHBOUR2}


def frame(index, tag="neutral", usable=True, similarity=0.99, antispoof=0.99, yaw=0.0):
    return FrameMeasure(index=index, tag=tag, usable=usable, similarity=similarity, antispoof=antispoof, yaw=yaw)


def pattern(scans_count=3):
    return {
        "scans_count": scans_count,
        "bssids": {
            OWN: {"median_rssi": -48.0, "band": "5GHz", "count": 3, "label": "own"},
            OWN2: {"median_rssi": -50.0, "band": "2.4GHz", "count": 3, "label": "own"},
            NEIGHBOUR: {"median_rssi": -70.0, "band": "5GHz", "count": 3, "label": "hostel"},
            NEIGHBOUR2: {"median_rssi": -78.0, "band": "2.4GHz", "count": 3, "label": "hostel"},
        },
    }


# --- face ---------------------------------------------------------------------------------------


def test_face_similarity_maps_linearly_between_the_floors():
    low = scorers.face_score([frame(0, similarity=S.FACE_SIM_LOW)], S)
    high = scorers.face_score([frame(0, similarity=S.FACE_SIM_HIGH)], S)
    middle = scorers.face_score([frame(0, similarity=(S.FACE_SIM_LOW + S.FACE_SIM_HIGH) / 2)], S)
    assert low.score == 0.0 and low.reason == "FACE_MISMATCH"
    assert high.score == 1.0 and high.reason is None
    assert abs(middle.score - 0.5) < 1e-6


def test_face_only_matches_neutral_frames():
    action_only = scorers.face_score([frame(0, tag="blink", similarity=0.99)], S)
    assert action_only.score == 0.0 and action_only.reason == "FACE_MISMATCH"


def test_face_with_no_usable_frame_is_a_mismatch():
    assert scorers.face_score([frame(0, usable=False, similarity=None)], S).reason == "FACE_MISMATCH"


# --- liveness -----------------------------------------------------------------------------------


def _steps(*actions):
    return [ChallengeStep(a, i * 1500, i * 1500 + 900) for i, a in enumerate(actions)]


def test_liveness_passes_for_plausible_timing_and_real_faces():
    result = scorers.liveness_score(_steps("blink", "smile"), [frame(0, tag="blink"), frame(1, tag="neutral")], True, S)
    assert result.score == 1.0 and result.reason is None


def test_liveness_fails_for_an_action_completed_too_quickly():
    steps = [ChallengeStep("blink", 0, 120), ChallengeStep("smile", 1500, 2400)]
    result = scorers.liveness_score(steps, [frame(0)], True, S)
    assert result.score == 0.0 and result.reason == "LIVENESS_FAILED" and "too quickly" in result.detail


def test_liveness_fails_when_anti_spoof_is_below_the_minimum():
    result = scorers.liveness_score(_steps("blink", "smile"), [frame(0, antispoof=0.5)], True, S)
    assert result.reason == "LIVENESS_FAILED"


def test_liveness_fails_when_anti_spoof_is_unavailable():
    result = scorers.liveness_score(_steps("blink", "smile"), [frame(0)], False, S)
    assert result.score == 0.0 and "unavailable" in result.detail


def test_liveness_requires_the_head_turn_in_the_right_direction():
    left_ok = [frame(0, tag="turn_left", yaw=S.HEAD_TURN_LEFT_SIGN * abs(S.HEAD_TURN_MIN_DEG + 5))]
    right_ok = [frame(1, tag="turn_right", yaw=-S.HEAD_TURN_LEFT_SIGN * abs(S.HEAD_TURN_MIN_DEG + 5))]
    assert scorers.liveness_score(_steps("turn_left", "turn_right"), left_ok + right_ok, True, S).score == 1.0

    wrong_way = [frame(0, tag="turn_left", yaw=-S.HEAD_TURN_LEFT_SIGN * abs(S.HEAD_TURN_MIN_DEG + 5))]
    assert scorers.liveness_score(_steps("turn_left", "blink"), wrong_way, True, S).score == 0.0

    too_small = [frame(0, tag="turn_left", yaw=S.HEAD_TURN_LEFT_SIGN * 2.0)]
    assert scorers.liveness_score(_steps("turn_left", "blink"), too_small, True, S).score == 0.0


# --- fingerprint --------------------------------------------------------------------------------


def test_fingerprint_missing_gives_a_neutral_half_with_review_reason():
    result = scorers.fingerprint_score({OWN: -50}, 0, None, 0, ROOM_MAP, S)
    assert result.score == 0.5 and result.reason == "FINGERPRINT_MISSING"


def test_fingerprint_is_zero_without_the_rooms_own_router():
    result = scorers.fingerprint_score({NEIGHBOUR: -70}, 0, pattern(), 3, ROOM_MAP, S)
    assert result.score == 0.0 and result.reason == "WIFI_PATTERN_MISMATCH"


def test_fingerprint_is_high_inside_and_low_outside():
    inside = {OWN: -48, OWN2: -50, NEIGHBOUR: -70, NEIGHBOUR2: -78}
    outside = {NEIGHBOUR: -92, "de:ad:be:ef:00:01": -60, "de:ad:be:ef:00:02": -66, "de:ad:be:ef:00:03": -70}
    inside_score = scorers.fingerprint_score(inside, 0, pattern(), 3, ROOM_MAP, S).score
    outside_score = scorers.fingerprint_score(outside, 0, pattern(), 3, ROOM_MAP, S).score
    assert inside_score > 0.8
    assert outside_score < inside_score


def test_stale_scan_halves_the_fingerprint_score():
    scan = {OWN: -48, OWN2: -50, NEIGHBOUR: -70, NEIGHBOUR2: -78}
    fresh = scorers.fingerprint_score(scan, 0, pattern(), 3, ROOM_MAP, S).score
    stale = scorers.fingerprint_score(scan, S.SCAN_STALE_MS + 1, pattern(), 3, ROOM_MAP, S)
    assert abs(stale.score - fresh * 0.5) < 1e-3
    assert "stale" in stale.detail


def test_rank_agreement_is_perfect_when_the_order_matches():
    assert abs(scorers._spearman([1.0, 2.0, 3.0, 4.0], [10.0, 20.0, 30.0, 40.0]) - 1.0) < 1e-9
    assert scorers._spearman([1.0, 2.0, 3.0], [30.0, 20.0, 10.0]) == -1.0


def test_ties_share_their_average_rank():
    assert scorers._ranks([5.0, 5.0, 1.0]) == [2.5, 2.5, 1.0]


# --- own router and access point agreement ------------------------------------------------------


def test_own_router_maps_between_its_floors():
    assert scorers.own_ap_score({OWN: S.OWN_AP_RSSI_HIGH}, {OWN}, S).score == 1.0
    assert scorers.own_ap_score({OWN: S.OWN_AP_RSSI_LOW}, {OWN}, S).score == 0.0
    assert scorers.own_ap_score({NEIGHBOUR: -40}, {OWN}, S).score == 0.0


def test_access_point_agreement_within_ten_db_is_full_marks():
    assert scorers.ap_agreement_score(-50, -55, S).score == 1.0
    assert scorers.ap_agreement_score(-50, -90, S).score == 0.0


def test_access_point_agreement_is_neutral_without_a_reading():
    result = scorers.ap_agreement_score(None, -55, S)
    assert result.score == 0.5 and result.reason == "AP_UNAVAILABLE"


# --- fusion -------------------------------------------------------------------------------------


def _results(**overrides):
    base = {
        "face": ScorerResult("face", 1.0, None, ""),
        "liveness": ScorerResult("liveness", 1.0, None, ""),
        "fingerprint": ScorerResult("fingerprint", 0.9, None, ""),
        "own_ap": ScorerResult("own_ap", 1.0, None, ""),
        "ap_agreement": ScorerResult("ap_agreement", 0.5, "AP_UNAVAILABLE", ""),
    }
    base.update(overrides)
    return base


def test_a_strong_match_is_present():
    verdict = fuse(_results(), S)
    assert verdict.verdict == "PRESENT" and verdict.reasons == ()


def test_a_zero_face_is_rejected_even_with_perfect_wifi():
    verdict = fuse(_results(face=ScorerResult("face", 0.0, "FACE_MISMATCH", "")), S)
    assert verdict.verdict == "REJECTED" and verdict.reasons == ("FACE_MISMATCH",)


def test_a_zero_liveness_is_rejected_even_with_perfect_wifi():
    verdict = fuse(_results(liveness=ScorerResult("liveness", 0.0, "LIVENESS_FAILED", "")), S)
    assert verdict.verdict == "REJECTED" and verdict.reasons == ("LIVENESS_FAILED",)


def test_a_room_without_a_fingerprint_is_capped_at_review():
    verdict = fuse(_results(fingerprint=ScorerResult("fingerprint", 0.5, "FINGERPRINT_MISSING", "")), S)
    assert verdict.verdict == "NEEDS_REVIEW"
    assert "FINGERPRINT_MISSING" in verdict.reasons


def test_low_total_is_rejected_with_the_lowest_scorer_reason():
    verdict = fuse(
        _results(
            fingerprint=ScorerResult("fingerprint", 0.0, "WIFI_PATTERN_MISMATCH", ""),
            own_ap=ScorerResult("own_ap", 0.0, "WIFI_PATTERN_MISMATCH", ""),
        ),
        S,
    )
    assert verdict.verdict == "REJECTED"
    assert verdict.reasons[0] == "LOW_SCORE" and verdict.reasons[1] == "WIFI_PATTERN_MISMATCH"


def test_cutoffs_come_from_settings_not_code():
    strict = S.model_copy(update={"THRESHOLD_PRESENT": 0.999})
    assert fuse(_results(), strict).verdict == "NEEDS_REVIEW"
