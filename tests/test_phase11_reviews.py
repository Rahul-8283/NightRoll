"""Phase 11 review rules, run against the real database.
Needs the Phase 11 migration applied. Run from the backend folder:
    uv run pytest ../tests/test_phase11_reviews.py -v
"""

from __future__ import annotations

import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import jwt
import pytest
import pytest_asyncio

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from app.config import get_settings  # noqa: E402
from app.db import pool as db_pool  # noqa: E402
from app.main import app  # noqa: E402
from app.redis import client as redis_client  # noqa: E402


def _token(role: str = "warden") -> str:
    now = datetime.now(UTC)
    claims = {
        "sub": str(uuid4()),
        "aud": "authenticated",
        "exp": int((now + timedelta(minutes=10)).timestamp()),
        "aal": "aal2",
        "email": f"{role}@test.local",
        "app_metadata": {"role": role},
    }
    return jwt.encode(claims, get_settings().SUPABASE_JWT_SECRET, algorithm="HS256")


def _client(role: str = "warden") -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {_token(role)}"},
    )


@pytest_asyncio.fixture
async def world():
    settings = get_settings()
    await db_pool.connect(settings)
    await redis_client.connect(settings)
    pool = db_pool.get_pool()
    student = await pool.fetchrow(
        "select id, room_id from students where active and enrolled_at is not null order by roll_number limit 1"
    )
    assert student is not None, "seed an enrolled student before running these tests"
    # Each test gets its own night far in the future, so it never meets real attendance.
    night = date(2090, 1, 1) + timedelta(days=uuid4().int % 3000)
    now = datetime.now(UTC)
    window_id = await pool.fetchval(
        """
        insert into attendance_windows (night, opens_at, closes_at, state)
        values ($1, $2, $3, 'open') returning id
        """,
        night,
        now - timedelta(minutes=5),
        now + timedelta(hours=1),
    )
    yield {"pool": pool, "student": student, "window_id": window_id}

    await pool.execute(
        "delete from reviews where mark_id in (select id from attendance_marks where window_id = $1)", window_id
    )
    await pool.execute("delete from attendance_marks where window_id = $1", window_id)
    await pool.execute("delete from attendance_windows where id = $1", window_id)
    await db_pool.disconnect()
    await redis_client.disconnect()


async def _mark(pool, window_id, student_id, verdict, attempt=1) -> UUID:
    return await pool.fetchval(
        """
        insert into attendance_marks (window_id, student_id, verdict, reasons, attempt)
        values ($1, $2, $3, '{}', $4) returning id
        """,
        window_id,
        student_id,
        verdict,
        attempt,
    )


@pytest.mark.asyncio
async def test_queue_lists_only_marks_awaiting_a_decision(world):
    mark = await _mark(world["pool"], world["window_id"], world["student"]["id"], "NEEDS_REVIEW")
    async with _client() as c:
        response = await c.get("/v1/reviews", params={"window_id": str(world["window_id"])})
    assert response.status_code == 200
    assert str(mark) in [item["mark_id"] for item in response.json()]


