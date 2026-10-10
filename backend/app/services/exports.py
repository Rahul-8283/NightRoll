"""The attendance CSV: what a warden needs to file the night, and nothing biometric or diagnostic."""

from __future__ import annotations

import csv
import io
from collections.abc import AsyncIterator
from datetime import date
from uuid import UUID

import asyncpg

from app.auth.supabase import Warden
from app.db.queries import exports as export_q
from app.errors import AppError
from app.services import audit
from app.services.review import actor_of

MAX_RANGE_DAYS = 31
COLUMNS = [
    "date",
    "roll_number",
    "name",
    "room",
    "floor",
    "status",
    "marked_at",
    "how_decided",
    "decided_by",
    "note",
]
HOW = {
    "automatic": "automatic",
    "approved": "approved",
    "manual": "manual",
    "override": "override",
    "declined": "declined",
}
# Spreadsheet programs run any cell that starts with one of these as a formula. A leading quote makes it text.
FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value: object) -> str:
    """Text for one CSV cell, with formula injection neutralised."""
    if value is None:
        return ""
    text = str(value)
    return "'" + text if text.startswith(FORMULA_STARTS) else text


def check_range(date_from: date, date_to: date) -> None:
    if date_to < date_from:
        raise AppError(code="INVALID_RANGE", status_code=422, message="The end date is before the start date")
    if (date_to - date_from).days + 1 > MAX_RANGE_DAYS:
        raise AppError(
            code="RANGE_TOO_LONG",
            status_code=422,
            message=f"One export covers at most {MAX_RANGE_DAYS} days. Export a shorter range.",
        )


async def stream(
    pool: asyncpg.Pool,
    warden: Warden,
    *,
    date_from: date,
    date_to: date,
    floor: int | None,
    room_id: UUID | None,
) -> AsyncIterator[str]:
    check_range(date_from, date_to)
    rows = await export_q.attendance_rows(pool, date_from=date_from, date_to=date_to, floor=floor, room_id=room_id)
    async with pool.acquire() as conn:
        async with conn.transaction():
            await audit.write(
                conn,
                actor=actor_of(warden),
                action="export.created",
                payload={
                    "from": date_from.isoformat(),
                    "to": date_to.isoformat(),
                    "floor": floor,
                    "room_id": str(room_id) if room_id else None,
                    "rows": len(rows),
                },
            )

    yield _line(COLUMNS)
    for row in rows:
        how = HOW.get(row["decided_how"] or "", "")
        decided_by = row["decided_by"] if row["decided_by"] and how else ""
        note = row["decided_note"] if how else ""
        marked_at = row["present_at"] or (row["decided_at"] if how else None)
        yield _line(
            [
                row["night"].isoformat(),
                row["roll_number"],
                row["student_name"],
                row["room_number"],
                row["floor"],
                row["status"],
                marked_at.isoformat() if marked_at else "",
                how or "not decided",
                decided_by,
                note,
            ]
        )


def _line(cells: list) -> str:
    buffer = io.StringIO()
    csv.writer(buffer).writerow([safe_cell(cell) for cell in cells])
    return buffer.getvalue()
