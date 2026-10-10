"""Simulate a night of attendance without any phone.

Each seeded test student gets a real device key, a real enrolled face and a real signed submission, sent to
the running API and face worker exactly as the app would send it. Watch the warden dashboard while it runs.

Needs the API (port 8000) and the face worker running, and the seed already applied. Run from the backend folder:

    uv run python ../scripts/simulate_night.py            # run the night, one student every 3 seconds
    uv run python ../scripts/simulate_night.py --delay 1  # faster
    uv run python ../scripts/simulate_night.py --close    # close the simulated window (records absentees)
    uv run python ../scripts/simulate_night.py --reset    # remove everything the simulator created

It uses its own night (2089-12-31), never a real one. It skips any student who already has a real device or a
real enrolment, and --reset removes only what the simulator made. Faces come from InsightFace's sample photo.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import ipaddress
import json
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import asyncpg
import httpx
import jwt
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.config import get_settings  # noqa: E402
from app.redis import client as redis_client  # noqa: E402
from app.redis import keys  # noqa: E402

SIM_NIGHT = date(2089, 12, 31)
MARKER = "simulator"
NEIGHBOURS = ["aa:bb:cc:ff:00:01", "aa:bb:cc:ff:00:02"]

# What each student does tonight, in roll-number order. The last one never opens the app.
SCENARIOS = [
    ("in bed, own phone", "present"),
    ("in bed, own phone", "present"),
    ("a friend holds the phone", "wrong_person"),
    ("in bed, own phone", "present"),
    ("marking from another room's Wi-Fi", "wrong_network"),
    ("in the corridor, weak signal", "far"),
    ("in bed, own phone", "present"),
    ("never opens the app", "no_show"),
]


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def admin_token(settings) -> str:
    """A short-lived admin token signed with the backend's own secret, for the open and close calls."""
    now = int(time.time())
    claims = {
        "sub": str(uuid.uuid4()),
        "aud": "authenticated",
        "aal": "aal2",
        "email": "simulator@nightroll.local",
        "iat": now,
        "exp": now + 600,
        "app_metadata": {"role": "admin"},
    }
    return jwt.encode(claims, settings.SUPABASE_JWT_SECRET, algorithm="HS256")


def make_frames() -> dict[str, list[bytes]]:
    """Face crops from InsightFace's sample photo, made by the face worker's own Python."""
    out = Path(tempfile.mkdtemp(prefix="nightroll-sim-"))
    result = subprocess.run(
        [str(ROOT / "face/.venv/bin/python"), "-W", "ignore", str(ROOT / "tests/phase9_frame_factory.py"), str(out)],
        cwd=ROOT / "face",
        capture_output=True,
        text=True,
        check=True,
    )
    summary = json.loads(result.stdout.strip().splitlines()[-1])
    return {name: [Path(p).read_bytes() for p in paths] for name, paths in summary.items()}


def room_ip(subnet: str) -> str:
    network = ipaddress.ip_network(subnet, strict=False)
    hosts = list(network.hosts())
    return str(hosts[0] if hosts else network.network_address)


def scan_for(own: list[dict], *, far: bool) -> list[dict]:
    strength = [-86, -88] if far else [-48, -50]
    scan = [{"bssid": ap["bssid"], "rssi": strength[i % 2], "band": ap["band"] or "5GHz"} for i, ap in enumerate(own)]
    if not far:
        scan += [
            {"bssid": NEIGHBOURS[0], "rssi": -70, "band": "5GHz"},
            {"bssid": NEIGHBOURS[1], "rssi": -78, "band": "2.4GHz"},
        ]
    return scan


