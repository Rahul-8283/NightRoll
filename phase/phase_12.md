# Phase 12: Hardening, Deployment and Demo Environment

| | |
|---|---|
| **Type** | Implementation |
| **Depends on** | Phases 1 to 11 |
| **Unlocks** | Phase 13 |
| **Leads** | Backend, with the whole team for the demo environment |

## Goal

Turn a set of services that work on developers' machines into one system that starts with a single command, is safe to put on a shared network, can be watched while it runs, and is set up on the actual demo hardware. This is the last implementation phase. Nothing new is built for users here.

## Outcome

- One Docker Compose file starts the whole server side.
- HTTPS in front of everything, with the correct client address reaching the network gate.
- Unsafe settings cannot start outside local development.
- Logs, metrics and alerts cover an attendance window.
- The demo environment is assembled: two routers, two phones, one laptop, seeded and enrolled.
- A signed release build of the app is installed on the test phones.

## Scope

**In:** containers, reverse proxy, TLS, startup safety checks, rate limits, operational jobs, observability, network adapter contract, release app build, demo environment, runbook, documentation update.
**Out:** any testing beyond confirming each item works once (Phase 13).

---

## Tasks

### 1. Containers

| # | Task |
|---|---|
| 1.1 | `backend/Dockerfile`: slim Python base, pinned dependencies, runs as a non-root user |
| 1.2 | `face/Dockerfile`: same approach. Models are mounted or downloaded at build with checksum verification, not committed. |
| 1.3 | `dashboard/Dockerfile`: build the static files, serve them from nginx |
| 1.4 | Extend `infra/docker-compose.yml` with `nginx`, `api`, `scheduler`, `face-worker` and `redis` |
| 1.5 | Add a `.dockerignore` to each service so env files, secrets and local data never enter an image |
| 1.6 | Health checks on every service. `api` waits for `redis` and `face-worker` to be healthy. |
| 1.7 | Restart policy `unless-stopped` |
| 1.8 | Only nginx publishes ports. Redis, the face worker and the API are reachable inside the Compose network only. |
| 1.9 | Env files are passed at run time. No secret is baked into an image. |

Supabase is hosted, so there is no database container. The host needs outbound internet access to Supabase, Firebase and Google.

### 2. Reverse proxy and TLS

| # | Task |
|---|---|
| 2.1 | `infra/nginx/nightroll.conf`: serve the dashboard at `/`, proxy `/v1/` to the API, and upgrade `/v1/ws/` to WebSocket |
| 2.2 | Terminate HTTPS at nginx. Redirect HTTP to HTTPS. |
| 2.3 | For the demo and a LAN pilot, use a certificate from a local certificate authority (for example `mkcert`), and install that authority on the test phones and the warden's laptop |
| 2.4 | Set the forwarded-for header to the real client address, overwriting anything the client sent. Set `TRUSTED_PROXY_IPS` to nginx's address inside the Compose network. |
| 2.5 | Limit upload size to match the verify endpoint's limits |
| 2.6 | Security headers on the dashboard: strict transport security, a content security policy that allows only the API and Supabase, no framing, no MIME sniffing |
| 2.7 | Pin the app to the server's certificate authority, so a different certificate on the same network is refused |

Task 2.4 matters most. If the proxy passed along a client-supplied address, a phone outside the room could claim an inside address and pass the network gate.

### 3. Startup safety checks

The API refuses to start, with a clear message, when `APP_ENV` is `pilot` or `production` and any of these is true:

| Check |
|---|
| `PLAY_INTEGRITY_ENFORCE` is false |
| `NETWORK_VERIFY_MODE` is `off` |
| `REQUIRE_MFA` is false |
| `TRUSTED_PROXY_IPS` is empty or allows every address |
| `FACE_WORKER_TOKEN` is shorter than 32 characters |
| The face worker reports anti-spoof unavailable |

For the demo, `APP_ENV=demo` allows relaxed settings but prints a banner at startup listing each one, so the team knows exactly what is relaxed on stage.

### 4. Rate limits

| Route | Limit | Keyed by |
|---|---|---|
| `POST /v1/attendance/verify` | 1 per 20 s, 3 attempts per window | Student |
| `POST /v1/enrollments` | 5 failed codes per 15 min | Student |
| `GET /v1/attendance/nonce` | 10 per minute | Student |
| Any student route failing signature checks | 20 per minute | Client address |
| Warden API | 300 per minute | Warden |
| Export | 10 per hour | Warden |

Counters live in Redis. A limited request gets `429` with a `Retry-After` header.

### 5. Operational jobs

| Job | Runs | Does |
|---|---|---|
| Frame cleanup | Hourly, in the face worker | Deletes frames older than 24 hours (built in Phase 5; confirm it runs in the container) |
| Scheduler heartbeat | Every 15 s | Writes a timestamp to Redis; `/v1/health` reports it stale after 60 s |
| Expired code cleanup | Daily | Removes used and expired enrollment codes |
| Room health | Nightly, after close | Computes the flags from Phase 11 |

Database backups are handled by Supabase. Write down in the runbook which backup option the project's plan includes and how a restore is requested.

### 6. Observability

| # | Task |
|---|---|
| 6.1 | All services log JSON to standard output with the same request ID, passed from nginx through the API to the face worker |
| 6.2 | `GET /v1/metrics` (admin, or internal network only), in Prometheus text format |
| 6.3 | Metrics: requests and latency per route; verdicts by type; gate failures by reason; per-stage timings; face worker latency; pushes sent and failed; open WebSocket connections; scheduler heartbeat age |
| 6.4 | An admin-only "System" page on the dashboard: service health, tonight's verdict counts, gate failures by reason, latency, last cleanup, last scheduler heartbeat |
| 6.5 | Alerts shown as a banner on the dashboard: face worker down during an open window; scheduler heartbeat stale; rejection rate above 20% in the last 5 minutes; push failure rate above 10% |

