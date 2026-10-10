"""Hand-written, parameterised SQL for the attendance export: one row per enrolled student per night."""

from __future__ import annotations

from datetime import date
from uuid import UUID

import asyncpg


async def attendance_rows(
    pool: asyncpg.Pool,
    *,
    date_from: date,
    date_to: date,
    floor: int | None,
    room_id: UUID | None,
) -> list[asyncpg.Record]:
    return await pool.fetch(
        """
        select w.night, s.roll_number, s.name as student_name, r.number as room_number, r.floor,
               v.status, v.decided_how, v.decided_by, v.decided_note, v.decided_at,
               (select min(m.marked_at) from attendance_marks m
                  where m.window_id = v.window_id and m.student_id = v.student_id
                    and m.verdict in ('PRESENT', 'MANUAL')) as present_at
        from student_window_status v
        join attendance_windows w on w.id = v.window_id
        join students s on s.id = v.student_id
        join rooms r on r.id = s.room_id
        where w.night between $1 and $2
          and v.status <> 'OFF'
          and ($3::int is null or r.floor = $3)
          and ($4::uuid is null or r.id = $4)
        order by w.night, r.floor, r.number, s.roll_number
        """,
        date_from,
        date_to,
        floor,
        room_id,
    )
