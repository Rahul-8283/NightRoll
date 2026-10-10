"""Hand-written, parameterised SQL for the warden dashboard's read views."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import asyncpg


async def room_counts(pool: asyncpg.Pool, window_id: UUID | None) -> list[asyncpg.Record]:
    """Per room: enrolled students, and each status from the student window view, plus rejected attempts."""
    return await pool.fetch(
        """
        select
          r.id as room_id, r.number, r.floor,
          (select count(*) from students s
             where s.room_id = r.id and s.active and s.enrolled_at is not null) as total,
          (select count(*) from student_window_status v
             where v.window_id = $1 and v.room_id = r.id and v.status = 'PRESENT') as present,
          (select count(*) from student_window_status v
             where v.window_id = $1 and v.room_id = r.id and v.status = 'PENDING') as pending_review,
          (select count(*) from student_window_status v
             where v.window_id = $1 and v.room_id = r.id and v.status = 'ABSENT') as absent,
          (select count(*) from attendance_marks m
             join students s on s.id = m.student_id
             where m.window_id = $1 and s.room_id = r.id and m.verdict = 'REJECTED') as rejected
        from rooms r
        order by r.floor, r.number
        """,
        window_id,
    )


async def recent_marks(pool: asyncpg.Pool, window_id: UUID, limit: int) -> list[asyncpg.Record]:
    return await pool.fetch(
        """
        select m.id as mark_id, m.verdict, m.reasons, m.marked_at,
               m.score, s.name as student_name, r.number as room_number, r.id as room_id
        from attendance_marks m
        join students s on s.id = m.student_id
        join rooms r on r.id = s.room_id
        where m.window_id = $1
        order by m.marked_at desc
        limit $2
        """,
        window_id,
        limit,
    )


async def mark_summary(pool: asyncpg.Pool, mark_id: UUID) -> asyncpg.Record | None:
    return await pool.fetchrow(
        """
        select m.id as mark_id, m.verdict, m.reasons, m.marked_at, m.score,
               s.name as student_name, r.number as room_number, r.id as room_id
        from attendance_marks m
        join students s on s.id = m.student_id
        join rooms r on r.id = s.room_id
        where m.id = $1
        """,
        mark_id,
    )


async def room_students_with_marks(pool: asyncpg.Pool, room_id: UUID, window_id: UUID | None) -> list[asyncpg.Record]:
    """Every student in the room, with their best mark for the window (a PRESENT wins, else the latest)."""
    return await pool.fetch(
        """
        select s.id as student_id, s.roll_number, s.name, s.active,
               (s.enrolled_at is not null) as enrolled,
               (exists (select 1 from face_embeddings fe where fe.student_id = s.id)) as face_enrolled,
               (exists (select 1 from devices d where d.student_id = s.id and d.active = true)) as device_enrolled,
               (
                 select d.key_alias from devices d
                 where d.student_id = s.id and d.active = true
                 order by d.enrolled_at desc limit 1
               ) as device_security_level,
               m.id as mark_id, m.verdict, m.reasons, m.score, m.marked_at, m.attempt, m.scores
        from students s
        left join lateral (
          select * from attendance_marks am
          where am.window_id = $2 and am.student_id = s.id
          order by (am.verdict in ('PRESENT', 'MANUAL')) desc, am.attempt desc
          limit 1
        ) m on true
        where s.room_id = $1
        order by s.roll_number
        """,
        room_id,
        window_id,
    )


async def window_history(pool: asyncpg.Pool, limit: int) -> list[asyncpg.Record]:
    return await pool.fetch(
        """
        select w.id, w.night, w.opens_at, w.closes_at, w.state,
          (select count(*) from student_window_status v
             where v.window_id = w.id and v.status = 'PRESENT') as present,
          (select count(*) from students s
             where s.active and s.enrolled_at is not null) as enrolled
        from attendance_windows w
        order by w.night desc
        limit $1
        """,
        limit,
    )


async def window_by_id(pool: asyncpg.Pool, window_id: UUID) -> asyncpg.Record | None:
    return await pool.fetchrow(
        "select id, night, opens_at, closes_at, state from attendance_windows where id = $1",
        window_id,
    )


async def enrolled_total(pool: asyncpg.Pool) -> int:
    return int(await pool.fetchval("select count(*) from students where active and enrolled_at is not null"))


async def closes_at_of(pool: asyncpg.Pool, window_id: UUID) -> datetime | None:
    return await pool.fetchval("select closes_at from attendance_windows where id = $1", window_id)


async def room_health_rows(pool: asyncpg.Pool, window_id: UUID | None, room_id: UUID | None) -> list[asyncpg.Record]:
    """Per room, the figures behind its health flags: the last 7 days' Wi-Fi trouble, and tonight's router sightings."""
    return await pool.fetch(
        """
        select r.id as room_id,
          (select count(*) from attendance_marks m join students s on s.id = m.student_id
             where s.room_id = r.id and m.marked_at >= now() - interval '7 days'
               and m.verdict in ('PRESENT', 'NEEDS_REVIEW', 'REJECTED')) as week_total,
          (select count(*) from attendance_marks m join students s on s.id = m.student_id
             where s.room_id = r.id and m.marked_at >= now() - interval '7 days'
               and (m.verdict = 'NEEDS_REVIEW'
                    or (m.verdict = 'REJECTED'
                        and m.reasons && array['WIFI_PATTERN_MISMATCH', 'FINGERPRINT_MISSING',
                                       'AP_UNAVAILABLE']::text[])))
             as week_flagged,
          (select count(*) from attendance_marks m join students s on s.id = m.student_id
             where $1::uuid is not null and m.window_id = $1 and s.room_id = r.id and m.scores is not null
               and m.verdict in ('PRESENT', 'NEEDS_REVIEW', 'REJECTED')) as tonight_scored,
          (select count(*) from attendance_marks m join students s on s.id = m.student_id
             where $1::uuid is not null and m.window_id = $1 and s.room_id = r.id and m.scores is not null
               and m.verdict in ('PRESENT', 'NEEDS_REVIEW', 'REJECTED')
               and exists (
                 select 1 from jsonb_array_elements(m.scores->'scorers') e
                 where e->>'name' = 'own_ap' and (e->>'score')::float > 0
               )) as tonight_ap_seen
        from rooms r
        where ($2::uuid is null or r.id = $2)
        """,
        window_id,
        room_id,
    )
