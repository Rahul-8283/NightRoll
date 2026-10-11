# Network adapter contract

NightRoll's network gate asks one question: **is this phone really in its own room?** The demo and the first pilot answer it with the *subnet check*, which needs nothing from the campus network. This document describes what a *controller adapter* or a *RADIUS adapter* must provide to replace it, and what the campus network administrator has to supply. Neither adapter is built. Both modes (`NETWORK_VERIFY_MODE=controller` and `radius`) refuse to run and point here.

## The four modes

| `NETWORK_VERIFY_MODE` | Source of truth | Status |
|---|---|---|
| `subnet` | The phone's source address must be inside the room's subnet, and the router it reports must be one of the room's. | Built. Used for the demo and the first pilot. |
| `controller` | The campus Wi-Fi controller says which access point the phone is on and how strong the signal is. | Contract only. |
| `radius` | RADIUS accounting says which access point the phone is on. | Contract only. |
| `off` | Nothing is checked. | Local development and the relaxed demo only. The API refuses it when `APP_ENV` is `pilot` or `production`. |

## The interface

An adapter implements `NetworkVerifier` (`backend/app/services/verification/network.py`):

```python
class NetworkVerifier(Protocol):
    def locate(self, device_identifier: str) -> Location | None: ...
    def verify(self, room: RoomNetwork, client_ip: str | None, connected_bssid: str) -> NetworkResult: ...
    def measured_rssi(self, room: RoomNetwork, client_ip: str | None, connected_bssid: str) -> int | None: ...
```

`locate` is the only method a controller or RADIUS adapter writes by hand. `LocatingVerifier` builds `verify` and `measured_rssi` on top of it, so every adapter judges a location the same way.

### `locate(device_identifier) -> Location | None`

| Part | Meaning |
|---|---|
| `device_identifier` | The phone's address as the **server** saw it: the connection address, or the forwarded-for address when the connection comes from a trusted proxy. It is never taken from the request body. |
| returns `Location` | `bssid`: the access point the phone is attached to, lower-case `aa:bb:cc:dd:ee:ff`. `signal`: the access point's own reading of the phone's signal in dBm, or `None` when the source cannot report it. `seen_at`: when the network last saw the phone, timezone-aware. |
| returns `None` | The network does not know this device. This is "not found", and the gate fails with `NETWORK_MISMATCH`. |
| raises | Any error reaching the controller or RADIUS server is raised as `NetworkUnavailable`. The gate then answers 503 and the student is pointed to the ground-floor scanner. **An error is never a pass.** |

The calls are synchronous and short. Each must finish in about 2 seconds, because a student is waiting. An adapter that needs a slow query should keep a cache of recent sightings and answer from it.

### How a location is judged

`LocatingVerifier.verify` passes only when all of these hold:

1. `locate` found the device.
2. `seen_at` is no more than **120 seconds** old.
3. `bssid` is one of the room's registered access points (`access_points` table).

`measured_rssi` returns `signal` under the same freshness rule. The scorer for "access point agrees with the phone" compares it with what the phone reported. A `None` signal gives `AP_UNAVAILABLE` and sends the attempt to the warden, instead of failing the student.

## What a controller adapter needs

The controller (Cisco, Aruba, Ruckus, UniFi, Meraki and similar) must be able to answer "which access point is the client with this IP address on, and how strong is it?".

The network administrator provides:

| Item | Why |
|---|---|
| The controller's API address, reachable from the NightRoll server | The adapter calls it. |
| A **read-only** account or API token | The adapter only reads client lists. It must not be able to change anything. |
| The name of the call that lists connected clients, with the fields for client IP, access point MAC (BSSID), signal strength and last-seen time | These are the three parts of `Location`. |
| Whether client MAC addresses are randomised on the hostel Wi-Fi | Phones randomise by default. The adapter must look clients up by IP address, which the server knows for certain. |
| The controller's call rate limit | The adapter caches to stay under it. |
| A certificate for the controller's HTTPS endpoint, or its certificate authority | The adapter verifies TLS and never turns verification off. |
| The access point MAC (BSSID) of every router, per room | These fill `config/rooms.local.json`. For controllers that report one MAC per radio, list every one. |

## What a RADIUS adapter needs

RADIUS accounting tells the server when a phone connects and how long it stays. It does not usually report signal strength.

The network administrator provides:

| Item | Why |
|---|---|
| Accounting packets forwarded to the NightRoll server, or a log or API that exposes them | The adapter reads them. |
| `Framed-IP-Address` in accounting records | This is the `device_identifier`. |
| `Called-Station-Id` in accounting records | This carries the access point's BSSID. |
| Interim accounting updates at an interval of 60 seconds or less | `seen_at` comes from the most recent record. A phone that connected an hour ago and sent no update is not fresh. |
| A shared secret exchanged through a secure channel | Never put in the repository. |

`signal` is `None` for a RADIUS adapter unless the vendor adds a signal attribute. The access point check still works; the signal-agreement score does not.

## What every adapter must do

- Take its address, credentials and certificate paths from environment variables or files that are not committed. Never hard-code hostel network details (CLAUDE.md).
- Never log credentials, tokens, or full client lists.
- Fail closed: an unreachable controller is `NetworkUnavailable`, not a pass.
- Return `None` for an unknown device instead of guessing from a neighbouring record.
- Come with tests that run against a recorded sample response, so the gate can be tested without the campus network.

## Switching a mode on

1. Write the adapter class and register it in `get_network_verifier`.
2. Put its settings in `backend/.env` and list them in `backend/.env.example`.
3. Set `NETWORK_VERIFY_MODE` to the new mode.
4. Walk the demo from the README with the phone inside the room, in the next room, and outside, and check each gate result in the attempt's detail view.

Until step 1 exists, setting `NETWORK_VERIFY_MODE=controller` or `radius` makes every verify request fail with `NETWORK_UNAVAILABLE` and a message pointing to this file.
