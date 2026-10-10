"""Hand-written, parameterised SQL for warden reviews, overrides, manual marks and the effective status view."""

from __future__ import annotations

from uuid import UUID

import asyncpg

Db = asyncpg.Pool | asyncpg.Connection


async def get_mark(db: Db, mark_id: UUID) -> asyncpg.Record | None:
    return await db.fetchrow(
        """
        select m.id as mark_id, m.window_id, m.student_id, m.verdict, m.score, m.reasons, m.scores,
               m.attempt, m.marked_at, m.frames_path,
               s.name as student_name, s.roll_number, s.room_id, r.number as room_number, r.floor,
               w.state as window_state, w.opens_at, w.closes_at
        from attendance_marks m
        join students s on s.id = m.student_id
        join rooms r on r.id = s.room_id
        join attendance_windows w on w.id = m.window_id
        where m.id = $1
        """,
        mark_id,
    )


async def lock_mark(conn: asyncpg.Connection, mark_id: UUID) -> asyncpg.Record | None:
    return await conn.fetchrow(
        "select id, verdict, window_id, student_id from attendance_marks where id = $1 for update", mark_id
    )


async def lock_window(conn: asyncpg.Connection, window_id: UUID) -> asyncpg.Record | None:
    return await conn.fetchrow(
        "select id, state, opens_at, closes_at from attendance_windows where id = $1 for update", window_id
    )


async def reviews_for_mark(db: Db, mark_id: UUID) -> list[asyncpg.Record]:
    return await db.fetch(
        """
        select decision, status, reviewed_by, note, reviewed_at
        from reviews where mark_id = $1
        order by reviewed_at desc, id desc
        """,
        mark_id,
    )


async def insert_review(
    conn: asyncpg.Connection,
    *,
    mark_id: UUID,
    decision: str,
    status: str | None,
    reviewed_by: str,
    note: str | None,
) -> None:
    await conn.execute(
        """
        insert into reviews (mark_id, decision, status, reviewed_by, note)
        values ($1, $2, $3, $4, $5)
        """,
        mark_id,
        decision,
        status,
        reviewed_by,
        note,
    )


async def awaiting_review(pool: asyncpg.Pool, window_id: UUID) -> list[asyncpg.Record]:
    """Marks in review with no decision yet, oldest first, with what the warden needs beside them."""
    return await pool.fetch(
        """
        select m.id as mark_id, m.window_id, m.student_id, m.reasons, m.scores, m.score, m.attempt,
               m.marked_at, m.frames_path,
               s.name as student_name, s.roll_number, s.room_id, r.number as room_number, r.floor,
               rf.created_at as fingerprint_created_at,
               (select count(*) from attendance_marks a
                  where a.window_id = m.window_id and a.student_id = m.student_id) as attempts_tonight
        from attendance_marks m
        join students s on s.id = m.student_id
        join rooms r on r.id = s.room_id
        left join lateral (
          select created_at from room_fingerprints f
          where f.room_id = s.room_id order by f.version desc limit 1
        ) rf on true
        where m.window_id = $1
          and m.verdict = 'NEEDS_REVIEW'
          and not exists (select 1 from reviews rv where rv.mark_id = m.id)
        order by m.marked_at asc
        """,
        window_id,
    )


async def earlier_attempts(db: Db, window_id: UUID, student_id: UUID, mark_id: UUID) -> list[asyncpg.Record]:
    return await db.fetch(
        """
        select id as mark_id, verdict, reasons, marked_at, attempt
        from attendance_marks
        where window_id = $1 and student_id = $2 and id <> $3
        order by attempt
        """,
        window_id,
        student_id,
        mark_id,
    )


async def student_status(db: Db, window_id: UUID, student_id: UUID) -> asyncpg.Record | None:
    return await db.fetchrow(
        """
        select status, decided_how, decided_by, decided_note, decided_at
        from student_window_status where window_id = $1 and student_id = $2
        """,
        window_id,
        student_id,
    )


async def next_attempt(conn: asyncpg.Connection, window_id: UUID, student_id: UUID) -> int:
    return int(
        await conn.fetchval(
            "select coalesce(max(attempt), 0) + 1 from attendance_marks where window_id = $1 and student_id = $2",
            window_id,
            student_id,
        )
    )


async def insert_manual_mark(conn: asyncpg.Connection, *, window_id: UUID, student_id: UUID, attempt: int) -> UUID:
    return await conn.fetchval(
        """
        insert into attendance_marks (window_id, student_id, verdict, reasons, attempt)
        values ($1, $2, 'MANUAL', '{}', $3)
        returning id
        """,
        window_id,
        student_id,
        attempt,
    )


async def active_enrolled_student(pool: asyncpg.Pool, student_id: UUID) -> asyncpg.Record | None:
    return await pool.fetchrow(
        "select id, name, roll_number, room_id from students where id = $1 and active and enrolled_at is not null",
        student_id,
    )