class Phone:
    """One student's phone: a P-256 key that signs every request, as the Keystore key does on Android."""

    def __init__(self, student: asyncpg.Record, api: str) -> None:
        self.student_id = str(student["id"])
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.api = api

    def public_der(self) -> bytes:
        return self.key.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
        )

    def _sign(self, data: bytes) -> str:
        return base64.b64encode(self.key.sign(data, ec.ECDSA(hashes.SHA256()))).decode()

    def _headers(self, method: str, path: str, ip: str) -> dict[str, str]:
        ts = str(int(time.time()))
        return {
            "X-Student-Id": self.student_id,
            "X-Timestamp": ts,
            "X-Signature": self._sign(f"{method}\n{path}\n{ts}\n{sha256_hex(b'')}".encode()),
            "X-Forwarded-For": ip,
        }

    async def nonce(self, client: httpx.AsyncClient, ip: str) -> dict:
        path = "/v1/attendance/nonce"
        response = await client.get(f"{self.api}{path}", headers=self._headers("GET", path, ip))
        response.raise_for_status()
        return response.json()

    async def mark(self, client: httpx.AsyncClient, ip: str, window_id: str, nonce: str, frames: list[bytes], scan):
        actions = ["blink", "smile"]
        payload = {
            "v": 1,
            "student_id": self.student_id,
            "window_id": window_id,
            "nonce": nonce,
            "client_time": datetime.now(UTC).isoformat(),
            "challenge": [
                {"action": action, "started_ms": i * 1500, "detected_ms": i * 1500 + 900}
                for i, action in enumerate(actions)
            ],
            "frames": [
                {"index": i, "sha256": sha256_hex(raw), "tag": (actions + ["neutral", "neutral"])[i]}
                for i, raw in enumerate(frames)
            ],
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
        return await client.post(
            f"{self.api}/v1/attendance/verify",
            data={"payload": text, "signature": self._sign(text.encode())},
            files=[(f"frame_{i}", (f"{i}.jpg", raw, "image/jpeg")) for i, raw in enumerate(frames)],
            headers={"X-Forwarded-For": ip},
        )


async def students_and_rooms(pool: asyncpg.Pool) -> list[asyncpg.Record]:
    return await pool.fetch(
        """
        select s.id, s.roll_number, s.name, s.room_id, s.enrolled_at, s.consent_version,
               r.number as room_number, r.subnet::text as subnet,
               exists (select 1 from devices d where d.student_id = s.id and d.key_alias <> $1) as real_device
        from students s join rooms r on r.id = s.room_id
        where s.active and s.roll_number like 'TEST%'
        order by s.roll_number
        """,
        MARKER,
    )


async def access_points(pool: asyncpg.Pool) -> dict:
    rows = await pool.fetch("select room_id, bssid::text as bssid, band from access_points order by bssid")
    by_room: dict = {}
    for row in rows:
        by_room.setdefault(row["room_id"], []).append({"bssid": row["bssid"], "band": row["band"]})
    return by_room


async def ensure_fingerprint(pool: asyncpg.Pool, room_id, own: list[dict]) -> None:
    if await pool.fetchval("select exists (select 1 from room_fingerprints where room_id = $1)", room_id):
        return
    bssids = {
        ap["bssid"]: {"median_rssi": -48.0 - 2 * i, "band": ap["band"] or "5GHz", "count": 3, "label": "own"}
        for i, ap in enumerate(own)
    }
    bssids[NEIGHBOURS[0]] = {"median_rssi": -70.0, "band": "5GHz", "count": 3, "label": "hostel"}
    bssids[NEIGHBOURS[1]] = {"median_rssi": -78.0, "band": "2.4GHz", "count": 3, "label": "hostel"}
    await pool.execute(
        "insert into room_fingerprints (room_id, version, pattern) values ($1, 1, $2::jsonb)",
        room_id,
        json.dumps({"scans_count": 3, MARKER: True, "bssids": bssids}),
    )


async def sim_window(pool: asyncpg.Pool) -> asyncpg.Record | None:
    return await pool.fetchrow("select id, state, closes_at from attendance_windows where night = $1", SIM_NIGHT)


async def announce(redis, window_id, state: str) -> None:
    await redis.publish(
        keys.WINDOW_STATE_CHANNEL,
        json.dumps({"type": "window_state", "window_id": str(window_id), "state": state}),
    )


async def run(delay: float) -> None:
    settings = get_settings()
    api = f"http://localhost:{settings.API_PORT}"
    worker = settings.FACE_WORKER_URL.rstrip("/")
    worker_auth = {"Authorization": f"Bearer {settings.FACE_WORKER_TOKEN}"}
    pool = await asyncpg.create_pool(settings.DATABASE_URL, statement_cache_size=0, min_size=1, max_size=2)
    await redis_client.connect(settings)
    redis = redis_client.get_client()

    print("Making face crops (first run loads the face model, about 20 seconds)...")
    frames = make_frames()
    students = await students_and_rooms(pool)
    aps = await access_points(pool)
    if not students:
        sys.exit("No TEST students found. Run the seed first: uv run python ../scripts/seed.py")
    rooms = {s["room_id"]: s for s in students}

    # One open window on the simulator's own night.
    now = datetime.now(UTC)
    window_id = await pool.fetchval(
        """
        insert into attendance_windows (night, opens_at, closes_at, state) values ($1, $2, $3, 'open')
        on conflict (night) do update set state = 'open', opens_at = $2, closes_at = $3
        returning id
        """,
        SIM_NIGHT,
        now - timedelta(minutes=1),
        now + timedelta(minutes=45),
    )
    await announce(redis, window_id, "open")
    print("Window open for 45 minutes. Open the dashboard now: Tonight page.\n")

    async with httpx.AsyncClient(timeout=120) as client:
        phones: list[tuple[asyncpg.Record, Phone, str, str]] = []
        for index, student in enumerate(students):
            label, scenario = SCENARIOS[index % len(SCENARIOS)]
            if student["real_device"] or (student["enrolled_at"] and student["consent_version"] != MARKER):
                print(f"  {student['roll_number']}  skipped: already has a real device or enrolment")
                continue
            phone = Phone(student, api)
            await pool.execute("delete from devices where student_id = $1 and key_alias = $2", student["id"], MARKER)
            await pool.execute(
                "insert into devices (student_id, public_key, key_alias, active, enrolled_at) "
                "values ($1, $2, $3, true, now())",
                student["id"],
                phone.public_der(),
                MARKER,
            )
            await pool.execute(
                "update students set enrolled_at = now(), consent_at = now(), consent_version = $2 where id = $1",
                student["id"],
                MARKER,
            )
            enrol = await client.post(
                f"{worker}/enroll",
                headers=worker_auth,
                data={"student_id": str(student["id"])},
                files=[("frames", (f"{i}.jpg", b, "image/jpeg")) for i, b in enumerate(frames["enroll"])],
            )
            if enrol.status_code != 200:
                sys.exit(f"Face worker refused the enrolment for {student['roll_number']}: {enrol.text[:200]}")
            await ensure_fingerprint(pool, student["room_id"], aps.get(student["room_id"], []))
            phones.append((student, phone, label, scenario))
        await redis.publish(keys.ENROLLMENT_CHANNEL, json.dumps({"type": "enrollment_update", "enrolled": True}))
        print(f"Enrolled {len(phones)} students. Sending attendance, one every {delay:g}s:\n")

        for student, phone, label, scenario in phones:
            await asyncio.sleep(delay)
            name = f"{student['roll_number']} {student['name']:<14} room {student['room_number']}"
            if scenario == "no_show":
                print(f"  {name}  {label:<34} -> no attempt")
                continue
            own = aps.get(student["room_id"], [])
            if not own:
                print(f"  {name}  skipped: the room has no access point in the seed")
                continue
            ip = room_ip(student["subnet"])
            if scenario == "wrong_network":
                other = next((r for rid, r in rooms.items() if rid != student["room_id"]), None)
                ip = room_ip(other["subnet"]) if other else "203.0.113.9"
            status = await phone.nonce(client, room_ip(student["subnet"]))
            if status.get("state") != "open":
                print(f"  {name}  {label:<34} -> cannot mark, state is {status.get('state')}")
                continue
            # Still photos cannot turn a head, so pin the two actions a still face can pass.
            await redis.hset(keys.nonce_key(str(window_id), phone.student_id), "challenge", "blink,smile")
            live = frames["live_b"] if scenario == "wrong_person" else frames["live_a"]
            response = await phone.mark(
                client, ip, str(window_id), status["nonce"], live, scan_for(own, far=scenario == "far")
            )
            if response.status_code != 200:
                print(f"  {name}  {label:<34} -> HTTP {response.status_code} {response.text[:120]}")
                continue
            body = response.json()
            reasons = ", ".join(r["code"] for r in body.get("reasons", [])) or "-"
            score = f"{body['score']:.2f}" if body.get("score") is not None else " -  "
            print(f"  {name}  {label:<34} -> {body['verdict']:<12} score {score}  {reasons}")

    print("\nDone. Try the Review page, a room page, and Absentees.")
    print("Close the window with --close to see absentees after close. Clean up with --reset.")
    await pool.close()
    await redis_client.disconnect()


async def close() -> None:
    settings = get_settings()
    pool = await asyncpg.create_pool(settings.DATABASE_URL, statement_cache_size=0, min_size=1, max_size=1)
    window = await sim_window(pool)
    await pool.close()
    if window is None:
        sys.exit("There is no simulated window. Run the simulator first.")
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            f"http://localhost:{settings.API_PORT}/v1/windows/{window['id']}/close-now",
            headers={"Authorization": f"Bearer {admin_token(settings)}"},
            json={},
        )
    print(f"Close: HTTP {response.status_code} {response.text[:200]}")


