"""Record absentees when a window closes.

Every active, enrolled student with no PRESENT or MANUAL mark gets an ABSENT row.
A student still in NEEDS_REVIEW is left alone; the warden decides those.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg


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
