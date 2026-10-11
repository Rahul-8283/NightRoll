"""Checks that need the running face worker, and the demo banner (Phase 12 section 3).

Settings that can be judged from the environment alone are refused in `Settings`. Whether the face
worker has its anti-spoof model loaded can only be asked of the worker, so it is asked here.
"""

from __future__ import annotations

import logging

import httpx

from app.config import STRICT_ENVS, Settings
from app.logging import log_event

logger = logging.getLogger("nightroll.startup")

ANTISPOOF_UNAVAILABLE = "the face worker reports that its anti-spoof model is not available"


async def face_worker_antispoof(settings: Settings) -> bool | None:
    """True or False as the worker reports it, None when the worker could not be asked."""
    try:
        async with httpx.AsyncClient(timeout=settings.FACE_WORKER_TIMEOUT_SECONDS) as client:
            resp = await client.get(
                f"{settings.FACE_WORKER_URL.rstrip('/')}/health",
                headers={"Authorization": f"Bearer {settings.FACE_WORKER_TOKEN}"},
            )
        if resp.status_code != 200:
            return None
        return bool(resp.json().get("antispoof_available"))
    except (httpx.HTTPError, ValueError):
        return None


def banner(lines: list[str]) -> str:
    rule = "=" * 72
    body = "\n".join(f"  - {line}" for line in lines)
    title = "  DEMO MODE: these settings are relaxed. Do not use this server for real attendance."
    return f"\n{rule}\n{title}\n{body}\n{rule}"


async def run(settings: Settings) -> None:
    """Refuse to start in pilot or production when the face worker has no anti-spoof model.

    In demo mode, log and print every relaxed setting so the team knows what is relaxed on stage.
    """
    if settings.APP_ENV == "local":
        return
    antispoof = await face_worker_antispoof(settings)

    if settings.APP_ENV in STRICT_ENVS:
        if antispoof is None:
            raise SystemExit(
                f"APP_ENV={settings.APP_ENV} needs the face worker at {settings.FACE_WORKER_URL}, "
                "which did not answer. Start it first."
            )
        if not antispoof:
            raise SystemExit(f"APP_ENV={settings.APP_ENV} is not allowed: {ANTISPOOF_UNAVAILABLE}")
        return

    if settings.APP_ENV == "demo":
        relaxed = settings.relaxed_settings()
        if antispoof is not True:
            relaxed.append(ANTISPOOF_UNAVAILABLE if antispoof is False else "the face worker did not answer")
        print(banner(relaxed or ["nothing is relaxed"]), flush=True)
        log_event(logger, logging.WARNING, "demo mode", relaxed=relaxed)
