"""Play Integrity: decoding the phone's token through Google (Phase 8 section 7).

Two outcomes are kept apart on purpose:
- The token is decoded and its verdict is wrong: a failure, which may be a warning if enforcement is off.
- Google, or our credentials for it, is unavailable: a 503. This never passes the gate.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
import jwt

from app.config import Settings
from app.errors import AppError

TOKEN_URI_DEFAULT = "https://oauth2.googleapis.com/token"
DECODE_URL = "https://playintegrity.googleapis.com/v1/{package}:decodeIntegrityToken"
SCOPE = "https://www.googleapis.com/auth/playintegrity"
MAX_TOKEN_AGE_MS = 2 * 60 * 1000
TIMEOUT_SECONDS = 10.0

# Test seam: tests replace this with an httpx.MockTransport. Never set in production code.
TRANSPORT: httpx.AsyncBaseTransport | None = None


class IntegrityUnavailable(AppError):
    def __init__(self, reason: str) -> None:
        super().__init__(
            code="INTEGRITY_UNAVAILABLE",
            status_code=503,
            message=f"Could not check the app with Google right now ({reason}). Use the ground-floor scanner.",
        )


@dataclass(frozen=True)
class DecodedVerdict:
    package_name: str
    request_hash: str
    timestamp_ms: int
    app_verdict: str
    device_verdicts: tuple[str, ...]


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=TIMEOUT_SECONDS, transport=TRANSPORT)


def _service_account(settings: Settings) -> dict:
    try:
        return json.loads(Path(settings.GOOGLE_APPLICATION_CREDENTIALS).read_text())
    except (OSError, ValueError) as exc:
        raise IntegrityUnavailable("service account file is missing or unreadable") from exc


async def _access_token(account: dict) -> str:
    now = int(time.time())
    assertion = jwt.encode(
        {
            "iss": account["client_email"],
            "scope": SCOPE,
            "aud": account.get("token_uri", TOKEN_URI_DEFAULT),
            "iat": now,
            "exp": now + 3600,
        },
        account["private_key"],
        algorithm="RS256",
    )
    try:
        async with _client() as client:
            resp = await client.post(
                account.get("token_uri", TOKEN_URI_DEFAULT),
                data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion},
            )
    except httpx.HTTPError as exc:
        raise IntegrityUnavailable("Google's sign-in service is unreachable") from exc
    if resp.status_code != 200:
        raise IntegrityUnavailable(f"sign-in with the service account failed: HTTP {resp.status_code}")
    return resp.json()["access_token"]


async def decode_token(settings: Settings, token: str) -> DecodedVerdict | None:
    """Return the verdict, or None if Google says the token itself is not valid."""
    account = _service_account(settings)
    access_token = await _access_token(account)
    url = DECODE_URL.format(package=settings.PLAY_INTEGRITY_PACKAGE_NAME)
    try:
        async with _client() as client:
            resp = await client.post(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
                json={"integrityToken": token},
            )
    except httpx.HTTPError as exc:
        raise IntegrityUnavailable("Google's integrity service is unreachable") from exc

    if resp.status_code == 400:
        return None
    if resp.status_code != 200:
        raise IntegrityUnavailable(f"integrity service returned HTTP {resp.status_code}")

    body = resp.json()["tokenPayloadExternal"]
    request_details = body.get("requestDetails", {})
    app_integrity = body.get("appIntegrity", {})
    device_integrity = body.get("deviceIntegrity", {})
    return DecodedVerdict(
        package_name=app_integrity.get("packageName", ""),
        request_hash=request_details.get("requestHash", ""),
        timestamp_ms=int(request_details.get("timestampMillis", 0)),
        app_verdict=app_integrity.get("appRecognitionVerdict", "UNEVALUATED"),
        device_verdicts=tuple(device_integrity.get("deviceRecognitionVerdict", [])),
    )


def check_verdict(
    verdict: DecodedVerdict,
    *,
    expected_package: str,
    payload_hash: str,
    now_ms: int,
) -> tuple[str | None, str | None]:
    """Return (failure detail, warning). A failure means the token does not prove this request."""
    if verdict.package_name != expected_package:
        return "token is for a different app", None
    if verdict.request_hash.lower() != payload_hash.lower():
        return "token is not bound to this payload", None
    if abs(now_ms - verdict.timestamp_ms) > MAX_TOKEN_AGE_MS:
        return "token is older than 2 minutes", None
    if "MEETS_DEVICE_INTEGRITY" not in verdict.device_verdicts:
        return "device does not meet device integrity", None
    # Phase 0 spike 11.2 (directly installed builds) has not been run. Until it is, an app that is not
    # recognised by Play is recorded as a warning, not a rejection.
    warning = None if verdict.app_verdict == "PLAY_RECOGNIZED" else f"app verdict {verdict.app_verdict}"
    return None, warning
