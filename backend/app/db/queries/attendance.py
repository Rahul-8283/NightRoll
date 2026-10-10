"""Hand-written, parameterised SQL for attendance marks."""

from __future__ import annotations

from uuid import UUID

import asyncpg


async def has_present_mark(pool: asyncpg.Pool, window_id: UUID, student_id: UUID) -> bool:
    return await pool.fetchval(
        """
        select exists (
          select 1 from attendance_marks
          where window_id = $1 and student_id = $2 and verdict in ('PRESENT', 'MANUAL')
        )
        """,
        window_id,
        student_id,
    )
