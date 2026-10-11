"""Phase 8 exit criteria, run against the real database and Redis.

Google's Play Integrity service is replaced by a mock at the HTTP layer; everything else (signatures,
nonces, the window, the device table, the room network) is the real code path.

Run from the backend folder:
    uv run pytest ../tests/test_phase8_verify.py -v
"""

from __future__ import annotations

import asyncio
import base64
import datetime as dt
import hashlib
import json
import random
import sys
import time
import uuid
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from app.config import Settings, get_settings  # noqa: E402
from app.db import pool as db_pool  # noqa: E402
from app.main import app  # noqa: E402
from app.redis import client as redis_client  # noqa: E402
from app.redis import keys  # noqa: E402
from app.services.verification import integrity  # noqa: E402

ROUTER_101 = "192.168.101.10"  # room 101's router address (the room's subnet)
ROUTER_102 = "192.168.102.10"  # room 102's router address
AP_101 = "aa:bb:cc:00:01:01"
AP_102 = "aa:bb:cc:00:02:01"
ROLL = "TEST001"  # enrolled in room 101 by the seed
PACKAGE = get_settings().PLAY_INTEGRITY_PACKAGE_NAME
ROUTER_PEER = "127.0.0.1"  # the trusted reverse proxy in the default TRUSTED_PROXY_IPS


def _google(request: httpx.Request) -> httpx.Response:
    if request.url.host == "oauth2.googleapis.com":
        return httpx.Response(200, json={"access_token": "test-access-token"})
    kind, _, digest = json.loads(request.content)["integrityToken"].partition(":")
    if kind == "badtoken":
        return httpx.Response(400, json={"error": {"message": "invalid token"}})
    if kind == "down":
        return httpx.Response(500, json={})
    now_ms = int(time.time() * 1000)
    verdict = {
        "package": PACKAGE,
        "hash": digest,
        "timestamp": now_ms,
        "app": "PLAY_RECOGNIZED",
        "device": ["MEETS_DEVICE_INTEGRITY"],
    }
    if kind == "wronghash":
        verdict["hash"] = "0" * 64
    if kind == "old":
        verdict["timestamp"] = now_ms - 10 * 60 * 1000
    if kind == "nodevice":
        verdict["device"] = []
    if kind == "wrongpkg":
        verdict["package"] = "com.evil.app"
    if kind == "sideload":
        verdict["app"] = "UNRECOGNIZED_VERSION"
    return httpx.Response(
        200,
        json={
            "tokenPayloadExternal": {
                "requestDetails": {"requestHash": verdict["hash"], "timestampMillis": str(verdict["timestamp"])},
                "appIntegrity": {"packageName": verdict["package"], "appRecognitionVerdict": verdict["app"]},
                "deviceIntegrity": {"deviceRecognitionVerdict": verdict["device"]},
            }
        },
    )


