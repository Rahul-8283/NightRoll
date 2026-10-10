"""Phase 11 room health flags: the thresholds behind "Re-scan this room's Wi-Fi" and "Check the router".
Pure logic, no database. Run from the backend folder:
    uv run pytest ../tests/test_phase11_health.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from app.services.dashboard import health_flags  # noqa: E402


def _row(**overrides) -> dict:
    row = {"week_total": 0, "week_flagged": 0, "tonight_scored": 0, "tonight_ap_seen": 0}
    row.update(overrides)
    return row


def test_no_flags_for_a_healthy_room():
    assert health_flags(_row(week_total=10, week_flagged=2, tonight_scored=4, tonight_ap_seen=4)) == []


def test_wifi_flag_needs_more_than_30_percent_over_at_least_five_marks():
    assert "rescan_wifi" in health_flags(_row(week_total=10, week_flagged=4))
    assert "rescan_wifi" not in health_flags(_row(week_total=10, week_flagged=3))
    assert "rescan_wifi" not in health_flags(_row(week_total=4, week_flagged=4))


def test_router_flag_when_nobody_saw_the_room_access_point_tonight():
    assert "check_router" in health_flags(_row(tonight_scored=3, tonight_ap_seen=0))
    assert "check_router" not in health_flags(_row(tonight_scored=3, tonight_ap_seen=1))


def test_one_mark_is_not_enough_to_say_the_router_is_down():
    assert "check_router" not in health_flags(_row(tonight_scored=1, tonight_ap_seen=0))
