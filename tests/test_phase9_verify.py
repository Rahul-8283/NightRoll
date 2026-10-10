"""Phase 9 exit criteria, run against the real API, database, Redis and face worker.

Needs the face worker running at FACE_WORKER_URL (see backend/.env). Google's Play Integrity service is
mocked at the HTTP layer; the face crops come from InsightFace's sample photo.

Run from the backend folder, with the face worker already started:
    uv run pytest ../tests/test_phase9_verify.py -v
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import random
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.config import get_settings  # noqa: E402
from app.db import pool as db_pool  # noqa: E402
from app.main import app  # noqa: E402
from app.redis import client as redis_client  # noqa: E402
from app.redis import keys  # noqa: E402
from app.services.verification import integrity  # noqa: E402

ROUTER_101 = "192.168.101.10"
OWN = "aa:bb:cc:00:01:01"
OWN2 = "aa:bb:cc:00:01:05"
NEIGH = "aa:bb:cc:00:02:01"
NEIGH2 = "aa:bb:cc:00:02:05"
ROLL = "TEST001"
PACKAGE = get_settings().PLAY_INTEGRITY_PACKAGE_NAME

INSIDE_SCAN = [
    {"bssid": OWN, "rssi": -48, "band": "5GHz"},
    {"bssid": OWN2, "rssi": -50, "band": "2.4GHz"},
    {"bssid": NEIGH, "rssi": -70, "band": "5GHz"},
    {"bssid": NEIGH2, "rssi": -78, "band": "2.4GHz"},
]
FAR_SCAN = [
    {"bssid": OWN, "rssi": -86, "band": "5GHz"},
    {"bssid": OWN2, "rssi": -88, "band": "2.4GHz"},
    {"bssid": "de:ad:be:ef:00:01", "rssi": -61, "band": "2.4GHz"},
    {"bssid": "de:ad:be:ef:00:02", "rssi": -66, "band": "5GHz"},
    {"bssid": "de:ad:be:ef:00:03", "rssi": -70, "band": "2.4GHz"},
]


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _google(request: httpx.Request) -> httpx.Response:
    if request.url.host == "oauth2.googleapis.com":
        return httpx.Response(200, json={"access_token": "test-access-token"})
    digest = json.loads(request.content)["integrityToken"].partition(":")[2]
    now_ms = int(time.time() * 1000)
    return httpx.Response(
        200,
        json={
            "tokenPayloadExternal": {
                "requestDetails": {"requestHash": digest, "timestampMillis": str(now_ms)},
                "appIntegrity": {"packageName": PACKAGE, "appRecognitionVerdict": "PLAY_RECOGNIZED"},
                "deviceIntegrity": {"deviceRecognitionVerdict": ["MEETS_DEVICE_INTEGRITY"]},
            }
        },
    )


@pytest.fixture(scope="session")
def frames(tmp_path_factory) -> dict[str, list[bytes]]:
    out = tmp_path_factory.mktemp("p9frames")
    result = subprocess.run(
        [str(ROOT / "face/.venv/bin/python"), "-W", "ignore", str(ROOT / "tests/phase9_frame_factory.py"), str(out)],
        cwd=ROOT / "face",
        capture_output=True,
        text=True,
        check=True,
    )
    summary = json.loads(result.stdout.strip().splitlines()[-1])
    return {name: [Path(p).read_bytes() for p in paths] for name, paths in summary.items()}


class Harness:
    def __init__(self, device, student_id: str, creds: str, frames) -> None:
        self.device = device
        self.student_id = student_id
        self.creds = creds
        self.frames = frames
        self.pool = db_pool.get_pool()
        self.redis = redis_client.get_client()
        self.windows: list[str] = []

    def client(self, peer: str = ROUTER_101) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=(peer, 50000)), base_url="http://test")

    def sign_headers(self, method: str, path: str) -> dict[str, str]:
        ts = str(int(time.time()))
        signature = self.device.sign(f"{method}\n{path}\n{ts}\n{_sha256_hex(b'')}".encode(), ec.ECDSA(hashes.SHA256()))
        return {
            "X-Student-Id": self.student_id,
            "X-Timestamp": ts,
            "X-Signature": base64.b64encode(signature).decode(),
        }

    async def open_window(self) -> str:
        night = dt.date(2035, 1, 1) + dt.timedelta(days=random.randint(0, 3000))
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

    async def nonce(self, window_id: str, actions=("blink", "smile")) -> str:
        """Issue the nonce through the real endpoint, then pin the challenge the test performs."""
        path = "/v1/attendance/nonce"
        async with self.client() as c:
            body = (await c.get(path, headers=self.sign_headers("GET", path))).json()
        assert body["state"] == "open", body
        await self.redis.hset(keys.nonce_key(window_id, self.student_id), "challenge", ",".join(actions))
        return body["nonce"]

    def build(self, window_id: str, nonce: str, live: list[bytes], *, scan=INSIDE_SCAN, durations=None) -> dict:
        durations = durations or [900, 900]
        actions = ["blink", "smile"]
        steps = [
            {"action": action, "started_ms": i * 1500, "detected_ms": i * 1500 + durations[i]}
            for i, action in enumerate(actions)
        ]
        tags = ["blink", "smile", "neutral", "neutral"]
        frame_raw = live
        payload = {
            "v": 1,
            "student_id": self.student_id,
            "window_id": window_id,
            "nonce": nonce,
            "client_time": "2026-10-11T22:01:00+05:30",
            "challenge": steps,
            "frames": [{"index": i, "sha256": _sha256_hex(raw), "tag": tags[i]} for i, raw in enumerate(frame_raw)],
            "wifi": {
                "connected": {"bssid": scan[0]["bssid"], "rssi": scan[0]["rssi"], "band": scan[0]["band"]},
                "scan_age_ms": 800,
                "scan": scan,
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
        text = json.dumps(payload, separators=(",", ":"))
        raw = text.encode("utf-8")
        return {
            "payload": text,
            "signature": base64.b64encode(self.device.sign(raw, ec.ECDSA(hashes.SHA256()))).decode(),
            "frames": frame_raw,
            "token": f"ok:{_sha256_hex(raw)}",
        }

    async def post(self, built: dict):
        data = {"payload": built["payload"], "signature": built["signature"], "integrity_token": built["token"]}
        files = [(f"frame_{i}", (f"{i}.jpg", raw, "image/jpeg")) for i, raw in enumerate(built["frames"])]
        async with self.client() as c:
            return await c.post("/v1/attendance/verify", data=data, files=files)

    async def scores_for(self, mark_id: str) -> dict:
        raw = await self.pool.fetchval("select scores::text from attendance_marks where id = $1", uuid.UUID(mark_id))
        return json.loads(raw)

    async def clear_rate_limit(self) -> None:
        await self.redis.delete(keys.submit_rate_key(self.student_id))


@pytest_asyncio.fixture
async def p9(tmp_path, frames):
    settings = get_settings()
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    creds = tmp_path / "sa.json"
    creds.write_text(
        json.dumps(
            {
                "client_email": "test@nightroll.test",
                "private_key": key.private_bytes(
                    serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
                ).decode(),
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        )
    )
    test_settings = settings.model_copy(
        update={"GOOGLE_APPLICATION_CREDENTIALS": str(creds), "PLAY_INTEGRITY_ENFORCE": True}
    )
    app.dependency_overrides[get_settings] = lambda: test_settings
    integrity.TRANSPORT = httpx.MockTransport(_google)
    await db_pool.connect(settings)
    await redis_client.connect(settings)

    pool = db_pool.get_pool()
    redis = redis_client.get_client()
    row = await pool.fetchrow("select id from students where roll_number = $1", ROLL)
    student_id = str(row["id"])
    device = ec.generate_private_key(ec.SECP256R1())
    public_der = device.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    await pool.execute("delete from devices where student_id = $1", row["id"])
    await pool.execute(
        "insert into devices (student_id, public_key, key_alias, active, enrolled_at) "
        "values ($1, $2, 'test-key', true, now())",
        row["id"],
        public_der,
    )
    await pool.execute(
        "update students set enrolled_at = now(), consent_at = now(), consent_version = 'test' where id = $1", row["id"]
    )

    # The student's enrolled face, from the enrolment crops.
    worker = settings.FACE_WORKER_URL.rstrip("/")
    worker_auth = {"Authorization": f"Bearer {settings.FACE_WORKER_TOKEN}"}
    enrol = httpx.post(
        f"{worker}/enroll",
        headers=worker_auth,
        data={"student_id": student_id},
        files=[("frames", (f"{i}.jpg", b, "image/jpeg")) for i, b in enumerate(frames["enroll"])],
        timeout=120,
    )
    assert enrol.status_code == 200, enrol.text

    # A room-101 fingerprint learned from three spot scans: own routers strong, neighbours medium.
    room_id = await pool.fetchval("select room_id from students where id = $1", row["id"])
    version = (
        int(await pool.fetchval("select coalesce(max(version), 0) from room_fingerprints where room_id = $1", room_id))
        + 1
    )
    pattern = {
        "scans_count": 3,
        "bssids": {
            OWN: {"median_rssi": -48.0, "band": "5GHz", "count": 3, "label": "own"},
            OWN2: {"median_rssi": -50.0, "band": "2.4GHz", "count": 3, "label": "own"},
            NEIGH: {"median_rssi": -70.0, "band": "5GHz", "count": 3, "label": "hostel"},
            NEIGH2: {"median_rssi": -78.0, "band": "2.4GHz", "count": 3, "label": "hostel"},
        },
    }
    fingerprint_id = await pool.fetchval(
        "insert into room_fingerprints (room_id, version, pattern) values ($1, $2, $3::jsonb) returning id",
        room_id,
        version,
        json.dumps(pattern),
    )
    await redis.delete(keys.submit_rate_key(student_id))

    h = Harness(device, student_id, str(creds), frames)
    h.room_id = room_id
    h.fingerprint_id = fingerprint_id
    yield h

    for window_id in h.windows:
        await redis.delete(keys.window_state_key(window_id), keys.WINDOW_CURRENT)
        await pool.execute("delete from attendance_marks where window_id = $1", uuid.UUID(window_id))
        await pool.execute("delete from attendance_windows where id = $1", uuid.UUID(window_id))
    await pool.execute("delete from room_fingerprints where id = $1", fingerprint_id)
    await pool.execute("delete from devices where student_id = $1", row["id"])
    await pool.execute(
        "update students set enrolled_at = null, consent_at = null, consent_version = null where id = $1", row["id"]
    )
    httpx.delete(f"{worker}/students/{student_id}/embedding", headers=worker_auth, timeout=30)
    await redis.delete(keys.submit_rate_key(student_id))
    await db_pool.disconnect()
    await redis_client.disconnect()
    app.dependency_overrides.clear()
    integrity.TRANSPORT = None


@pytest.mark.asyncio
async def test_teammate_in_own_room_gets_present(p9: Harness):
    window_id = await p9.open_window()
    nonce = await p9.nonce(window_id)
    started = time.perf_counter()
    resp = await p9.post(p9.build(window_id, nonce, p9.frames["live_a"]))
    elapsed_ms = (time.perf_counter() - started) * 1000
    body = resp.json()
    assert resp.status_code == 200, resp.text
    assert body["verdict"] == "PRESENT", body
    assert body["score"] >= 0.8
    assert body["reasons"] == []
    print(f"\nend-to-end time: {elapsed_ms:.0f} ms, score {body['score']}")


@pytest.mark.asyncio
async def test_response_has_no_per_scorer_breakdown(p9: Harness):
    window_id = await p9.open_window()
    nonce = await p9.nonce(window_id)
    body = (await p9.post(p9.build(window_id, nonce, p9.frames["live_a"]))).json()
    assert set(body) == {"mark_id", "verdict", "score", "reasons", "retry_allowed", "attempts_left", "fallback"}


@pytest.mark.asyncio
async def test_stored_mark_shows_all_five_scores_and_reasons(p9: Harness):
    window_id = await p9.open_window()
    nonce = await p9.nonce(window_id)
    body = (await p9.post(p9.build(window_id, nonce, p9.frames["live_a"]))).json()
    stored = await p9.scores_for(body["mark_id"])
    names = {scorer["name"] for scorer in stored["scorers"]}
    assert names == {"face", "liveness", "fingerprint", "own_ap", "ap_agreement"}
    assert all("score" in scorer and "detail" in scorer for scorer in stored["scorers"])
    assert stored["rule"] == "present cutoff"


@pytest.mark.asyncio
async def test_a_different_person_is_rejected_for_face(p9: Harness):
    window_id = await p9.open_window()
    nonce = await p9.nonce(window_id)
    body = (await p9.post(p9.build(window_id, nonce, p9.frames["live_b"]))).json()
    assert body["verdict"] == "REJECTED"
    assert body["reasons"][0]["code"] == "FACE_MISMATCH"
    assert len(body["reasons"]) == 1


@pytest.mark.asyncio
async def test_far_from_the_room_gets_a_lower_fingerprint_and_is_not_present(p9: Harness):
    inside_window = await p9.open_window()
    inside = (await p9.post(p9.build(inside_window, await p9.nonce(inside_window), p9.frames["live_a"]))).json()
    inside_fp = next(s for s in (await p9.scores_for(inside["mark_id"]))["scorers"] if s["name"] == "fingerprint")[
        "score"
    ]

    await p9.clear_rate_limit()
    far_window = await p9.open_window()
    await p9.pool.execute("update attendance_windows set state = 'closed' where id = $1", uuid.UUID(inside_window))
    far = (await p9.post(p9.build(far_window, await p9.nonce(far_window), p9.frames["live_a"], scan=FAR_SCAN))).json()
    far_fp = next(s for s in (await p9.scores_for(far["mark_id"]))["scorers"] if s["name"] == "fingerprint")["score"]
    assert far_fp < inside_fp
    assert far["verdict"] != "PRESENT"


@pytest.mark.asyncio
async def test_room_without_a_fingerprint_is_needs_review(p9: Harness):
    await p9.pool.execute("delete from room_fingerprints where id = $1", p9.fingerprint_id)
    window_id = await p9.open_window()
    body = (await p9.post(p9.build(window_id, await p9.nonce(window_id), p9.frames["live_a"]))).json()
    assert body["verdict"] == "NEEDS_REVIEW", body
    assert "FINGERPRINT_MISSING" in [r["code"] for r in body["reasons"]]


@pytest.mark.asyncio
async def test_a_second_genuine_submission_after_present_returns_the_existing_mark(p9: Harness):
    window_id = await p9.open_window()
    first = (await p9.post(p9.build(window_id, await p9.nonce(window_id), p9.frames["live_a"]))).json()
    assert first["verdict"] == "PRESENT"

    await p9.clear_rate_limit()
    again = (await p9.post(p9.build(window_id, "n" * 24, p9.frames["live_a"]))).json()
    assert again["verdict"] == "PRESENT"
    assert again["mark_id"] == first["mark_id"]
    count = await p9.pool.fetchval(
        "select count(*) from attendance_marks where window_id = $1 and verdict = 'PRESENT'", uuid.UUID(window_id)
    )
    assert count == 1


@pytest.mark.asyncio
async def test_thresholds_from_settings_change_the_verdict(p9: Harness):
    app.dependency_overrides[get_settings] = lambda: get_settings().model_copy(
        update={
            "GOOGLE_APPLICATION_CREDENTIALS": p9.creds,
            "PLAY_INTEGRITY_ENFORCE": True,
            "THRESHOLD_PRESENT": 0.999,
        }
    )
    window_id = await p9.open_window()
    body = (await p9.post(p9.build(window_id, await p9.nonce(window_id), p9.frames["live_a"]))).json()
    assert body["verdict"] == "NEEDS_REVIEW"


@pytest.mark.asyncio
async def test_a_too_fast_action_is_rejected_for_liveness(p9: Harness):
    window_id = await p9.open_window()
    nonce = await p9.nonce(window_id)
    body = (await p9.post(p9.build(window_id, nonce, p9.frames["live_a"], durations=[120, 900]))).json()
    assert body["verdict"] == "REJECTED"
    assert body["reasons"][0]["code"] == "LIVENESS_FAILED"


@pytest.mark.asyncio
async def test_face_service_down_is_503_and_nothing_is_recorded(p9: Harness):
    app.dependency_overrides[get_settings] = lambda: get_settings().model_copy(
        update={
            "GOOGLE_APPLICATION_CREDENTIALS": p9.creds,
            "PLAY_INTEGRITY_ENFORCE": True,
            "FACE_WORKER_URL": "http://127.0.0.1:9",
        }
    )
    window_id = await p9.open_window()
    resp = await p9.post(p9.build(window_id, await p9.nonce(window_id), p9.frames["live_a"]))
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "FACE_UNAVAILABLE"
    assert (
        await p9.pool.fetchval("select count(*) from attendance_marks where window_id = $1", uuid.UUID(window_id)) == 0
    )
