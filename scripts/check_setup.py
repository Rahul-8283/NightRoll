"""Phase 0 setup check. Verifies the local setup and external connections without printing secrets.

Run from the backend folder so the backend's packages are available:

    cd backend && uv run python ../scripts/check_setup.py

Exit code 1 if any check fails. Warnings do not fail the run.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE_NAME = "com.zerolatency.nightroll"

REQUIRED = {
    "backend/.env": [
        "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_JWT_SECRET", "DATABASE_URL",
        "REDIS_URL", "FACE_WORKER_TOKEN", "PLAY_INTEGRITY_PACKAGE_NAME",
    ],
    "face/.env": ["FACE_WORKER_TOKEN", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "FRAMES_BUCKET"],
    "dashboard/.env": ["VITE_API_BASE_URL", "VITE_SUPABASE_URL", "VITE_SUPABASE_ANON_KEY"],
    "app/.env": ["EXPO_PUBLIC_API_BASE_URL"],
}

results: list[tuple[str, str, str]] = []  # (status, name, detail)


def record(status: str, name: str, detail: str = "") -> None:
    results.append((status, name, detail))


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def check_env_files() -> dict[str, dict[str, str]]:
    loaded: dict[str, dict[str, str]] = {}
    for rel, keys in REQUIRED.items():
        path = ROOT / rel
        if not path.exists():
            record("FAIL", f"{rel} exists", "copy the matching .env.example and fill it in")
            continue
        values = parse_env(path)
        loaded[rel] = values
        missing = [k for k in keys if not values.get(k)]
        if missing:
            record("FAIL", f"{rel} has required values", "empty: " + ", ".join(missing))
        else:
            record("PASS", f"{rel} has required values", f"{len(keys)} checked, none printed")
    return loaded


def check_values(env: dict[str, dict[str, str]]) -> None:
    backend = env.get("backend/.env", {})
    face = env.get("face/.env", {})

    url = backend.get("REDIS_URL", "")
    if url and not url.startswith("rediss://"):
        record("FAIL", "REDIS_URL uses TLS", "must start with rediss://")
    elif url:
        record("PASS", "REDIS_URL uses TLS", "rediss://")

    token = backend.get("FACE_WORKER_TOKEN", "")
    if token and len(token) < 32:
        record("FAIL", "FACE_WORKER_TOKEN length", "must be at least 32 characters")
    elif token and token != face.get("FACE_WORKER_TOKEN", ""):
        record("FAIL", "FACE_WORKER_TOKEN matches face/.env", "the two values differ")
    elif token:
        record("PASS", "FACE_WORKER_TOKEN length and match", "32+ characters, same in both services")

    if backend.get("PLAY_INTEGRITY_PACKAGE_NAME") not in (None, "", PACKAGE_NAME):
        record("FAIL", "PLAY_INTEGRITY_PACKAGE_NAME", f"must be {PACKAGE_NAME}")
    elif backend.get("PLAY_INTEGRITY_PACKAGE_NAME"):
        record("PASS", "PLAY_INTEGRITY_PACKAGE_NAME", PACKAGE_NAME)

    service_role = backend.get("SUPABASE_SERVICE_ROLE_KEY", "")
    dashboard = env.get("dashboard/.env", {})
    if service_role and service_role in dashboard.values():
        record("FAIL", "service role key kept out of dashboard", "the dashboard has the service role key")
    elif service_role:
        record("PASS", "service role key kept out of dashboard")

    if backend.get("PLAY_INTEGRITY_ENFORCE", "false").lower() == "true" and backend.get("APP_ENV") == "local":
        record("WARN", "PLAY_INTEGRITY_ENFORCE", "true while APP_ENV=local; fine if the demo is ready")

    creds = ROOT / "backend" / backend.get("GOOGLE_APPLICATION_CREDENTIALS", "./secrets/google-service-account.json").lstrip("./")
    if not creds.exists():
        record("FAIL", "Google service account file", "put it at backend/secrets/google-service-account.json")
    else:
        try:
            data = json.loads(creds.read_text(encoding="utf-8"))
            if data.get("type") == "service_account":
                record("PASS", "Google service account file", "valid service account JSON, contents not printed")
            else:
                record("FAIL", "Google service account file", "JSON is not a service account key")
        except (OSError, ValueError):
            record("FAIL", "Google service account file", "not valid JSON")

    local_rooms = ROOT / "config" / "rooms.local.json"
    if local_rooms.exists():
        record("PASS", "config/rooms.local.json exists")
    else:
        record("WARN", "config/rooms.local.json", "not created yet; copy config/rooms.example.json and fill it in")


async def check_redis(url: str) -> None:
    try:
        import redis.asyncio as redis_async
    except ImportError:
        record("WARN", "Redis PING", "run this script with: cd backend && uv run python ../scripts/check_setup.py")
        return
    client = redis_async.from_url(url, socket_timeout=5, socket_connect_timeout=5)
    try:
        pong = await client.ping()
        record("PASS" if pong else "FAIL", "Redis PING over TLS", "PONG" if pong else "no reply")
    except Exception as exc:  # report the class of error only; messages can echo the URL
        record("FAIL", "Redis PING over TLS", type(exc).__name__)
    finally:
        await client.aclose()


async def check_database(url: str) -> None:
    try:
        import asyncpg
    except ImportError:
        record("WARN", "pgvector extension", "run this script from the backend folder")
        return
    try:
        conn = await asyncpg.connect(url, timeout=10, statement_cache_size=0)
        try:
            found = await conn.fetchval("select extname from pg_extension where extname = 'vector'")
        finally:
            await conn.close()
        if found:
            record("PASS", "pgvector extension enabled", "vector")
        else:
            record("FAIL", "pgvector extension enabled", "enable it in Supabase: Database, Extensions")
    except Exception as exc:
        record("FAIL", "Supabase database connection", type(exc).__name__)


def check_supabase(env: dict[str, str]) -> None:
    try:
        import httpx
    except ImportError:
        record("WARN", "Supabase REST and Storage", "run this script from the backend folder")
        return
    base = env.get("SUPABASE_URL", "").rstrip("/")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY", "")
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    try:
        rest = httpx.get(f"{base}/rest/v1/", headers=headers, timeout=10)
        record("PASS" if rest.status_code == 200 else "FAIL", "Supabase REST reachable", f"HTTP {rest.status_code}")
        bucket = httpx.get(f"{base}/storage/v1/bucket/{env.get('FRAMES_BUCKET', 'frames')}", headers=headers, timeout=10)
        if bucket.status_code != 200:
            record("FAIL", "frames bucket exists", f"HTTP {bucket.status_code}")
        elif bucket.json().get("public"):
            record("FAIL", "frames bucket is private", "the bucket is public; turn public access off")
        else:
            record("PASS", "frames bucket exists and is private")
    except httpx.HTTPError as exc:
        record("FAIL", "Supabase REST and Storage", type(exc).__name__)


def check_git() -> None:
    try:
        tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        record("WARN", "git secret scan", "not a git checkout")
        return
    bad = [f for f in tracked.splitlines()
           if f.endswith(".env") or "/secrets/" in f or f.endswith("google-services.json")]
    if bad:
        record("FAIL", "no secret files tracked by git", ", ".join(bad))
    else:
        record("PASS", "no secret files tracked by git")


def check_tools() -> None:
    wanted = {
        "uv": ["--version"],
        "node": ["--version"],
        "npm": ["--version"],
        "docker": ["--version"],
        "supabase": ["--version"],
        "java": ["-version"],
    }
    for tool, args in wanted.items():
        if tool == "supabase" and not shutil.which(tool):
            # the team runs the CLI through npx, which uses only the npm cache
            proc = subprocess.run(["npx", "--no-install", "supabase", *args], capture_output=True, text=True)
            text = (proc.stdout or "").strip()
            if proc.returncode == 0 and text:
                record("PASS", "supabase CLI (npx) installed", text.splitlines()[0][:60])
            else:
                record("WARN", "supabase CLI (npx) installed", "run: npx supabase --version")
            continue
        if not shutil.which(tool):
            record("WARN", f"{tool} installed", "missing; see phase 0 section 13")
            continue
        proc = subprocess.run([tool, *args], capture_output=True, text=True)
        # java prints its version to stderr, and the macOS stub exits non-zero with a message
        text = (proc.stdout or proc.stderr or "").strip()
        if proc.returncode != 0 or not text:
            record("WARN", f"{tool} installed", "stub or broken install; see phase 0 section 13")
            continue
        record("PASS", f"{tool} installed", text.splitlines()[0][:60])
    node_major = subprocess.run(["node", "-p", "process.versions.node.split('.')[0]"],
                                capture_output=True, text=True).stdout.strip()
    if node_major and node_major != "20":
        record("WARN", "Node major version", f"{node_major}; the team pins Node 20 in .nvmrc")


REQUIRED_PATHS = [
    "app/.nvmrc", "app/.env.example",
    "backend/.python-version", "backend/.env.example", "backend/README.md",
    "face/.python-version", "face/.env.example", "face/models/README.md", "face/README.md",
    "dashboard/.nvmrc", "dashboard/.env.example", "dashboard/README.md",
    "supabase/README.md", "supabase/migrations/README.md",
    "infra/docker-compose.yml", "infra/README.md",
    "config/rooms.example.json", "config/README.md",
    "scripts/README.md", "scripts/spikes/RESULTS.md",
    "docs/PRD.md", "docs/TRD.md", "docs/architecture.md",
    "phase/phase_0.md", "CLAUDE.md", "LICENSE", "README.md", ".gitignore",
]


def check_structure() -> None:
    missing = [p for p in REQUIRED_PATHS if not (ROOT / p).exists()]
    if missing:
        record("FAIL", "folder structure complete", "missing: " + ", ".join(missing))
    else:
        record("PASS", "folder structure complete", f"{len(REQUIRED_PATHS)} required files present")


async def main() -> int:
    env = check_env_files()
    check_values(env)
    check_structure()
    check_git()
    check_tools()

    backend = env.get("backend/.env", {})
    if backend.get("REDIS_URL"):
        await check_redis(backend["REDIS_URL"])
    if backend.get("DATABASE_URL"):
        await check_database(backend["DATABASE_URL"])
    if backend.get("SUPABASE_URL") and backend.get("SUPABASE_SERVICE_ROLE_KEY"):
        check_supabase(backend)

    width = max(len(name) for _, name, _ in results)
    for status, name, detail in results:
        print(f"[{status}] {name.ljust(width)}  {detail}".rstrip())
    fails = sum(1 for status, _, _ in results if status == "FAIL")
    warns = sum(1 for status, _, _ in results if status == "WARN")
    print(f"\n{fails} failed, {warns} warnings")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