def _service_account_file(directory: Path) -> Path:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    path = directory / "service-account.json"
    path.write_text(
        json.dumps(
            {
                "client_email": "test@nightroll.test",
                "private_key": pem,
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        )
    )
    return path


GATE_CODES = {
    "DEVICE_NOT_ENROLLED",
    "SIGNATURE_INVALID",
    "PAYLOAD_INVALID",
    "OUTSIDE_WINDOW",
    "NONCE_INVALID",
    "INTEGRITY_FAILED",
    "ENVIRONMENT_FLAGGED",
    "NETWORK_MISMATCH",
}


def passed_all_gates(body: dict) -> bool:
    """Phase 9 scores what passes the gates, so gate tests check the gates, not the final verdict."""
    return not any(reason["code"] in GATE_CODES for reason in body["reasons"])


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Harness:
    def __init__(self, device, student_id: str, room_id: str, creds: str) -> None:
        self.creds = creds
        self.device = device
        self.student_id = student_id
        self.room_id = room_id
        self.windows: list[str] = []
        self.pool = db_pool.get_pool()
        self.redis = redis_client.get_client()

    def client(self, peer: str = ROUTER_101, headers: dict | None = None) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, client=(peer, 50000)),
            base_url="http://test",
            headers=headers or {},
        )

    def sign_headers(self, method: str, path: str, body: bytes = b"") -> dict[str, str]:
        ts = str(int(time.time()))
        to_sign = f"{method}\n{path}\n{ts}\n{_sha256_hex(body)}"
        signature = self.device.sign(to_sign.encode(), ec.ECDSA(hashes.SHA256()))
        return {
            "X-Student-Id": self.student_id,
            "X-Timestamp": ts,
            "X-Signature": base64.b64encode(signature).decode(),
        }

    async def open_window(self) -> str:
        night = dt.date(2034, 1, 1) + dt.timedelta(days=random.randint(0, 3000))
        now = dt.datetime.now(dt.UTC)
        window_id = await self.pool.fetchval(
            """
            insert into attendance_windows (night, opens_at, closes_at, state)
            values ($1, $2, $3, 'open')
            on conflict (night) do update set state = 'open', opens_at = $2, closes_at = $3
            returning id
            """,
            night,
            now - dt.timedelta(minutes=1),
            now + dt.timedelta(minutes=10),
        )
        self.windows.append(str(window_id))
        return str(window_id)

    async def nonce(self, peer: str = ROUTER_101) -> dict:
        path = "/v1/attendance/nonce"
        async with self.client(peer) as c:
            resp = await c.get(path, headers=self.sign_headers("GET", path))
        assert resp.status_code == 200, resp.text
        return resp.json()

    def build(
        self,
        window_id: str,
        nonce: str,
        actions: list[str],
        *,
        env: dict | None = None,
        bssid: str = AP_101,
        mutate=None,
    ) -> dict:
        frames_raw = [f"frame-{i}-{uuid.uuid4()}".encode() for i in range(4)]
        frame_records = [
            {"index": i, "sha256": _sha256_hex(raw), "tag": actions[i] if i < 2 else "neutral"}
            for i, raw in enumerate(frames_raw)
        ]
        payload = {
            "v": 1,
            "student_id": self.student_id,
            "window_id": window_id,
            "nonce": nonce,
            "client_time": "2026-10-11T22:01:00+05:30",
            "challenge": [
                {"action": action, "started_ms": i * 1500, "detected_ms": i * 1500 + 900}
                for i, action in enumerate(actions)
            ],
            "frames": frame_records,
            "wifi": {
                "connected": {"bssid": bssid, "rssi": -52, "band": "5GHz"},
                "scan_age_ms": 800,
                "scan": [{"bssid": bssid, "rssi": -52, "band": "5GHz"}],
            },
            "environment": {
                "vpn": False,
                "proxy": False,
                "mock_location": False,
                "developer_options": False,
                "on_wifi": True,
            },
            "app_version": "0.1.0",
        }
        if env:
            payload["environment"].update(env)
        if mutate:
            mutate(payload)
        payload_text = json.dumps(payload, separators=(",", ":"))
        payload_bytes = payload_text.encode("utf-8")
        signature = self.device.sign(payload_bytes, ec.ECDSA(hashes.SHA256()))
        return {
            "payload": payload_text,
            "signature": base64.b64encode(signature).decode(),
            "frames": frames_raw,
            "token": f"ok:{_sha256_hex(payload_bytes)}",
        }

    async def post(
        self,
        built: dict,
        *,
        peer: str = ROUTER_101,
        token: str | None = None,
        headers: dict | None = None,
    ):
        data = {"payload": built["payload"], "signature": built["signature"]}
        use_token = built["token"] if token is None else token
        if use_token is not None:
            data["integrity_token"] = use_token
        files = [(f"frame_{i}", (f"{i}.jpg", raw, "image/jpeg")) for i, raw in enumerate(built["frames"])]
        async with self.client(peer, headers) as c:
            return await c.post("/v1/attendance/verify", data=data, files=files)

    async def marks(self, window_id: str) -> list:
        return await self.pool.fetch(
            "select verdict, reasons, attempt from attendance_marks where window_id = $1 and student_id = $2 "
            "order by attempt",
            uuid.UUID(window_id),
            uuid.UUID(self.student_id),
        )

    async def clear_rate_limit(self) -> None:
        await self.redis.delete(keys.submit_rate_key(self.student_id))


