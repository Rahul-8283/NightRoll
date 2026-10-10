"""Gate 6: the request must come from the student's own room network (Phase 8 section 9).

The client address is the room's proof of place, so it is only ever read from the connection, or from
the forwarded-for header when the connection itself comes from a listed proxy.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
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


class NetworkVerifier(Protocol):
    def verify(self, room: RoomNetwork, client_ip: str | None, connected_bssid: str) -> NetworkResult: ...


class NetworkNotConfigured(AppError):
    def __init__(self, mode: str) -> None:
        super().__init__(
            code="NETWORK_UNAVAILABLE",
            status_code=503,
            message=f"Network verification mode '{mode}' is not configured on this server",
        )


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


class _Unconfigured:
    def __init__(self, mode: str) -> None:
        self._mode = mode

    def verify(self, room: RoomNetwork, client_ip: str | None, connected_bssid: str) -> NetworkResult:
        raise NetworkNotConfigured(self._mode)


class _Off:
    def verify(self, room: RoomNetwork, client_ip: str | None, connected_bssid: str) -> NetworkResult:
        return NetworkResult(True, "network gate disabled", warning="NETWORK_GATE_DISABLED")


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
