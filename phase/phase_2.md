# Phase 2: Backend Core

| | |
|---|---|
| **Type** | Implementation |
| **Depends on** | Phases 0, 1 |
| **Unlocks** | Phases 3, 6, 8, 10 |
| **Lead** | Backend |

## Goal

A running FastAPI service with the plumbing every later endpoint needs: configuration, database and Redis connections, warden authentication, a single error format, structured logs, and an audit writer. No attendance logic yet.

## Outcome

- `uvicorn` starts the API and `/v1/health` reports the state of the database and Redis.
- A request with a valid warden token reaches a protected route. Anything else gets `401` or `403`.
- Every error leaves the API in the same JSON shape.
- Later phases add a router file and nothing else.

## Scope

**In:** project skeleton, settings, connections, auth dependency, error handling, logging, audit helper, room and student read endpoints.
**Out:** windows, nonces, verification, enrollment, WebSocket.

---

## Tasks

### 1. Project skeleton

```text
backend/
├── app/
│   ├── main.py              App factory, router registration, lifespan
│   ├── config.py            Settings loaded from env
│   ├── deps.py              Shared dependencies (db, redis, current warden)
│   ├── errors.py            Error types and handlers
│   ├── logging.py           JSON log setup, request ID
│   ├── db/
│   │   ├── pool.py          Connection pool
│   │   └── queries/         One module per table group
│   ├── auth/
│   │   └── supabase.py      Token verification
│   ├── routers/
│   │   ├── health.py
│   │   ├── rooms.py
│   │   └── students.py
│   ├── services/
│   │   └── audit.py
│   └── schemas/             Pydantic request and response models
├── pyproject.toml
├── .env.example
└── README.md
```

| # | Task |
|---|---|
| 1.1 | Create `pyproject.toml` with pinned versions: `fastapi`, `uvicorn[standard]`, `pydantic-settings`, `asyncpg`, `redis`, `pyjwt[crypto]`, `httpx`, `cryptography` |
| 1.2 | Add `ruff` for lint and format, with one config shared by `backend/` and `face/` |
| 1.3 | Write `backend/README.md` with the three commands to install, configure and run |

### 2. Configuration

| # | Task |
|---|---|
| 2.1 | One `Settings` class in `config.py` reads every variable in `backend/.env.example` |
| 2.2 | The service refuses to start if a required value is missing, and names the missing variable |
| 2.3 | The five weights are checked at startup: they must add up to 1.0 |
| 2.4 | `THRESHOLD_PRESENT` must be greater than `THRESHOLD_REVIEW` |
| 2.5 | Settings are never printed in full. Startup logs list variable names only. |

### 3. Connections

| # | Task |
|---|---|
| 3.1 | Open an `asyncpg` pool at startup and close it at shutdown, using FastAPI's lifespan |
| 3.2 | Open one async Redis client from `REDIS_URL`. The URL is `rediss://` (TLS). Set a connection timeout and a small retry limit. Refuse to start if the URL is not `rediss://`. |
| 3.3 | Write SQL by hand in `db/queries/`, with parameters. No string-built SQL anywhere. |
| 3.4 | If Supabase's pooled connection is used in transaction mode, turn off prepared statement caching in `asyncpg` |

### 4. Warden authentication

The dashboard logs in with Supabase Auth and sends the access token as `Authorization: Bearer <token>`.

| # | Task |
|---|---|
| 4.1 | `auth/supabase.py` verifies the token's signature, expiry and audience |
| 4.2 | Read the role from `app_metadata.role`. Accept only `warden` or `admin`. |
| 4.3 | Require the token's assurance level claim `aal` to be `aal2`, which means the user passed the TOTP step. Make this switchable with `REQUIRE_MFA`, default `true`. |
| 4.4 | Expose `current_warden` and `require_admin` as dependencies for routes |
| 4.5 | Missing or bad token returns `401`. Valid token with the wrong role returns `403`. |

Student requests are not authenticated here. They are authenticated by device signature in Phase 8.

### 5. Errors

Every error response has this shape:

```json
{
  "error": {
    "code": "VALIDATION_FAILED",
    "message": "Human-readable summary",
    "details": [{"field": "closes_at", "issue": "must be after opens_at"}],
    "request_id": "..."
  }
}
```

| # | Task |
|---|---|
| 5.1 | Define `AppError` with `code`, `status` and `message` |
| 5.2 | Register handlers for `AppError`, validation errors and unexpected exceptions |
| 5.3 | Unexpected exceptions return `500` with a generic message. The detail goes to the log only. |
| 5.4 | Request models reject unknown fields |

### 6. Logging

| # | Task |
|---|---|
| 6.1 | JSON logs, one line per request: request ID, method, path, status, latency |
| 6.2 | Middleware creates a request ID and returns it as `X-Request-ID` |
| 6.3 | A redaction filter drops these keys wherever they appear: `authorization`, `signature`, `integrity_token`, `embedding`, `frames`, `nonce` |
| 6.4 | Student IDs in application logs are written as a short hash, never raw |

### 7. Audit writer

| # | Task |
|---|---|
| 7.1 | `services/audit.py` exposes `write(actor, action, target_id, payload)` |
| 7.2 | It runs inside the caller's database transaction, so an action and its audit row succeed or fail together |
| 7.3 | The payload goes through the same redaction as logs |

### 8. First endpoints

These prove the stack works end to end and give the dashboard something to render in Phase 10.

| Method | Path | Auth | Returns |
|---|---|---|---|
| GET | `/v1/health` | None | `{status, db, redis, version}` |
| GET | `/v1/rooms` | Warden | Rooms with floor and student count |
| GET | `/v1/rooms/{room_id}` | Warden | One room with its students and access points |
| GET | `/v1/students` | Warden | Students, filterable by room or floor |

No endpoint ever returns an embedding or a public key.

---

## Exit criteria

- [ ] The API starts with one command from `backend/README.md`.
- [ ] `/v1/health` reports `ok` for both the database and Redis, and `degraded` if either is stopped.
- [ ] Removing a required env variable stops startup with a message naming it.
- [ ] `/v1/rooms` returns seeded rooms with the test warden's token.
- [ ] The same call returns `401` with no token and `403` with a token lacking the role.
- [ ] A token from a login that skipped TOTP is rejected while `REQUIRE_MFA=true`.
- [ ] A malformed request returns the standard error shape with a request ID.
- [ ] A log line for a request carrying a token shows no token.

## Deferred to Phase 13

- Unit tests for settings validation, token verification and redaction.
- Contract tests for the error shape.

## Risks

| Risk | What to do |
|---|---|
| Token verification method differs by Supabase project settings | Check which signing method the project uses in Phase 0, and support that one |
| Pooled connections reject prepared statements | Covered by task 3.4 |
| Logs leak sensitive fields added later | New request fields that are sensitive are added to the redaction list in the same commit |

## Hand-off to Phase 3

Phase 3 needs the app factory, the Redis client, the warden dependency and the audit writer.