@pytest_asyncio.fixture
async def harness(tmp_path):
    settings = get_settings()
    test_settings = settings.model_copy(
        update={
            "GOOGLE_APPLICATION_CREDENTIALS": str(_service_account_file(tmp_path)),
            "PLAY_INTEGRITY_ENFORCE": True,
        }
    )
    app.dependency_overrides[get_settings] = lambda: test_settings
    integrity.TRANSPORT = httpx.MockTransport(_google)
    await db_pool.connect(settings)
    await redis_client.connect(settings)

    pool = db_pool.get_pool()
    redis = redis_client.get_client()
    row = await pool.fetchrow("select s.id, s.room_id from students s where s.roll_number = $1", ROLL)
    student_id = row["id"]
    device = ec.generate_private_key(ec.SECP256R1())
    public_der = device.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )

    async def reset_device() -> None:
        await pool.execute("delete from devices where student_id = $1", student_id)
        await pool.execute(
            "insert into devices (student_id, public_key, key_alias, active, enrolled_at) "
            "values ($1, $2, 'test-key', true, now())",
            student_id,
            public_der,
        )
        await pool.execute(
            "update students set enrolled_at = now(), consent_at = now(), consent_version = 'test' where id = $1",
            student_id,
        )

    async def clear_limits() -> None:
        # Every test shares one student and one router address, so earlier tests must not count against later ones.
        await redis.delete(keys.submit_rate_key(str(student_id)), f"ratelimit:nonce:{student_id}")
        async for key in redis.scan_iter("ratelimit:signature-failures:*"):
            await redis.delete(key)

    await reset_device()
    await clear_limits()
    h = Harness(device, str(student_id), str(row["room_id"]), test_settings.GOOGLE_APPLICATION_CREDENTIALS)
    yield h

    await clear_limits()
    for window_id in h.windows:
        await redis.delete(keys.window_state_key(window_id), keys.WINDOW_CURRENT)
        await pool.execute("delete from attendance_marks where window_id = $1", uuid.UUID(window_id))
        await pool.execute("delete from attendance_windows where id = $1", uuid.UUID(window_id))
    await pool.execute("delete from devices where student_id = $1", student_id)
    await pool.execute(
        "update students set enrolled_at = null, consent_at = null, consent_version = null where id = $1", student_id
    )
    await db_pool.disconnect()
    await redis_client.disconnect()
    app.dependency_overrides.clear()
    integrity.TRANSPORT = None


@pytest.mark.asyncio
async def test_genuine_submission_passes_all_six_gates(harness: Harness):
    window_id = await harness.open_window()
    issued = await harness.nonce()
    built = harness.build(window_id, issued["nonce"], issued["challenge"])
    resp = await harness.post(built)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert passed_all_gates(body), body
    assert body["mark_id"] is not None
    rows = await harness.marks(window_id)
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_other_routers_network_is_rejected(harness: Harness):
    window_id = await harness.open_window()
    issued = await harness.nonce()
    built = harness.build(window_id, issued["nonce"], issued["challenge"])
    resp = await harness.post(built, peer=ROUTER_102)
    body = resp.json()
    assert body["verdict"] == "REJECTED"
    assert body["reasons"][0]["code"] == "NETWORK_MISMATCH"
    assert "subnet" not in body["reasons"][0]["message"].lower()
    assert [r["verdict"] for r in await harness.marks(window_id)] == ["REJECTED"]


@pytest.mark.asyncio
async def test_right_router_wrong_access_point_is_rejected(harness: Harness):
    window_id = await harness.open_window()
    issued = await harness.nonce()
    built = harness.build(window_id, issued["nonce"], issued["challenge"], bssid=AP_102)
    body = (await harness.post(built)).json()
    assert body["reasons"][0]["code"] == "NETWORK_MISMATCH"


@pytest.mark.asyncio
async def test_forwarded_for_is_trusted_only_from_a_listed_proxy(harness: Harness):
    window_id = await harness.open_window()
    issued = await harness.nonce()
    spoofed_envelope = harness.build(window_id, issued["nonce"], issued["challenge"])
    spoofed = await harness.post(spoofed_envelope, peer=ROUTER_102, headers={"X-Forwarded-For": ROUTER_101})
    assert spoofed.json()["reasons"][0]["code"] == "NETWORK_MISMATCH"

    # The rejection issued a fresh nonce, so the trusted-proxy case is a new envelope.
    await harness.clear_rate_limit()
    fresh = await harness.nonce()
    proxied_envelope = harness.build(window_id, fresh["nonce"], fresh["challenge"])
    proxied = await harness.post(proxied_envelope, peer=ROUTER_PEER, headers={"X-Forwarded-For": ROUTER_101})
    assert passed_all_gates(proxied.json())

    # The proxied attempt used this window's nonce, so the unproxied case gets its own window.
    await harness.pool.execute("update attendance_windows set state = 'closed' where id = $1", uuid.UUID(window_id))
    second_window = await harness.open_window()
    await harness.clear_rate_limit()
    fresh = await harness.nonce()
    unproxied_envelope = harness.build(
        second_window, fresh["nonce"], fresh["challenge"], env={"developer_options": True}
    )
    unproxied = await harness.post(unproxied_envelope, peer=ROUTER_PEER)
    assert unproxied.json()["reasons"][0]["code"] == "NETWORK_MISMATCH"


