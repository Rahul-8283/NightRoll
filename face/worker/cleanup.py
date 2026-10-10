"""Hourly frame deletion and retention cleanup job."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
import httpx

from worker.config import settings

logger = logging.getLogger(__name__)

# Track the timestamp of the last successful cleanup run
last_cleanup_time: datetime | None = None


async def run_frame_cleanup() -> int:
    """Find and delete frame folders older than FRAME_RETENTION_HOURS.

    1. Enumerate objects in Supabase Storage 'frames' bucket.
    2. Remove objects older than the retention threshold.
    3. Clear frames_path on the corresponding attendance_marks.
    4. Log the count of removed folders (never logging file contents).
    """
    global last_cleanup_time

    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        logger.warning("Supabase credentials missing, skipping cleanup run")
        last_cleanup_time = datetime.now(timezone.utc)
        return 0

    base_url = settings.SUPABASE_URL.rstrip("/")
    key = settings.SUPABASE_SERVICE_ROLE_KEY
    bucket = settings.FRAMES_BUCKET
    retention_cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.FRAME_RETENTION_HOURS)

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    folders_removed = 0
    cleared_paths: set[str] = set()

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # List items in the bucket root or under 'frames'
            list_url = f"{base_url}/storage/v1/object/list/{bucket}"
            resp = await client.post(
                list_url,
                headers=headers,
                json={"prefix": "frames", "limit": 1000, "sortBy": {"column": "name", "order": "asc"}},
            )

            if resp.status_code == 200:
                items = resp.json()
                objects_to_delete: list[str] = []

                for item in items:
                    created_at_str = item.get("created_at") or item.get("updated_at")
                    name = item.get("name")
                    if not name or not created_at_str:
                        continue

                    try:
                        created_time = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                        if created_time < retention_cutoff:
                            full_path = f"frames/{name}" if not name.startswith("frames/") else name
                            objects_to_delete.append(full_path)

                            # Determine folder prefix: frames/<window_id>/<mark_id>/
                            parts = full_path.split("/")
                            if len(parts) >= 3:
                                folder = f"{parts[0]}/{parts[1]}/{parts[2]}/"
                                cleared_paths.add(folder)
                    except Exception:
                        continue

                # Delete expired objects
                if objects_to_delete:
                    del_url = f"{base_url}/storage/v1/object/{bucket}"
                    del_resp = await client.request(
                        "DELETE",
                        del_url,
                        headers=headers,
                        json={"prefixes": objects_to_delete},
                    )
                    if del_resp.status_code in (200, 204):
                        folders_removed = len(cleared_paths)
                        logger.info(f"Purged {len(objects_to_delete)} expired frame object(s) across {folders_removed} folder(s)")

                # Clear frames_path on matching attendance_marks
                for folder in cleared_paths:
                    marks_url = f"{base_url}/rest/v1/attendance_marks?frames_path=eq.{folder}"
                    await client.patch(marks_url, headers=headers, json={"frames_path": None})

            last_cleanup_time = datetime.now(timezone.utc)
            logger.info(f"Hourly cleanup finished. Folders removed: {folders_removed}")
            return folders_removed
        except Exception as e:
            logger.error(f"Error during frame retention cleanup: {e}")
            return 0


def get_last_cleanup_time() -> datetime | None:
    """Return the timestamp of the last successful retention cleanup."""
    return last_cleanup_time
