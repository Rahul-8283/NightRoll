"""What the System page shows and what the alert banner warns about (Phase 12, tasks 6.4 and 6.5)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from importlib.metadata import PackageNotFoundError, version

import asyncpg
import httpx
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app import metrics
from app.config import Settings
from app.db import pool as db_pool
from app.db.queries import system as system_q
from app.db.queries import windows as windows_q
from app.redis import client as redis_client
from app.schemas.dashboard import WindowBrief
from app.schemas.system import (
    AlertOut,
    FaceWorkerOut,
    GateFailureOut,
    JobOut,
    LatencyOut,
    SchedulerOut,
    ServiceOut,
    SystemOut,
    TonightStatsOut,
)
from app.services import housekeeping, ops
from app.services.verification.reasons import GATE_FAILURE_CODES, reason

# More than this share of the last five minutes' attempts rejected raises an alert, once there are enough
# attempts for a share to mean anything.
REJECTION_RATE_LIMIT = 0.20
REJECTION_WINDOW = timedelta(minutes=5)
REJECTION_MIN_ATTEMPTS = 5

FACE_HEALTH_CACHE_SECONDS = 5.0
FACE_HEALTH_TIMEOUT_SECONDS = 3.0


@dataclass(frozen=True)
class FaceHealth:
    reachable: bool
    ready: bool = False
    antispoof_available: bool = False
    model_version: str | None = None
    last_cleanup: datetime | None = None
    latency_ms: float | None = None


_face_cache: tuple[float, str, FaceHealth] | None = None


async def face_health(settings: Settings) -> FaceHealth:
    """Ask the face worker how it is. Every warden's banner asks, so the answer is kept for a few seconds."""
    global _face_cache
    if (
        _face_cache
        and time.monotonic() - _face_cache[0] < FACE_HEALTH_CACHE_SECONDS
        and _face_cache[1] == settings.FACE_WORKER_URL
    ):
        return _face_cache[2]
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=FACE_HEALTH_TIMEOUT_SECONDS) as client:
            resp = await client.get(
                f"{settings.FACE_WORKER_URL.rstrip('/')}/health",
                headers={"Authorization": f"Bearer {settings.FACE_WORKER_TOKEN}"},
            )
        body = resp.json() if resp.status_code == 200 else {}
        health = FaceHealth(
            reachable=resp.status_code == 200,
            ready=bool(body.get("ready")),
            antispoof_available=bool(body.get("antispoof_available")),
            model_version=body.get("model_version"),
            last_cleanup=datetime.fromisoformat(body["last_cleanup"]) if body.get("last_cleanup") else None,
            latency_ms=round((time.perf_counter() - started) * 1000, 1),
        )
    except (httpx.HTTPError, ValueError):
        health = FaceHealth(reachable=False)
    _face_cache = (time.monotonic(), settings.FACE_WORKER_URL, health)
    return health


def _app_version() -> str:
    try:
        return version("nightroll-backend")
    except PackageNotFoundError:
        return "0.1.0"


async def _heartbeat(redis: Redis) -> tuple[datetime | None, float | None]:
    try:
        beat = await ops.last_heartbeat(redis)
    except (RedisError, OSError, ValueError):
        return None, None
    if beat is None:
        return None, None
    return beat, max(0.0, (datetime.now(UTC) - beat).total_seconds())


def build_alerts(
    *,
    window_open: bool,
    face: FaceHealth,
    heartbeat_age: float | None,
    attempts_5m: int,
    rejected_5m: int,
) -> list[AlertOut]:
    """The three conditions a warden must hear about. Pure, so each rule can be tested on its own."""
    alerts: list[AlertOut] = []
    if window_open and not (face.reachable and face.ready):
        alerts.append(
            AlertOut(
                code="FACE_WORKER_DOWN",
                severity="critical",
                message="The face check is down while attendance is open. Students are being sent to the "
                "ground-floor scanner. Restart the face worker.",
            )
        )
    if not ops.heartbeat_is_fresh(heartbeat_age):
        seen = "has not been seen" if heartbeat_age is None else f"last checked in {int(heartbeat_age)} seconds ago"
        alerts.append(
            AlertOut(
                code="SCHEDULER_STALE",
                severity="critical",
                message=f"The scheduler {seen}. Windows may not open or close on time. Restart the scheduler.",
            )
        )
    if attempts_5m >= REJECTION_MIN_ATTEMPTS and rejected_5m / attempts_5m > REJECTION_RATE_LIMIT:
        percent = round(100 * rejected_5m / attempts_5m)
        alerts.append(
            AlertOut(
                code="HIGH_REJECTION_RATE",
                severity="warning",
                message=f"{percent}% of the last {attempts_5m} attempts in five minutes were rejected. "
                "Check a router or the face worker.",
            )
        )
    return alerts


