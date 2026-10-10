"""Seed demo rooms, access points and test students for local development.

Phase 1, task 7. Reads config/rooms.local.json if present, otherwise
config/rooms.example.json. Safe to run twice: every insert upserts by the
table's natural key (room number, access point BSSID, student roll number),
so a second run updates existing rows instead of duplicating them.

No biometric data is seeded here. Face embeddings arrive through enrollment
in Phase 6.

Usage (from the backend folder, so its venv has asyncpg):

    uv run python ../scripts/seed.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import asyncpg

ROOT = Path(__file__).resolve().parent.parent

# Made-up names and roll numbers. Never real student data in this file.
TEST_STUDENTS = [
    "Asha Verma",
    "Rohan Mehta",
    "Priya Nair",
    "Kabir Singh",
    "Divya Rao",
    "Arjun Pillai",
    "Meera Iyer",
    "Sanjay Kumar",
]


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_room_map() -> dict:
    local = ROOT / "config" / "rooms.local.json"
    example = ROOT / "config" / "rooms.example.json"
    path = local if local.exists() else example
    print(f"Reading room map from {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


async def seed_rooms(conn: asyncpg.Connection, rooms: list[dict]) -> dict[str, str]:
    room_ids: dict[str, str] = {}
    for room in rooms:
        row = await conn.fetchrow(
            """
            insert into rooms (number, floor, subnet)
            values ($1, $2, $3)
            on conflict (number) do update set floor = excluded.floor, subnet = excluded.subnet
            returning id
            """,
            room["number"],
            room["floor"],
            room.get("subnet"),
        )
        room_ids[room["number"]] = row["id"]
        for ap in room.get("access_points", []):
            await conn.execute(
                """
                insert into access_points (bssid, room_id, band)
                values ($1, $2, $3)
                on conflict (bssid) do update set room_id = excluded.room_id, band = excluded.band
                """,
                ap["bssid"],
                row["id"],
                ap["band"],
            )
    print(f"Seeded {len(rooms)} rooms")
    return room_ids


async def seed_students(conn: asyncpg.Connection, room_ids: dict[str, str]) -> None:
    room_numbers = list(room_ids.keys())
    if not room_numbers:
        print("No rooms to assign students to; skipping students", file=sys.stderr)
        return
    for i, name in enumerate(TEST_STUDENTS):
        roll_number = f"TEST{i + 1:03d}"
        room_number = room_numbers[i % len(room_numbers)]
        await conn.execute(
            """
            insert into students (roll_number, name, room_id, consent_at, active)
            values ($1, $2, $3, now(), true)
            on conflict (roll_number) do update
              set name = excluded.name, room_id = excluded.room_id, active = true
            """,
            roll_number,
            name,
            room_ids[room_number],
        )
    print(f"Seeded {len(TEST_STUDENTS)} test students")


async def main() -> int:
    env = parse_env(ROOT / "backend" / ".env")
    conn = await asyncpg.connect(env["DATABASE_URL"], statement_cache_size=0, timeout=15)
    try:
        data = load_room_map()
        async with conn.transaction():
            room_ids = await seed_rooms(conn, data["rooms"])
            await seed_students(conn, room_ids)
    finally:
        await conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
