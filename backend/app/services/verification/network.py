"""Gate 6: the request must come from the student's own room network (Phase 8 section 9).

The client address is the room's proof of place, so it is only ever read from the connection, or from
the forwarded-for header when the connection itself comes from a listed proxy.

`NetworkVerifier` is the contract every mode implements (docs/network-adapter.md). The subnet mode needs nothing
from the campus network. A controller or RADIUS adapter writes only `locate` and inherits the rest from
`LocatingVerifier`.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from fastapi import Request

from app.errors import AppError


@dataclass(frozen=True)
class RoomNetwork:
    room_id: str
    subnet: str | None
    access_point_bssids: frozenset[str]


@dataclass(frozen=True)
class NetworkResult:
    passed: bool
    detail: str
    warning: str | None = None


@dataclass(frozen=True)
class Location:
    """Where the campus network last saw a device."""

    bssid: str  # lower-case aa:bb:cc:dd:ee:ff, the access point the device is attached to
    signal: int | None  # the access point's own reading of the device in dBm, None if the source cannot report it
    seen_at: datetime  # timezone-aware


# A location older than this says nothing about where the phone is now.
MAX_LOCATION_AGE = timedelta(seconds=120)
ADAPTER_DOCUMENT = "docs/network-adapter.md"


class NetworkVerifier(Protocol):
    def locate(self, device_identifier: str) -> Location | None: ...

    def verify(self, room: RoomNetwork, client_ip: str | None, connected_bssid: str) -> NetworkResult: ...

    def measured_rssi(self, room: RoomNetwork, client_ip: str | None, connected_bssid: str) -> int | None: ...


class NetworkNotConfigured(AppError):
    def __init__(self, mode: str) -> None:
        super().__init__(
            code="NETWORK_UNAVAILABLE",
            status_code=503,
            message=f"Network verification mode '{mode}' is not configured on this server. See {ADAPTER_DOCUMENT}.",
        )


class NetworkUnavailable(AppError):
    """The controller or RADIUS server could not be reached. This is never a pass."""

    def __init__(self, reason: str) -> None:
        super().__init__(
            code="NETWORK_UNAVAILABLE",
            status_code=503,
            message=f"The network check is not available right now ({reason}). Use the ground-floor scanner.",
        )


class LocatingVerifier:
    """The shared rules for any mode that can say where a device is. Subclasses write only `locate`."""

    def locate(self, device_identifier: str) -> Location | None:
        raise NotImplementedError

    def _fresh_location(self, client_ip: str | None) -> Location | None:
        if client_ip is None:
            return None
        location = self.locate(client_ip)
        if location is None or datetime.now(UTC) - location.seen_at > MAX_LOCATION_AGE:
            return None
        return location

    def verify(self, room: RoomNetwork, client_ip: str | None, connected_bssid: str) -> NetworkResult:
        if client_ip is None:
            return NetworkResult(False, "client address unavailable")
        location = self._fresh_location(client_ip)
        if location is None:
            return NetworkResult(False, "the network has no recent sighting of this device")
        if location.bssid.lower() not in room.access_point_bssids:
            return NetworkResult(False, "the network places this device on another room's access point")
        return NetworkResult(True, "the network places this device on the room's access point")

    def measured_rssi(self, room: RoomNetwork, client_ip: str | None, connected_bssid: str) -> int | None:
        location = self._fresh_location(client_ip)
        return None if location is None else location.signal


class SubnetVerifier:
    """The client address must be inside the room's subnet, and the router must be one of the room's."""

    def verify(self, room: RoomNetwork, client_ip: str | None, connected_bssid: str) -> NetworkResult:
        if room.subnet is None:
            return NetworkResult(False, "room has no subnet configured")
        if client_ip is None:
            return NetworkResult(False, "client address unavailable")
        try:
            address = ipaddress.ip_address(client_ip)
            network = ipaddress.ip_network(room.subnet, strict=False)
        except ValueError:
            return NetworkResult(False, "unparseable address")
        if address not in network:
            return NetworkResult(False, "client address outside room subnet")
        if connected_bssid.lower() not in room.access_point_bssids:
            return NetworkResult(False, "connected access point is not this room's")
        return NetworkResult(True, "client address and access point match the room")

    def measured_rssi(self, room: RoomNetwork, client_ip: str | None, connected_bssid: str) -> int | None:
        """The subnet mode has no controller, so the access point never reports what it hears."""
        return None

    def locate(self, device_identifier: str) -> Location | None:
        """Subnet mode cannot see where a device is; it only judges the address the request came from."""
        return None


class _Unconfigured:
    """`controller` and `radius` until an adapter is written. Every call says so and points to the contract."""

    def __init__(self, mode: str) -> None:
        self._mode = mode

    def locate(self, device_identifier: str) -> Location | None:
        raise NetworkNotConfigured(self._mode)

    def verify(self, room: RoomNetwork, client_ip: str | None, connected_bssid: str) -> NetworkResult:
        raise NetworkNotConfigured(self._mode)

    def measured_rssi(self, room: RoomNetwork, client_ip: str | None, connected_bssid: str) -> int | None:
        raise NetworkNotConfigured(self._mode)


class _Off:
    def locate(self, device_identifier: str) -> Location | None:
        return None

    def verify(self, room: RoomNetwork, client_ip: str | None, connected_bssid: str) -> NetworkResult:
        return NetworkResult(True, "network gate disabled", warning="NETWORK_GATE_DISABLED")

    def measured_rssi(self, room: RoomNetwork, client_ip: str | None, connected_bssid: str) -> int | None:
        return None


def get_network_verifier(mode: str) -> NetworkVerifier:
    if mode == "subnet":
        return SubnetVerifier()
    if mode == "off":
        return _Off()
    return _Unconfigured(mode)


def client_address(request: Request, trusted_proxies: set[str]) -> str | None:
    """The address to test against the room subnet.

    The forwarded-for header is read only when the direct connection comes from a trusted proxy. The
    rightmost entry is the one that proxy saw, so a client cannot choose it by sending its own header.
    """
    peer = request.client.host if request.client else None
    if peer is None:
        return None
    if peer in trusted_proxies:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[-1].strip()
    return peer


def parse_trusted_proxies(raw: str) -> set[str]:
    return {item.strip() for item in raw.split(",") if item.strip()}
