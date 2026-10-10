"""Shared setup for the Phase 11 tests that need an enrolled student."""

from __future__ import annotations


async def purge_test_windows(pool):
    """Tests use nights from 2090 on, far from any real night. Remove any a crashed run left behind."""
    ids = [r["id"] for r in await pool.fetch("select id from attendance_windows where night >= '2090-01-01'")]
    if ids:
        await pool.execute(
            "delete from reviews where mark_id in (select id from attendance_marks where window_id = any($1))", ids
        )
        await pool.execute("delete from attendance_marks where window_id = any($1)", ids)
        await pool.execute("delete from attendance_windows where id = any($1)", ids)


async def enrol_for_test(pool):
    """Seeded students are not enrolled (that happens on a phone). Mark one enrolled for the test, restore after."""
    await purge_test_windows(pool)
    student = await pool.fetchrow(
        "select id, room_id, enrolled_at, consent_at, consent_version "
        "from students where active order by roll_number limit 1"
    )
    assert student is not None, "seed the students before running these tests"
    await pool.execute(
        "update students set enrolled_at = coalesce(enrolled_at, now()), consent_at = coalesce(consent_at, now()), "
        "consent_version = coalesce(consent_version, 'test') where id = $1",
        student["id"],
    )
    return student


async def restore_enrolment(pool, student):
    await pool.execute(
        "update students set enrolled_at = $2, consent_at = $3, consent_version = $4 where id = $1",
        student["id"],
        student["enrolled_at"],
        student["consent_at"],
        student["consent_version"],
    )