@pytest.mark.asyncio
async def test_different_phone_signature_is_rejected_and_not_attributed(harness: Harness):
    window_id = await harness.open_window()
    issued = await harness.nonce()
    built = harness.build(window_id, issued["nonce"], issued["challenge"])
    built["signature"] = base64.b64encode(
        ec.generate_private_key(ec.SECP256R1()).sign(built["payload"].encode(), ec.ECDSA(hashes.SHA256()))
    ).decode()
    body = (await harness.post(built)).json()
    assert body["reasons"][0]["code"] == "SIGNATURE_INVALID"
    assert body["mark_id"] is None
    assert await harness.marks(window_id) == []


@pytest.mark.asyncio
async def test_one_byte_changed_after_signing_is_rejected(harness: Harness):
    window_id = await harness.open_window()
    issued = await harness.nonce()
    built = harness.build(window_id, issued["nonce"], issued["challenge"])
    built["payload"] = built["payload"].replace('"app_version":"0.1.0"', '"app_version":"0.1.1"')
    body = (await harness.post(built)).json()
    assert body["reasons"][0]["code"] == "SIGNATURE_INVALID"


@pytest.mark.asyncio
async def test_replaced_frame_after_signing_is_rejected(harness: Harness):
    window_id = await harness.open_window()
    issued = await harness.nonce()
    built = harness.build(window_id, issued["nonce"], issued["challenge"])
    built["frames"][2] = b"a different photo"
    body = (await harness.post(built)).json()
    assert body["reasons"][0]["code"] == "SIGNATURE_INVALID"


@pytest.mark.asyncio
async def test_reused_nonce_in_a_new_submission_is_rejected(harness: Harness):
    window_id = await harness.open_window()
    issued = await harness.nonce()
    first = harness.build(window_id, issued["nonce"], issued["challenge"])
    assert passed_all_gates((await harness.post(first)).json())

    await harness.clear_rate_limit()
    second = harness.build(window_id, issued["nonce"], issued["challenge"], env={"developer_options": True})
    body = (await harness.post(second)).json()
    assert body["reasons"][0]["code"] == "NONCE_INVALID"


@pytest.mark.asyncio
async def test_wrong_challenge_is_refused_and_a_fresh_nonce_is_issued(harness: Harness):
    window_id = await harness.open_window()
    issued = await harness.nonce()
    wrong = harness.build(window_id, issued["nonce"], list(reversed(issued["challenge"])))
    assert (await harness.post(wrong)).json()["reasons"][0]["code"] == "NONCE_INVALID"

    await harness.clear_rate_limit()
    fresh = await harness.nonce()
    assert fresh["nonce"] != issued["nonce"]
    right = harness.build(window_id, fresh["nonce"], fresh["challenge"])
    assert passed_all_gates((await harness.post(right)).json())


@pytest.mark.asyncio
async def test_submission_after_the_window_closes_is_rejected(harness: Harness):
    window_id = await harness.open_window()
    issued = await harness.nonce()
    await harness.pool.execute(
        "update attendance_windows set closes_at = now() - interval '1 second', opens_at = now() - interval '1 hour' "
        "where id = $1",
        uuid.UUID(window_id),
    )
    built = harness.build(window_id, issued["nonce"], issued["challenge"])
    body = (await harness.post(built)).json()
    assert body["reasons"][0]["code"] == "OUTSIDE_WINDOW"


@pytest.mark.asyncio
async def test_phone_reporting_a_vpn_is_flagged(harness: Harness):
    window_id = await harness.open_window()
    issued = await harness.nonce()
    built = harness.build(window_id, issued["nonce"], issued["challenge"], env={"vpn": True})
    body = (await harness.post(built)).json()
    assert body["reasons"][0]["code"] == "ENVIRONMENT_FLAGGED"


@pytest.mark.asyncio
async def test_identical_resend_returns_the_same_response_and_one_row(harness: Harness):
    window_id = await harness.open_window()
    issued = await harness.nonce()
    built = harness.build(window_id, issued["nonce"], issued["challenge"])
    first = await harness.post(built)
    second = await harness.post(built)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert len(await harness.marks(window_id)) == 1