A full monitoring stack is not needed for the pilot. The System page and the logs are enough.

### 7. Network adapter contract

The demo and the first pilot use the subnet check. This task makes the upgrade path concrete without building it.

| # | Task |
|---|---|
| 7.1 | Finalise the `NetworkVerifier` interface: `locate(device_identifier) → {bssid, signal, seen_at}` or not found |
| 7.2 | Write `docs/network-adapter.md`: what a controller adapter and a RADIUS adapter must return, and what the campus network admin needs to provide for each |
| 7.3 | Leave `controller` and `radius` modes raising "not configured" with a pointer to that document |

### 8. Release app build

| # | Task |
|---|---|
| 8.1 | Build a release APK signed with the release keystore |
| 8.2 | Turn on code shrinking, with keep rules for the native modules |
| 8.3 | Point `API_BASE_URL` at the demo host's HTTPS address |
| 8.4 | Remove any debug screens and local-only switches from the release build |
| 8.5 | Install on both test phones and the spare |
| 8.6 | Confirm Play Integrity returns a verdict for this build, and record what it says |

### 9. Demo environment

| # | Task |
|---|---|
| 9.1 | Fix the laptop's address on the upstream network so the phones and the certificate keep working |
| 9.2 | Set up the two routers as Room 101 and Room 102, with different SSIDs, both uplinked to the laptop's network |
| 9.3 | Record each router's BSSIDs and the address the laptop sees for it. Put them in `config/rooms.local.json`. |
| 9.4 | Add any other Wi-Fi networks visible at the venue to the room map as `hostel`, so the fingerprint has neighbours to compare |
| 9.5 | Run the seed script against a fresh `nightroll-demo` Supabase project, separate from development |
| 9.6 | Create the demo warden and admin accounts and set up their authenticator apps |
| 9.7 | Enroll two teammates as students: one in Room 101 with phone A, one in Room 102 with phone B |
| 9.8 | Capture each room's Wi-Fi fingerprint at the demo location, or as close to it as possible. A fingerprint captured elsewhere will not match. |
| 9.9 | Prepare the spoof prop: a printed photo and a second phone showing a video of the Room 101 teammate |
| 9.10 | Add a "Reset demo" admin action: closes any open window and clears tonight's marks for the demo students, so the demo can be run again from the start |

`Reset demo` exists only when `APP_ENV=demo` and is refused in every other mode.

### 10. Runbook

Write `docs/runbook.md`.

| Section | Content |
|---|---|
| Start and stop | The exact commands |
| Before a window | Checklist: health page green, scheduler heartbeat fresh, face worker ready |
| During a window | What each alert means and what to do |
| Router down in a room | Students use the ground-floor scanner; warden records manual marks |
| Server down | Fall back to the ground-floor scanner for everyone; how to restart |
| A student's phone is lost | Deactivate the device, issue a new enrollment code |
| A warden loses their authenticator | How an admin resets it |
| A secret is leaked | Which key to rotate and where |
| Restoring data | How a Supabase restore is requested |

### 11. Documentation update

| # | Task |
|---|---|
| 11.1 | Update `README.md`: replace the "design stage" status with real setup steps, and the planned layout with the actual one |
| 11.2 | Update `docs/TRD.md` and `docs/architecture.md` for every change made during the build: gate order, the submission envelope, verdict floors, enrollment codes, the missing database container |
| 11.3 | Update `CLAUDE.md` so its status and open decisions are current |
| 11.4 | Check every `.env.example` lists every variable the code reads, and nothing it does not |

---

## Exit criteria

- [ ] `docker compose up` on a clean machine with filled env files brings up every service healthy.
- [ ] Only ports 80 and 443 are open on the host.
- [ ] The dashboard and API are served over HTTPS, and the test phones trust the certificate.
- [ ] A request that sends its own forwarded-for header is seen by the API with its real address.
- [ ] Starting with `APP_ENV=pilot` and enforcement off fails with a clear message.
- [ ] A fourth verify attempt in one window gets `retry_allowed: false`, and rapid repeats get `429`.
- [ ] The System page shows live health, counts and latency.
- [ ] Stopping the face worker during an open window raises the dashboard alert.
- [ ] The release APK is installed on all test phones and completes a mark.
- [ ] The demo environment is seeded and enrolled, and "Reset demo" returns it to the start.
- [ ] `docs/runbook.md` exists and a teammate who did not write it can start the system by following it.
- [ ] README, TRD, architecture and `CLAUDE.md` match what was built.

## Deferred to Phase 13

- Load test of the packaged system.
- Security checks against the deployed stack.
- Full, timed demo rehearsals.

## Risks

| Risk | What to do |
|---|---|
| Venue network differs from the practice setup | Bring the routers and a switch so the demo network is self-contained; only the laptop needs internet |
| No internet at the venue | Supabase, Firebase and Play Integrity all need it. Bring a phone hotspot as the laptop's uplink, and have the backup video ready. |
| Phones do not trust the local certificate | Install the certificate authority during setup, and check it on each phone |
| Fingerprint captured in a different place than the demo | Capture at the venue during setup (task 9.8) |

## Hand-off to Phase 13

Phase 13 tests the system exactly as packaged here, on the demo hardware.
