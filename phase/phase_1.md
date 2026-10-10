# Phase 1: Data Layer on Supabase

| | |
|---|---|
| **Type** | Implementation |
| **Depends on** | Phase 0 |
| **Unlocks** | Phases 2, 3, 5, 6 |
| **Lead** | Backend |

## Goal

Every table, index, policy and storage rule the system needs exists in Supabase, created by migrations in git. After this phase the database shape is settled, so the services can be written against it.

## Outcome

- All tables from the TRD exist in the `nightroll-dev` project.
- Row-level security is on for every table, with no access for the public keys.
- The `frames` bucket is private and locked to server credentials.
- A seed script loads demo rooms, access points and test students.

## Scope

**In:** schema, indexes, constraints, row-level security, storage policy, warden roles, seed data.
**Out:** any API code, any query logic, embeddings for real people.

---

## Tasks

### 1. Migrations

All SQL goes in `supabase/migrations/` as timestamped files, applied with `supabase db push`. Nobody creates tables by hand in the dashboard.

| # | Migration | Contents |
|---|---|---|
| 1.1 | `init_extensions` | `create extension if not exists vector;` |
| 1.2 | `rooms_and_access_points` | `rooms`, `access_points` |
| 1.3 | `students_and_devices` | `students`, `devices`, `face_embeddings` |
| 1.4 | `fingerprints` | `room_fingerprints` |
| 1.5 | `attendance` | `attendance_windows`, `attendance_marks`, `reviews` |
| 1.6 | `enrollment_codes` | `enrollment_codes` |
| 1.7 | `audit` | `audit_log` |
| 1.8 | `rls` | Enable row-level security on every table |
| 1.9 | `storage` | Policies for the `frames` bucket |

### 2. Tables

Use the schema in `docs/TRD.md` section 7.1, with these additions.

**`students`**
- Add `fcm_token text` for push delivery. It is replaced whenever the app reports a new one.

**`devices`**
- Add a partial unique index so a student has at most one active device:
  `create unique index one_active_device on devices (student_id) where active;`

**`enrollment_codes`** (new)

| Column | Type | Notes |
|---|---|---|
| `code_hash` | `text primary key` | SHA-256 of the code. The code itself is never stored. |
| `student_id` | `uuid references students(id)` | Who the code is for |
| `created_by` | `uuid` | Warden's Supabase user ID |
| `expires_at` | `timestamptz not null` | Short life, 15 minutes |
| `used_at` | `timestamptz` | Set once, on use |

This is how enrollment is authorised: the warden creates a one-time code at the desk, and the app submits it. Without it, anyone who knew a roll number could enroll a device.

**`attendance_marks`**
- Add `attempt int not null default 1`, so retries inside a window are kept as history.
- Keep the partial unique index: one `PRESENT` mark per student per window.
- Add `frames_path text`, the storage folder for this mark's frames. Null once they are deleted.

**`audit_log`**
- Insert only. No update or delete is ever issued against it.

### 3. Indexes

| Index | Why |
|---|---|
| `attendance_marks (window_id, student_id)` | Dashboard and duplicate checks |
| `attendance_marks (window_id, verdict)` | Review queue and absentee list |
| `students (room_id)` | Room tiles |
| `access_points (room_id)` | Fingerprint and network checks |
| `audit_log (created_at)` | Audit view |

No vector index is needed. Matching is one-to-one against a known student, so each check reads one embedding by primary key.

### 4. Row-level security

Decision: **the backend is the only thing that reads or writes tables.** The dashboard uses Supabase only to log in, then calls the NightRoll API. The app never talks to Supabase.

| # | Task |
|---|---|
| 4.1 | `alter table ... enable row level security` on every table |
| 4.2 | Create no policies for the `anon` or `authenticated` roles. With security on and no policy, both are denied. |
| 4.3 | Confirm with the anon key that `select` on each table returns nothing |

The backend connects with the database connection string, which is not subject to these policies. That is why the string stays server-side.

### 5. Storage policy

| # | Task |
|---|---|
| 5.1 | Confirm the `frames` bucket is private |
| 5.2 | Add no policy for `anon` or `authenticated`. Only the service role can read or write. |
| 5.3 | Confirm with the anon key that listing and download both fail |

### 6. Warden roles

| # | Task |
|---|---|
| 6.1 | Store the role in the Supabase user's `app_metadata.role`, with values `warden` or `admin`. This field can only be set server-side. |
| 6.2 | Write `scripts/create_warden.py`, which creates a user and sets the role using the service role key |
| 6.3 | Create one `warden` and one `admin` test account |

### 7. Seed data

Write `scripts/seed.py`. It reads `config/rooms.local.json` if present, otherwise `config/rooms.example.json`.

| # | Loads |
|---|---|
| 7.1 | Rooms and access points from the room map |
| 7.2 | About eight test students spread across the demo rooms, with made-up names and roll numbers |
| 7.3 | Nothing biometric. Embeddings arrive through enrollment in Phase 6. |

The script is safe to run twice: it upserts by room number and roll number.

---

## Files

```text
supabase/migrations/*.sql
scripts/seed.py
scripts/create_warden.py
config/rooms.example.json
docs/TRD.md              (update section 7.1 with the additions above)
```

## Exit criteria

- [ ] `supabase db push` on a clean project creates everything with no manual step.
- [ ] Every table shows row-level security enabled in the Supabase dashboard.
- [ ] A query with the anon key returns no rows from any table.
- [ ] The anon key cannot list or download from `frames`.
- [ ] Inserting a second `PRESENT` mark for the same student and window fails.
- [ ] Inserting a second active device for the same student fails.
- [ ] `seed.py` runs twice in a row without errors or duplicates.
- [ ] The test warden's token carries `app_metadata.role = "warden"`.

## Deferred to Phase 13

- Automated migration test against a throwaway database.
- Tests for each constraint and index.

## Risks

| Risk | What to do |
|---|---|
| Someone edits a table in the Supabase dashboard | Changes go through a migration file only. Run `supabase db diff` before each phase ends to catch drift. |
| A policy is added later that opens a table | Any new policy needs a second teammate to read it before it is pushed |
| Real student data lands in the dev project | Use made-up names until the college approves a pilot |

## Hand-off to Phase 2

Phase 2 needs the connection string, the table names, and the two test accounts.
