"""Record absentees when a window closes.

Every active, enrolled student with no PRESENT or MANUAL mark gets an ABSENT row.
A student still in NEEDS_REVIEW is left alone; the warden decides those.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg

from app.db.queries import reviews as review_q
from app.schemas.reviews import AbsenteeListOut, AbsenteeRow


async def record(conn: asyncpg.Connection, window_id: UUID) -> int:
    rows = await conn.fetch(
        """
        insert into attendance_marks (window_id, student_id, verdict)
        select $1, s.id, 'ABSENT'
        from students s
        where s.active
          and s.enrolled_at is not null
          and not exists (
            select 1 from attendance_marks m
            where m.window_id = $1
              and m.student_id = s.id
              and m.verdict in ('PRESENT', 'MANUAL', 'NEEDS_REVIEW')
          )
        returning student_id
        """,
        window_id,
    )
    return len(rows)


REASON_TEXT = {
    "declined": "Declined in review",
    "rejected_only": "Rejected attempts only",
    "no_attempt": "No attempt tonight",
    "no_present_mark": "No present mark",
    "not_marked": "Not yet marked",
}


def _reason(row) -> str:
    if row["decided_how"] == "declined":
        return "declined"
    if row["status"] == "NOT_MARKED":
        return "not_marked"
    if row["attempts"] == 0:
        return "no_attempt"
    if row["rejected_attempts"] > 0:
        return "rejected_only"
    return "no_present_mark"


async def list_for_window(pool: asyncpg.Pool, window_id: UUID | None, window_state: str | None) -> AbsenteeListOut:
    """Absentees for one window, with the reason each one is not present and whether they have a device."""
    if window_id is None:
        return AbsenteeListOut(window_id=None, window_state=None, still_to_mark=0, absent=0, students=[])
    rows = await review_q.absentee_rows(pool, window_id)
    students = []
    for row in rows:
        reason = _reason(row)
        students.append(
            AbsenteeRow(
                student_id=row["student_id"],
                student_name=row["student_name"],
                roll_number=row["roll_number"],
                room_number=row["room_number"],
                floor=row["floor"],
                status=row["status"],
                reason=reason,
                reason_text=REASON_TEXT[reason],
                device_enrolled=row["device_enrolled"],
            )
        )
    return AbsenteeListOut(
        window_id=window_id,
        window_state=window_state,
        still_to_mark=sum(1 for s in students if s.status == "NOT_MARKED"),
        absent=sum(1 for s in students if s.status == "ABSENT"),
        students=students,
    )
