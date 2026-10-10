"""Scores a submission that passed every gate (Phase 9 sections 1 to 8).

The face worker call and the local inputs are fetched at the same time. The scorers and fusion are then
pure functions over those inputs.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.db.queries import rooms as rooms_q
from app.services.verification import face as face_client
from app.services.verification import scorers
from app.services.verification.fusion import Verdict, fuse
from app.services.verification.network import get_network_verifier
from app.services.verification.runner import Submission


@dataclass(frozen=True)
class ScoringOutcome:
    verdict: Verdict
    scorers: dict[str, scorers.ScorerResult]
    frames_path: str | None
    timings_ms: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class _LocalInputs:
    pattern: dict[str, Any] | None
    scan_count: int
    room_map: set[str]
    own: set[str]


def _lower(bssid: str) -> str:
    return bssid.lower()


async def _local_inputs(submission: Submission) -> _LocalInputs:
    room_id = UUID(submission.room.room_id)
    row = await rooms_q.get_latest_room_fingerprint(submission.pool, room_id)
    pattern = None
    scan_count = 0
    if row is not None:
        pattern = json.loads(row["pattern"]) if isinstance(row["pattern"], str) else row["pattern"]
        scan_count = int(pattern.get("scans_count", 0))

    all_aps = await rooms_q.list_all_access_points(submission.pool)
    room_map = {_lower(r["bssid"]) for r in all_aps}
    own = {_lower(r["bssid"]) for r in all_aps if str(r["room_id"]) == submission.room.room_id}
    return _LocalInputs(pattern=pattern, scan_count=scan_count, room_map=room_map, own=own)


async def score_submission(submission: Submission) -> ScoringOutcome:
    payload = submission.payload
    settings = submission.settings
    tags = [frame.tag for frame in payload.frames]
    hashes = [frame.sha256 for frame in payload.frames]

    started = time.perf_counter()
    face_started = time.perf_counter()
    face_coro = face_client.verify_frames(
        settings,
        student_id=payload.student_id,
        window_id=payload.window_id,
        mark_id=submission.mark_id,
        frames=submission.frames,
        hashes=hashes,
        tags=tags,
    )
    local_started = time.perf_counter()
    face_result, local = await asyncio.gather(face_coro, _local_inputs(submission))
    face_ms = (time.perf_counter() - face_started) * 1000
    local_ms = (time.perf_counter() - local_started) * 1000

    frames = face_result.frames if face_result else []
    antispoof_available = face_result.antispoof_available if face_result else False
    frames_path = face_result.frames_path if face_result else None

    scan = {_lower(net.bssid): net.rssi for net in payload.wifi.scan}
    scan[_lower(payload.wifi.connected.bssid)] = payload.wifi.connected.rssi

    fuse_started = time.perf_counter()
    measured = get_network_verifier(settings.NETWORK_VERIFY_MODE).measured_rssi(
        submission.room, submission.client_ip, payload.wifi.connected.bssid
    )
    results = {
        "face": scorers.face_score(frames, settings),
        "liveness": scorers.liveness_score(
            [scorers.ChallengeStep(step.action, step.started_ms, step.detected_ms) for step in payload.challenge],
            frames,
            antispoof_available,
            settings,
        ),
        "fingerprint": scorers.fingerprint_score(
            scan,
            payload.wifi.scan_age_ms,
            local.pattern,
            local.scan_count,
            local.room_map,
            settings,
        ),
        "own_ap": scorers.own_ap_score(scan, local.own, settings),
        "ap_agreement": scorers.ap_agreement_score(measured, payload.wifi.connected.rssi, settings),
    }
    verdict = fuse(results, settings)
    fuse_ms = (time.perf_counter() - fuse_started) * 1000

    return ScoringOutcome(
        verdict=verdict,
        scorers=results,
        frames_path=frames_path,
        timings_ms={
            "face_worker": round(face_ms, 2),
            "local_inputs": round(local_ms, 2),
            "fusion": round(fuse_ms, 2),
            "total": round((time.perf_counter() - started) * 1000, 2),
        },
    )