@pytest.mark.asyncio
async def test_concurrent_identical_submissions_are_processed_once(harness: Harness):
    window_id = await harness.open_window()
    issued = await harness.nonce()
    built = harness.build(window_id, issued["nonce"], issued["challenge"])
    responses = await asyncio.gather(*(harness.post(built) for _ in range(3)))
    assert {r.status_code for r in responses} == {200}
    assert len({json.dumps(r.json(), sort_keys=True) for r in responses}) == 1
    assert len(await harness.marks(window_id)) == 1


@pytest.mark.asyncio
async def test_new_submissions_are_rate_limited_to_one_per_20_seconds(harness: Harness):
    window_id = await harness.open_window()
    issued = await harness.nonce()
    assert (await harness.post(harness.build(window_id, issued["nonce"], issued["challenge"]))).status_code == 200
    other = harness.build(window_id, issued["nonce"], issued["challenge"], env={"developer_options": True})
    limited = await harness.post(other)
    assert limited.status_code == 429
    assert 1 <= int(limited.headers["retry-after"]) <= 20


@pytest.mark.asyncio
async def test_three_rejections_end_retries_and_send_the_student_to_the_scanner(harness: Harness):
    window_id = await harness.open_window()
    issued = await harness.nonce()
    bodies = []
    for _ in range(3):
        built = harness.build(window_id, issued["nonce"], issued["challenge"])
        bodies.append((await harness.post(built, peer=ROUTER_102)).json())
        await harness.clear_rate_limit()
        issued = await harness.nonce(peer=ROUTER_102)  # the app fetches the fresh nonce after a rejection
    assert [b["attempts_left"] for b in bodies] == [2, 1, 0]
    assert [b["retry_allowed"] for b in bodies] == [True, True, False]
    assert bodies[-1]["fallback"] == "GROUND_FLOOR_SCANNER"
    assert [r["attempt"] for r in await harness.marks(window_id)] == [1, 2, 3]


@pytest.mark.asyncio
async def test_rejected_attempt_issues_a_fresh_nonce_for_the_retry(harness: Harness):
    window_id = await harness.open_window()
    issued = await harness.nonce()
    built = harness.build(window_id, issued["nonce"], issued["challenge"], env={"vpn": True})
    body = (await harness.post(built)).json()
    assert body["retry_allowed"] is True
    fresh = await harness.nonce()
    assert fresh["state"] == "open"
    assert fresh["nonce"] != issued["nonce"]


@pytest.mark.asyncio
async def test_nonce_endpoint_refuses_unsigned_requests(harness: Harness):
    window_id = await harness.open_window()
    assert window_id
    async with harness.client() as c:
        assert (await c.get("/v1/attendance/nonce")).status_code == 401
        bad = {**harness.sign_headers("GET", "/v1/attendance/nonce"), "X-Signature": "AAAA"}
        assert (await c.get("/v1/attendance/nonce", headers=bad)).status_code == 401


@pytest.mark.asyncio
async def test_stale_request_timestamp_is_refused(harness: Harness):
    old = int(time.time()) - 120
    path = "/v1/attendance/nonce"
    ts = str(old)
    signature = harness.device.sign(f"GET\n{path}\n{ts}\n{_sha256_hex(b'')}".encode(), ec.ECDSA(hashes.SHA256()))
    headers = {
        "X-Student-Id": harness.student_id,
        "X-Timestamp": ts,
        "X-Signature": base64.b64encode(signature).decode(),
    }
    async with harness.client() as c:
        assert (await c.get(path, headers=headers)).status_code == 401


@pytest.mark.asyncio
async def test_play_integrity_bad_token_fails_when_enforced(harness: Harness):
    window_id = await harness.open_window()
    issued = await harness.nonce()
    built = harness.build(window_id, issued["nonce"], issued["challenge"])
    body = (await harness.post(built, token="badtoken:" + _sha256_hex(built["payload"].encode()))).json()
    assert body["reasons"][0]["code"] == "INTEGRITY_FAILED"


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["wronghash", "old", "nodevice", "wrongpkg"])
async def test_play_integrity_verdict_problems_fail(harness: Harness, kind: str):
    window_id = await harness.open_window()
    issued = await harness.nonce()
    built = harness.build(window_id, issued["nonce"], issued["challenge"])
    body = (await harness.post(built, token=f"{kind}:{_sha256_hex(built['payload'].encode())}")).json()
    assert body["reasons"][0]["code"] == "INTEGRITY_FAILED"