async def alerts(settings: Settings, pool: asyncpg.Pool, redis: Redis) -> list[AlertOut]:
    now = datetime.now(UTC)
    window = await windows_q.current(pool, now)
    attempts, rejected = await system_q.recent_attempts(pool, now - REJECTION_WINDOW)
    _, age = await _heartbeat(redis)
    return build_alerts(
        window_open=window is not None and window["state"] == "open",
        face=await face_health(settings),
        heartbeat_age=age,
        attempts_5m=attempts,
        rejected_5m=rejected,
    )


def _ms(seconds: float | None) -> float | None:
    return None if seconds is None else round(seconds * 1000, 1)


def _latency() -> LatencyOut:
    return LatencyOut(
        requests_p50_ms=_ms(metrics.http_latency.quantile(0.5)),
        requests_p95_ms=_ms(metrics.http_latency.quantile(0.95)),
        verify_p95_ms=_ms(metrics.http_latency.quantile(0.95, route="/v1/attendance/verify")),
        face_worker_p95_ms=_ms(metrics.face_latency.quantile(0.95)),
    )


async def _jobs(redis: Redis, face: FaceHealth) -> list[JobOut]:
    jobs = [JobOut(name="Frame cleanup", last_run=face.last_cleanup, detail="Runs hourly in the face worker")]
    for name, job in (
        ("Enrollment code cleanup", housekeeping.CODE_CLEANUP_JOB),
        ("Room health", housekeeping.ROOM_HEALTH_JOB),
    ):
        record = await ops.last_job(redis, job)
        if record is None:
            jobs.append(JobOut(name=name))
            continue
        detail = (
            f"{record['removed']} removed" if "removed" in record else f"{len(record.get('flagged', {}))} rooms flagged"
        )
        jobs.append(JobOut(name=name, last_run=datetime.fromisoformat(record["at"]), detail=detail))
    return jobs


async def overview(settings: Settings, pool: asyncpg.Pool, redis: Redis) -> SystemOut:
    now = datetime.now(UTC)
    window = await windows_q.current(pool, now)
    face = await face_health(settings)
    beat, age = await _heartbeat(redis)
    attempts_5m, rejected_5m = await system_q.recent_attempts(pool, now - REJECTION_WINDOW)

    verdicts = {name: 0 for name in system_q.ATTEMPT_VERDICTS}
    gate_failures: list[GateFailureOut] = []
    if window is not None:
        verdicts.update(await system_q.verdict_counts(pool, window["id"]))
        for code, count in sorted(
            (await system_q.rejection_reasons(pool, window["id"])).items(), key=lambda kv: -kv[1]
        ):
            if code in GATE_FAILURE_CODES:
                gate_failures.append(GateFailureOut(reason=code, message=reason(code).message, count=count))

    return SystemOut(
        generated_at=now,
        app_env=settings.APP_ENV,
        version=_app_version(),
        relaxed_settings=settings.relaxed_settings() if settings.APP_ENV not in ("pilot", "production") else [],
        database=ServiceOut(status="ok" if await db_pool.ping() else "down"),
        redis=ServiceOut(status="ok" if await redis_client.ping() else "down"),
        face_worker=FaceWorkerOut(
            status="ok" if face.reachable and face.ready else ("degraded" if face.reachable else "down"),
            detail=None if face.reachable else "The face worker did not answer",
            ready=face.ready,
            antispoof_available=face.antispoof_available,
            model_version=face.model_version,
            latency_ms=face.latency_ms,
        ),
        scheduler=SchedulerOut(
            status="ok" if ops.heartbeat_is_fresh(age) else ("down" if beat is None else "degraded"),
            detail=None if beat else "No heartbeat recorded",
            last_heartbeat=beat,
            age_seconds=None if age is None else round(age, 1),
        ),
        window=None
        if window is None
        else WindowBrief(
            id=window["id"],
            night=window["night"],
            opens_at=window["opens_at"],
            closes_at=window["closes_at"],
            state=window["state"],
        ),
        tonight=TonightStatsOut(
            attempts=sum(verdicts.values()),
            verdicts=verdicts,
            gate_failures=gate_failures,
            rejection_rate_5m=None if attempts_5m == 0 else round(rejected_5m / attempts_5m, 3),
            attempts_5m=attempts_5m,
        ),
        latency=_latency(),
        websocket_connections=int(metrics.websocket_connections.values.get((), 0)),
        jobs=await _jobs(redis, face),
        alerts=build_alerts(
            window_open=window is not None and window["state"] == "open",
            face=face,
            heartbeat_age=age,
            attempts_5m=attempts_5m,
            rejected_5m=rejected_5m,
        ),
    )
