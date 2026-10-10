"""Hourly deletion of nightly frames older than the retention limit (Phase 5, section 8)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import httpx

from worker.config import settings

logger = logging.getLogger(__name__)

ROOT_FOLDER = "frames"
PAGE_SIZE = 1000

# When the last run finished without any error. Not updated by a run that failed part-way.
last_cleanup_time: datetime | None = None


def _headers() -> dict[str, str]:
    key = settings.SUPABASE_SERVICE_ROLE_KEY
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}


async def _list(client: httpx.AsyncClient, base_url: str, prefix: str) -> list[dict]:
    """List every entry directly under `prefix`. Folders come back without a `created_at`."""
    entries: list[dict] = []
    offset = 0
    while True:
        resp = await client.post(
            f"{base_url}/storage/v1/object/list/{settings.FRAMES_BUCKET}",
            headers=_headers(),
            json={"prefix": prefix, "limit": PAGE_SIZE, "offset": offset, "sortBy": {"column": "name", "order": "asc"}},
        )
        resp.raise_for_status()
        page = resp.json()
        entries.extend(page)
        if len(page) < PAGE_SIZE:
            return entries
        offset += PAGE_SIZE


def _created(entry: dict) -> datetime | None:
    raw = entry.get("created_at") or entry.get("updated_at")
    return datetime.fromisoformat(raw.replace("Z", "+00:00")) if raw else None


async def run_frame_cleanup() -> int:
    """Delete every `frames/<window_id>/<mark_id>/` folder whose newest file is past the retention limit.

    Storage folders have no timestamp of their own, so age is read from the files inside. The matching
    attendance marks have `frames_path` cleared so nothing points at deleted evidence. Only counts and
    folder paths are logged, never file contents.
    """
    global last_cleanup_time

    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        logger.error("Supabase credentials missing; frame cleanup cannot run")
        return 0

    base_url = settings.SUPABASE_URL.rstrip("/")
    cutoff = datetime.now(UTC) - timedelta(hours=settings.FRAME_RETENTION_HOURS)
    folders_removed = 0

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            for window in await _list(client, base_url, ROOT_FOLDER):
                window_prefix = f"{ROOT_FOLDER}/{window['name']}"
                for mark in await _list(client, base_url, window_prefix):
                    mark_prefix = f"{window_prefix}/{mark['name']}"
                    files = [f for f in await _list(client, base_url, mark_prefix) if _created(f)]
                    if not files or max(_created(f) for f in files) >= cutoff:
                        continue

                    resp = await client.request(
                        "DELETE",
                        f"{base_url}/storage/v1/object/{settings.FRAMES_BUCKET}",
                        headers=_headers(),
                        json={"prefixes": [f"{mark_prefix}/{f['name']}" for f in files]},
                    )
                    resp.raise_for_status()

                    marks = await client.patch(
                        f"{base_url}/rest/v1/attendance_marks",
                        headers=_headers(),
                        params={"frames_path": f"eq.{mark_prefix}/"},
                        json={"frames_path": None},
                    )
                    marks.raise_for_status()
                    folders_removed += 1
    except Exception as exc:
        logger.error("Frame cleanup stopped early: %s", exc)
        return folders_removed

    last_cleanup_time = datetime.now(UTC)
    logger.info("Frame cleanup finished. Folders removed: %d", folders_removed)
    return folders_removed


def get_last_cleanup_time() -> datetime | None:
    """When the retention cleanup last completed without error."""
    return last_cleanup_time
