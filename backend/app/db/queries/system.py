"""Counts behind the System page and the alert banner. Marks are only read, never changed."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import asyncpg

ATTEMPT_VERDICTS = ("PRESENT", "NEEDS_REVIEW", "REJECTED")


async def verdict_counts(pool: asyncpg.Pool, window_id: UUID) -> dict[str, int]:
    rows = await pool.fetch(
        "select verdict, count(*) as n from attendance_marks "
        "where window_id = $1 and verdict = any($2) group by verdict",
        window_id,
        list(ATTEMPT_VERDICTS),
    )
    return {row["verdict"]: row["n"] for row in rows}


async def rejection_reasons(pool: asyncpg.Pool, window_id: UUID) -> dict[str, int]:
    """The first reason of every rejected attempt. A gate failure has exactly one, and it is the gate's code."""
    rows = await pool.fetch(
        "select reasons[1] as reason, count(*) as n from attendance_marks "
        "where window_id = $1 and verdict = 'REJECTED' and reasons[1] is not null group by 1",
        window_id,
    )
    return {row["reason"]: row["n"] for row in rows}


async def recent_attempts(pool: asyncpg.Pool, since: datetime) -> tuple[int, int]:
    """(attempts, rejected) across all windows since `since`."""
    row = await pool.fetchrow(
        "select count(*) as attempts, count(*) filter (where verdict = 'REJECTED') as rejected "
        "from attendance_marks where marked_at >= $1 and verdict = any($2)",
        since,
        list(ATTEMPT_VERDICTS),
    )
    return row["attempts"], row["rejected"]
