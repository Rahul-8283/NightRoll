# Phase 3: Attendance Window and Nonces

| | |
|---|---|
| **Type** | Implementation |
| **Depends on** | Phases 1, 2 |
| **Unlocks** | Phases 4, 7, 8, 10 |
| **Lead** | Backend |

## Goal

The warden can set tonight's window. At the opening time the system issues every enrolled student a one-time nonce. Students open the app during the window to get it. At the closing time the system records who is absent. Nothing is pushed to phones: students open NightRoll themselves at window time.

## Outcome

- Window create, update and off-day endpoints work.
- A scheduler process opens and closes windows on the server clock.
- Each student has one nonce in Redis that expires when the window closes.
- A nonce can be consumed exactly once, even under simultaneous requests.
- A student who opens the app during the window receives their nonce and challenge. Outside the window, the app receives the next opening time.

## Scope

**In:** window endpoints, scheduler, nonce issue and consume, the status endpoint the app calls, absentee recording.
**Out:** verifying a mark (Phase 8), the Home screen (Phase 4).

---

## Tasks

### 1. Window endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/v1/windows` | Warden | Create or update the window for a date |
| GET | `/v1/windows/current` | Warden | Tonight's window and its state |
| GET | `/v1/windows` | Warden | Past and upcoming windows |
| POST | `/v1/windows/{id}/off` | Warden | Mark the night as an off day |
| POST | `/v1/windows/{id}/open-now` | Admin | Open at once. For the demo and for testing. |
| POST | `/v1/windows/{id}/close-now` | Admin | Close at once |

Rules:
- One window per date. Posting again for the same date updates it.
- `closes_at` must be after `opens_at`.
- A window that is already open can have its closing time moved later, not earlier than now.
- A window that has closed cannot be edited.
- If no window is set for a date, the scheduler creates one from `WINDOW_DEFAULT_OPEN` and `WINDOW_DEFAULT_CLOSE`, unless the date is an off day.
- Times are stored in UTC and shown in `TIMEZONE`.
- Every change writes an audit row.

### 2. Window state

States: `scheduled`, `open`, `closed`, `off`.

| # | Task |
|---|---|
| 2.1 | Keep the durable record in `attendance_windows` |
| 2.2 | Mirror the live state to Redis as `window:{window_id}:state` for fast checks during verification |
| 2.3 | Keep a Redis key `window:current` pointing at the open window's ID, removed on close |

### 3. Nonce store

| # | Task |
|---|---|
| 3.1 | On open, for each active enrolled student, generate 32 random bytes with a cryptographic random source |
| 3.2 | Store as a Redis hash at `nonce:{window_id}:{student_id}` with fields `value` and `used=0` |
| 3.3 | Set the key to expire at `closes_at` |
| 3.4 | Write all nonces in one Redis pipeline |
| 3.5 | Write `consume_nonce` as a Lua script: it checks the key exists, the value matches and `used` is 0, then sets `used=1`. It returns one of `ok`, `missing`, `mismatch`, `already_used`. |
| 3.6 | Write `peek_nonce`, which checks without consuming. Phase 8 uses it before the signature check. |
| 3.7 | If the closing time is extended, extend every nonce's expiry to match |

A Lua script is used because Redis runs it as one step, so two requests arriving together cannot both consume the same nonce.

### 4. Nonce and status endpoint

The student's app calls this endpoint when it opens, and again every 60 seconds while Home is visible. The nonce is only ever handed out in response to that call, never stored on the phone in advance.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/v1/attendance/nonce` | Device signature (finished in Phase 8) | Tonight's status for this student, with nonce and challenge while the window is open |

Responses:

| State | Body |
|---|---|
| Window open, not yet marked | `{"state": "open", "window_id", "nonce", "closes_at", "challenge": ["blink", "turn_left"]}` |
| Window scheduled, not yet open | `{"state": "scheduled", "opens_at"}` |
| Already present tonight | `{"state": "marked", "window_id"}` |
| Off day | `{"state": "off"}` |
| Window closed | `{"state": "closed"}` |

For this phase, build the endpoint and the lookup. Leave the signature check as a clearly marked stub that Phase 8 replaces. Do not expose this endpoint outside local development until Phase 8 is done.

### 5. Scheduler

| # | Task |
|---|---|
| 5.1 | Run the scheduler as its own process (`python -m app.scheduler`), using APScheduler |
| 5.2 | Every 15 seconds, check for windows that should open or close |
| 5.3 | **Open job:** set state to `open`, issue nonces, write audit row |
| 5.4 | **Close job:** set state to `closed`, record absentees, publish final counts, write audit row |
| 5.5 | Both jobs are safe to run twice. A window already open is not opened again. |
| 5.6 | Take a short Redis lock per window per job, so two scheduler processes cannot both run it |
| 5.7 | On startup, catch up: a window that should already be open gets opened immediately |

### 6. Absentee recording

On close:

| # | Task |
|---|---|
| 6.1 | Find active enrolled students with no `PRESENT` or `MANUAL` mark in this window |
| 6.2 | Insert an `ABSENT` mark for each, in one transaction |
| 6.3 | Students with a mark still in `NEEDS_REVIEW` are left as they are. The warden decides those. |

---

## Files

```text
backend/app/routers/windows.py
backend/app/routers/attendance.py      (nonce and status endpoint only for now)
backend/app/services/windows.py
backend/app/services/nonces.py
backend/app/services/absentees.py
backend/app/scheduler.py
backend/app/redis/consume_nonce.lua
```

## Exit criteria

- [ ] A warden can create tonight's window and read it back.
- [ ] With the scheduler running, a window set one minute ahead opens on its own.
- [ ] After opening, Redis holds one nonce per active enrolled student, each with an expiry.
- [ ] Calling `consume_nonce` twice with the same value returns `ok`, then `already_used`.
- [ ] The status endpoint, called with a valid device signature during an open window, returns the nonce and challenge. Outside a window it returns the next opening time.
- [ ] `open-now` and `close-now` work for an admin and return `403` for a warden.
- [ ] After close, each student with no mark has an `ABSENT` row, and the nonces are gone.
- [ ] Restarting the scheduler mid-window does not issue a second set of nonces.
- [ ] An off day opens no window.

## Deferred to Phase 13

- Concurrency test: many simultaneous consumes of one nonce.
- Time-boundary tests at the exact open and close seconds.
- Scheduler restart and catch-up tests.

## Risks

| Risk | What to do |
|---|---|
| Server clock is wrong | Sync the host with network time. Log the offset at startup. |
| Students forget to open the app at window time | Warden announces the time. Home shows the opening time once opened (Phase 4). Reminder method is an open question in the PRD. |
| Scheduler stops unnoticed | `/v1/health` reports the scheduler's last heartbeat from Redis |
| Upstash command quota runs out during a window | Nonce issue is one pipeline per window, and the scheduler polls every 15 s. Count commands in the Phase 13 load test and check the plan limits before the pilot. |
| Stub endpoints get exposed | Guard them with `APP_ENV=local` until Phase 8 replaces the stub |

## Hand-off to Phase 4

Phase 4 needs the nonce and status endpoint and its response format.
