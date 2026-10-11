"""Container health checks, run by Docker: `python -m app.healthcheck api|scheduler`.

Exit 0 is healthy, anything else is not. The API answers for itself over HTTP. The scheduler has no port, so
its health is the heartbeat it writes to Redis every 15 seconds.
"""

from __future__ import annotations

import sys
import urllib.request
from datetime import UTC, datetime

import redis

from app.config import get_settings

HEARTBEAT_MAX_AGE_SECONDS = 60


def api_healthy() -> bool:
    """The API process answers. A degraded database or Redis is reported by /v1/health, not by restarting it."""
    with urllib.request.urlopen("http://127.0.0.1:8000/v1/health", timeout=4) as response:
        return response.status == 200


def scheduler_healthy() -> bool:
    client = redis.Redis.from_url(get_settings().REDIS_URL, socket_connect_timeout=4, socket_timeout=4)
    try:
        beat = client.get("scheduler:heartbeat")
    finally:
        client.close()
    if beat is None:
        return False
    age = (datetime.now(UTC) - datetime.fromisoformat(beat.decode())).total_seconds()
    return age <= HEARTBEAT_MAX_AGE_SECONDS


def main(argv: list[str]) -> int:
    checks = {"api": api_healthy, "scheduler": scheduler_healthy}
    if len(argv) != 2 or argv[1] not in checks:
        print("usage: python -m app.healthcheck api|scheduler", file=sys.stderr)
        return 2
    try:
        return 0 if checks[argv[1]]() else 1
    except Exception as exc:
        print(f"unhealthy: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
