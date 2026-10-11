"""Phase 12 network adapter contract. No database needed. Run from the backend folder:
uv run pytest ../tests/test_phase12_network.py -v
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from app.services.verification.network import (  # noqa: E402
    LocatingVerifier,
    Location,
    NetworkNotConfigured,
    NetworkUnavailable,
    RoomNetwork,
    SubnetVerifier,
    get_network_verifier,
)

ROOM = RoomNetwork(room_id="r1", subnet="192.168.101.0/24", access_point_bssids=frozenset({"aa:bb:cc:00:01:01"}))
IP = "192.168.101.20"


class FakeController(LocatingVerifier):
    def __init__(self, location: Location | None = None, error: Exception | None = None) -> None:
        self.location, self.error, self.asked = location, error, []

    def locate(self, device_identifier: str) -> Location | None:
        self.asked.append(device_identifier)
        if self.error:
            raise self.error
        return self.location


def _seen(bssid="aa:bb:cc:00:01:01", signal=-52, ago=10) -> Location:
    return Location(bssid=bssid, signal=signal, seen_at=datetime.now(UTC) - timedelta(seconds=ago))


def test_a_device_seen_recently_on_the_rooms_access_point_passes():
    controller = FakeController(_seen())
    assert controller.verify(ROOM, IP, "aa:bb:cc:00:01:01").passed
    assert controller.asked == [IP]


def test_the_comparison_ignores_letter_case_in_the_access_point_address():
    assert FakeController(_seen(bssid="AA:BB:CC:00:01:01")).verify(ROOM, IP, "x").passed


def test_a_device_on_another_rooms_access_point_fails():
    assert not FakeController(_seen(bssid="aa:bb:cc:00:02:01")).verify(ROOM, IP, "x").passed


def test_a_sighting_older_than_two_minutes_fails():
    assert FakeController(_seen(ago=119)).verify(ROOM, IP, "x").passed
    assert not FakeController(_seen(ago=121)).verify(ROOM, IP, "x").passed


def test_a_device_the_network_does_not_know_fails_and_so_does_a_missing_address():
    assert not FakeController(None).verify(ROOM, IP, "x").passed
    controller = FakeController(_seen())
    assert not controller.verify(ROOM, None, "x").passed
    assert controller.asked == []


def test_the_signal_comes_from_the_network_and_may_be_absent():
    assert FakeController(_seen(signal=-60)).measured_rssi(ROOM, IP, "x") == -60
    assert FakeController(_seen(signal=None)).measured_rssi(ROOM, IP, "x") is None
    assert FakeController(None).measured_rssi(ROOM, IP, "x") is None
    assert FakeController(_seen(ago=500)).measured_rssi(ROOM, IP, "x") is None


def test_an_unreachable_controller_is_a_503_never_a_pass():
    controller = FakeController(error=NetworkUnavailable("timed out"))
    with pytest.raises(NetworkUnavailable) as caught:
        controller.verify(ROOM, IP, "x")
    assert caught.value.status_code == 503
    assert "ground-floor scanner" in caught.value.message


def test_subnet_mode_cannot_locate_a_device():
    assert SubnetVerifier().locate(IP) is None


@pytest.mark.parametrize("mode", ["controller", "radius"])
def test_controller_and_radius_modes_refuse_and_point_to_the_contract(mode):
    verifier = get_network_verifier(mode)
    for call in (
        lambda: verifier.locate(IP),
        lambda: verifier.verify(ROOM, IP, "x"),
        lambda: verifier.measured_rssi(ROOM, IP, "x"),
    ):
        with pytest.raises(NetworkNotConfigured) as caught:
            call()
        assert caught.value.status_code == 503
        assert "docs/network-adapter.md" in caught.value.message
        assert mode in caught.value.message


def test_the_document_the_error_points_to_exists():
    assert (Path(__file__).resolve().parent.parent / "docs" / "network-adapter.md").is_file()