@pytest.mark.asyncio
async def test_play_integrity_warning_only_when_not_enforced(harness: Harness):
    app.dependency_overrides[get_settings] = lambda: get_settings().model_copy(
        update={"PLAY_INTEGRITY_ENFORCE": False, "GOOGLE_APPLICATION_CREDENTIALS": harness.creds}
    )
    window_id = await harness.open_window()
    issued = await harness.nonce()
    built = harness.build(window_id, issued["nonce"], issued["challenge"])
    body = (await harness.post(built, token=f"wronghash:{_sha256_hex(built['payload'].encode())}")).json()
    assert passed_all_gates(body)
    recorded = await harness.pool.fetchval(
        "select scores::text from attendance_marks where window_id = $1", uuid.UUID(window_id)
    )
    assert "INTEGRITY_NOT_ENFORCED" in recorded


@pytest.mark.asyncio
async def test_google_unreachable_is_503_and_never_passes(harness: Harness):
    window_id = await harness.open_window()
    issued = await harness.nonce()
    built = harness.build(window_id, issued["nonce"], issued["challenge"])
    resp = await harness.post(built, token=f"down:{_sha256_hex(built['payload'].encode())}")
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "INTEGRITY_UNAVAILABLE"
    assert await harness.marks(window_id) == []
    await harness.clear_rate_limit()
    retry = harness.build(window_id, issued["nonce"], issued["challenge"])
    assert (await harness.post(retry)).status_code == 200


@pytest.mark.asyncio
async def test_missing_service_account_is_503(harness: Harness):
    app.dependency_overrides[get_settings] = lambda: get_settings().model_copy(
        update={"GOOGLE_APPLICATION_CREDENTIALS": "/nonexistent/service-account.json"}
    )
    window_id = await harness.open_window()
    issued = await harness.nonce()
    built = harness.build(window_id, issued["nonce"], issued["challenge"])
    resp = await harness.post(built)
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_oversized_payload_and_frames_are_refused(harness: Harness):
    window_id = await harness.open_window()
    issued = await harness.nonce()
    built = harness.build(window_id, issued["nonce"], issued["challenge"])
    huge = dict(built, payload=built["payload"] + " " * (65 * 1024))
    assert (await harness.post(huge)).status_code == 413

    too_many = dict(built, frames=built["frames"] + [b"x", b"y"])
    assert (await harness.post(too_many)).status_code == 422

    big_frame = dict(built, frames=[b"0" * (1024 * 1024 + 1)] + built["frames"][1:])
    assert (await harness.post(big_frame)).status_code == 413


@pytest.mark.asyncio
async def test_unknown_payload_fields_are_refused_after_the_signature(harness: Harness):
    window_id = await harness.open_window()
    issued = await harness.nonce()
    built = harness.build(window_id, issued["nonce"], issued["challenge"], mutate=lambda p: p.update(extra=1))
    body = (await harness.post(built)).json()
    assert body["reasons"][0]["code"] == "PAYLOAD_INVALID"


@pytest.mark.asyncio
async def test_unsupported_payload_version_is_refused(harness: Harness):
    window_id = await harness.open_window()
    issued = await harness.nonce()
    built = harness.build(window_id, issued["nonce"], issued["challenge"], mutate=lambda p: p.update(v=2))
    body = (await harness.post(built)).json()
    assert body["reasons"][0]["code"] == "PAYLOAD_INVALID"


@pytest.mark.asyncio
async def test_startup_refuses_enforcement_off_in_pilot(harness: Harness):
    base = get_settings().model_dump()
    base.update(APP_ENV="pilot", PLAY_INTEGRITY_ENFORCE=False)
    with pytest.raises(Exception, match="PLAY_INTEGRITY_ENFORCE=false is not allowed"):
        Settings(**base)


@pytest.mark.asyncio
async def test_startup_refuses_network_gate_off_in_production(harness: Harness):
    base = get_settings().model_dump()
    base.update(APP_ENV="production", NETWORK_VERIFY_MODE="off", PLAY_INTEGRITY_ENFORCE=True)
    with pytest.raises(Exception, match="NETWORK_VERIFY_MODE=off is not allowed"):
        Settings(**base)
