"""Room Wi-Fi fingerprint pattern builder, submission, and management."""

from __future__ import annotations

import json
import logging
import statistics
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import asyncpg

from app.db.queries import rooms as rooms_q
from app.errors import AppError
from app.schemas.rooms import SubmitRoomScansRequest
from app.services import audit

logger = logging.getLogger("nightroll.fingerprint")

FINGERPRINT_EXISTS_MESSAGE = (
    "Room already has a fingerprint. A warden must reset it before a new scan can be submitted."
)


async def submit_room_fingerprint(
    pool: asyncpg.Pool,
    *,
    room_id: UUID,
    student_id: UUID,
    payload: SubmitRoomScansRequest,
) -> dict[str, Any]:
    # 1. Verify room exists and check reset status
    room = await rooms_q.get_room_with_reset_status(pool, room_id)
    if room is None:
        raise AppError(code="NOT_FOUND", status_code=404, message="Room not found")

    # Verify student belongs to this room
    student_room_id = await rooms_q.get_student_room_id(pool, student_id)
    if student_room_id != room_id:
        raise AppError(code="FORBIDDEN", status_code=403, message="Student does not belong to this room")

    # 7.1 Reject if the room already has a fingerprint and no reset is pending
    existing_fp = await rooms_q.get_latest_room_fingerprint(pool, room_id)
    if existing_fp is not None and not room["fingerprint_reset_pending"]:
        raise AppError(
            code="FINGERPRINT_EXISTS",
            status_code=400,
            message=FINGERPRINT_EXISTS_MESSAGE,
        )

    # 7.2 Require at least 3 scans
    if len(payload.scans) < 3:
        raise AppError(
            code="INSUFFICIENT_SCANS",
            status_code=400,
            message=f"At least 3 scans are required to build a fingerprint, received {len(payload.scans)}",
        )

    # Fetch room's own access points from database
    room_aps = await rooms_q.list_access_points(pool, room_id)
    own_bssids = {row["bssid"].lower() for row in room_aps}

    # Without a mapped access point there is nothing to anchor the fingerprint to.
    if not own_bssids:
        raise AppError(
            code="ROOM_NOT_MAPPED",
            status_code=409,
            message="This room has no access point in the room map yet. Ask the warden to add it.",
        )

    # 7.2 The room's own access point must appear in every scan
    for idx, scan in enumerate(payload.scans):
        scan_bssids = {net.bssid.strip().lower() for net in scan.networks}
        if not (scan_bssids & own_bssids):
            raise AppError(
                code="MISSING_OWN_AP",
                status_code=400,
                message=f"Room's own access point was not detected in scan {idx + 1}. Stand closer to the room's AP.",
            )

    # 7.3 & 7.4 Build the pattern and label each BSSID
    # Fetch all access points across the hostel to label own vs hostel vs unknown
    all_aps = await rooms_q.list_all_access_points(pool)
    hostel_ap_map: dict[str, UUID] = {row["bssid"].lower(): row["room_id"] for row in all_aps}

    # Aggregate RSSI readings and band across all scans
    rssi_by_bssid: dict[str, list[float]] = {}
    band_by_bssid: dict[str, str] = {}

    for scan in payload.scans:
        seen_in_scan: set[str] = set()
        for net in scan.networks:
            bssid = net.bssid.strip().lower()
            if bssid in seen_in_scan:
                continue  # count at most once per spot scan
            seen_in_scan.add(bssid)

            rssi_by_bssid.setdefault(bssid, []).append(net.rssi)
            # Store band (normalize e.g. 2.4GHz / 5GHz)
            band_by_bssid[bssid] = net.band

    pattern_bssids: dict[str, dict[str, Any]] = {}
    for bssid, rssi_list in rssi_by_bssid.items():
        med_rssi = round(float(statistics.median(rssi_list)), 1)
        count = len(rssi_list)
        band = band_by_bssid.get(bssid, "2.4GHz")

        # Label: own, hostel, or unknown
        if bssid in own_bssids:
            label = "own"
        elif bssid in hostel_ap_map:
            label = "hostel"
        else:
            label = "unknown"

        pattern_bssids[bssid] = {
            "median_rssi": med_rssi,
            "band": band,
            "count": count,
            "label": label,
        }

    pattern = {
        "bssids": pattern_bssids,
        "scans_count": len(payload.scans),
    }

    # 7.5 Store as a new version in room_fingerprints and write an audit row
    next_version = (existing_fp["version"] + 1) if existing_fp else 1

    async with pool.acquire() as conn:
        async with conn.transaction():
            try:
                row = await conn.fetchrow(
                    """
                    insert into room_fingerprints (room_id, version, pattern, created_at)
                    values ($1, $2, $3::jsonb, now())
                    returning id, created_at
                    """,
                    room_id,
                    next_version,
                    json.dumps(pattern),
                )
            except asyncpg.UniqueViolationError as exc:
                # Another roommate submitted at the same moment and won.
                raise AppError(
                    code="FINGERPRINT_EXISTS",
                    status_code=400,
                    message=FINGERPRINT_EXISTS_MESSAGE,
                ) from exc
            # Clear reset pending flag
            await conn.execute(
                "update rooms set fingerprint_reset_pending = false where id = $1",
                room_id,
            )
            # Audit log
            await audit.write(
                conn,
                actor=str(student_id),
                action="room.fingerprint_captured",
                target_id=str(room_id),
                payload={
                    "version": next_version,
                    "ap_count": len(pattern_bssids),
                    "scans_count": len(payload.scans),
                },
            )

    return {
        "id": row["id"],
        "room_id": room_id,
        "version": next_version,
        "pattern": pattern,
        "ap_count": len(pattern_bssids),
        "created_at": row["created_at"].isoformat(),
        "age_seconds": 0,
        "reset_pending": False,
    }


async def reset_room_fingerprint(
    pool: asyncpg.Pool,
    *,
    room_id: UUID,
    actor_id: str,
) -> dict[str, Any]:
    room = await rooms_q.get_room(pool, room_id)
    if room is None:
        raise AppError(code="NOT_FOUND", status_code=404, message="Room not found")

    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("update rooms set fingerprint_reset_pending = true where id = $1", room_id)
            await audit.write(
                conn,
                actor=actor_id,
                action="room.fingerprint_reset",
                target_id=str(room_id),
                payload={"room_number": room["number"]},
            )

    return {"reset_pending": True, "room_id": room_id}


async def get_room_fingerprint_status(
    pool: asyncpg.Pool,
    room_id: UUID,
) -> dict[str, Any]:
    room = await rooms_q.get_room_with_reset_status(pool, room_id)
    if room is None:
        raise AppError(code="NOT_FOUND", status_code=404, message="Room not found")

    fp = await rooms_q.get_latest_room_fingerprint(pool, room_id)
    if fp is None:
        raise AppError(code="NOT_FOUND", status_code=404, message="No fingerprint captured for this room yet")

    pattern = fp["pattern"]
    if isinstance(pattern, str):
        pattern = json.loads(pattern)

    created_at = fp["created_at"]
    age_seconds = int((datetime.now(UTC) - created_at).total_seconds())
    bssids = pattern.get("bssids", {})

    return {
        "id": fp["id"],
        "room_id": room_id,
        "version": fp["version"],
        "pattern": pattern,
        "ap_count": len(bssids),
        "created_at": created_at.isoformat(),
        "age_seconds": max(0, age_seconds),
        "reset_pending": room["fingerprint_reset_pending"],
    }