async def reset() -> None:
    settings = get_settings()
    pool = await asyncpg.create_pool(settings.DATABASE_URL, statement_cache_size=0, min_size=1, max_size=1)
    await redis_client.connect(settings)
    redis = redis_client.get_client()
    window = await sim_window(pool)
    simulated = await pool.fetch(
        "select id from students where consent_version = $1 "
        "or id in (select student_id from devices where key_alias = $1)",
        MARKER,
    )
    ids = [row["id"] for row in simulated]

    if window is not None:
        await pool.execute(
            "delete from reviews where mark_id in (select id from attendance_marks where window_id = $1)", window["id"]
        )
        await pool.execute("delete from attendance_marks where window_id = $1", window["id"])
        await pool.execute("delete from attendance_windows where id = $1", window["id"])
        for student_id in ids:
            await redis.delete(
                keys.nonce_key(str(window["id"]), str(student_id)), keys.submit_rate_key(str(student_id))
            )
        await redis.delete(keys.window_state_key(str(window["id"])))
        await announce(redis, window["id"], "closed")

    worker = settings.FACE_WORKER_URL.rstrip("/")
    async with httpx.AsyncClient(timeout=30) as client:
        for student_id in ids:
            try:
                await client.delete(
                    f"{worker}/students/{student_id}/embedding",
                    headers={"Authorization": f"Bearer {settings.FACE_WORKER_TOKEN}"},
                )
            except httpx.HTTPError:
                print(f"  could not reach the face worker to delete the face for {student_id}")
    await pool.execute("delete from devices where key_alias = $1", MARKER)
    await pool.execute(
        "update students set enrolled_at = null, consent_at = null, consent_version = null where consent_version = $1",
        MARKER,
    )
    await pool.execute("delete from room_fingerprints where pattern ? $1", MARKER)
    await redis.publish(keys.ENROLLMENT_CHANNEL, json.dumps({"type": "enrollment_update", "enrolled": False}))
    print(f"Removed the simulated window, {len(ids)} simulated enrolments, their devices, faces and fingerprints.")
    await pool.close()
    await redis_client.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate a night of attendance without a phone.")
    parser.add_argument("--delay", type=float, default=3.0, help="seconds between students (default 3)")
    parser.add_argument("--close", action="store_true", help="close the simulated window")
    parser.add_argument("--reset", action="store_true", help="remove everything the simulator created")
    args = parser.parse_args()
    if args.reset:
        asyncio.run(reset())
    elif args.close:
        asyncio.run(close())
    else:
        asyncio.run(run(args.delay))


if __name__ == "__main__":
    main()