@pytest.mark.asyncio
async def test_approving_a_review_makes_the_student_present(world):
    mark = await _mark(world["pool"], world["window_id"], world["student"]["id"], "NEEDS_REVIEW")
    async with _client() as c:
        response = await c.post(f"/v1/attendance/marks/{mark}/review", json={"decision": "APPROVED"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "PRESENT"
    assert body["decided_how"] == "approved"


@pytest.mark.asyncio
async def test_a_second_decision_on_the_same_mark_is_a_conflict(world):
    mark = await _mark(world["pool"], world["window_id"], world["student"]["id"], "NEEDS_REVIEW")
    async with _client() as c:
        first = await c.post(f"/v1/attendance/marks/{mark}/review", json={"decision": "APPROVED"})
        second = await c.post(
            f"/v1/attendance/marks/{mark}/review", json={"decision": "DECLINED", "note": "changed my mind"}
        )
    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "ALREADY_DECIDED"


@pytest.mark.asyncio
async def test_declining_needs_a_note_and_makes_the_student_absent(world):
    mark = await _mark(world["pool"], world["window_id"], world["student"]["id"], "NEEDS_REVIEW")
    async with _client() as c:
        without = await c.post(f"/v1/attendance/marks/{mark}/review", json={"decision": "DECLINED"})
        assert without.status_code == 422
        with_note = await c.post(
            f"/v1/attendance/marks/{mark}/review",
            json={"decision": "DECLINED", "note": "Could not confirm the face in the frames"},
        )
    assert with_note.status_code == 200
    assert with_note.json()["status"] == "ABSENT"
    assert with_note.json()["decided_how"] == "declined"


@pytest.mark.asyncio
async def test_reviewing_a_mark_that_is_not_in_review_is_a_conflict(world):
    mark = await _mark(world["pool"], world["window_id"], world["student"]["id"], "PRESENT")
    async with _client() as c:
        response = await c.post(f"/v1/attendance/marks/{mark}/review", json={"decision": "APPROVED"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "NOT_AWAITING_REVIEW"


@pytest.mark.asyncio
async def test_override_needs_a_note_of_ten_characters(world):
    mark = await _mark(world["pool"], world["window_id"], world["student"]["id"], "REJECTED")
    async with _client() as c:
        response = await c.post(f"/v1/attendance/marks/{mark}/override", json={"status": "PRESENT", "note": "short"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_overriding_a_rejected_mark_to_present_is_reflected_in_the_status(world):
    mark = await _mark(world["pool"], world["window_id"], world["student"]["id"], "REJECTED")
    async with _client() as c:
        response = await c.post(
            f"/v1/attendance/marks/{mark}/override",
            json={"status": "PRESENT", "note": "Checked in person at the warden desk"},
        )
    assert response.status_code == 200
    assert response.json()["status"] == "PRESENT"
    assert response.json()["decided_how"] == "override"


@pytest.mark.asyncio
async def test_a_later_override_replaces_the_earlier_one_and_both_stay_in_the_detail(world):
    mark = await _mark(world["pool"], world["window_id"], world["student"]["id"], "REJECTED")
    async with _client() as c:
        await c.post(
            f"/v1/attendance/marks/{mark}/override",
            json={"status": "PRESENT", "note": "Checked in person at the warden desk"},
        )
        await c.post(
            f"/v1/attendance/marks/{mark}/override",
            json={"status": "ABSENT", "note": "Phone was in another room, confirmed"},
        )
        detail = (await c.get(f"/v1/attendance/marks/{mark}")).json()
    assert detail["effective_status"] == "ABSENT"
    assert [d["status"] for d in detail["decisions"]] == ["ABSENT", "PRESENT"]


@pytest.mark.asyncio
async def test_manual_mark_for_a_present_student_is_a_conflict(world):
    await _mark(world["pool"], world["window_id"], world["student"]["id"], "PRESENT")
    async with _client() as c:
        response = await c.post(
            "/v1/attendance/manual",
            json={
                "student_id": str(world["student"]["id"]),
                "window_id": str(world["window_id"]),
                "note": "Recorded by hand at the desk",
            },
        )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ALREADY_PRESENT"


@pytest.mark.asyncio
async def test_manual_mark_during_the_window_works(world):
    async with _client() as c:
        response = await c.post(
            "/v1/attendance/manual",
            json={
                "student_id": str(world["student"]["id"]),
                "window_id": str(world["window_id"]),
                "note": "Verified in person at the warden desk",
            },
        )
    assert response.status_code == 200
    assert response.json()["status"] == "PRESENT"


@pytest.mark.asyncio
async def test_manual_mark_more_than_a_day_after_close_is_refused_for_a_warden_but_not_an_admin(world):
    pool = world["pool"]
    old_window = await pool.fetchval(
        """
        insert into attendance_windows (night, opens_at, closes_at, state)
        values ($1, $2, $3, 'closed') returning id
        """,
        date(2091, 1, 1) + timedelta(days=uuid4().int % 3000),
        datetime.now(UTC) - timedelta(days=3),
        datetime.now(UTC) - timedelta(days=2),
    )
    try:
        body = {
            "student_id": str(world["student"]["id"]),
            "window_id": str(old_window),
            "note": "Verified in person at the warden desk",
        }
        async with _client("warden") as c:
            refused = await c.post("/v1/attendance/manual", json=body)
        assert refused.status_code == 403
        async with _client("admin") as c:
            allowed = await c.post("/v1/attendance/manual", json=body)
        assert allowed.status_code == 200
    finally:
        await pool.execute(
            "delete from reviews where mark_id in (select id from attendance_marks where window_id = $1)", old_window
        )
        await pool.execute("delete from attendance_marks where window_id = $1", old_window)
        await pool.execute("delete from attendance_windows where id = $1", old_window)


@pytest.mark.asyncio
async def test_every_decision_writes_an_audit_row(world):
    mark = await _mark(world["pool"], world["window_id"], world["student"]["id"], "NEEDS_REVIEW")
    async with _client() as c:
        await c.post(f"/v1/attendance/marks/{mark}/review", json={"decision": "APPROVED"})
    rows = await world["pool"].fetch("select action, payload from audit_log where target_id = $1", str(mark))
    assert [row["action"] for row in rows] == ["review.decided"]


@pytest.mark.asyncio
async def test_absentees_list_students_without_a_present_status_with_a_reason(world):
    pool = world["pool"]
    other = await pool.fetchrow(
        "select id from students where active and enrolled_at is not null and id <> $1 limit 1", world["student"]["id"]
    )
    await pool.execute(
        "update attendance_windows set state = 'closed', closes_at = now() - interval '1 minute' where id = $1",
        world["window_id"],
    )
    await _mark(pool, world["window_id"], other["id"], "PRESENT")
    async with _client() as c:
        response = await c.get("/v1/attendance/absentees", params={"window_id": str(world["window_id"])})
    assert response.status_code == 200
    students = {row["student_id"]: row for row in response.json()["students"]}
    assert str(other["id"]) not in students
    assert students[str(world["student"]["id"])]["reason"] == "no_attempt"
