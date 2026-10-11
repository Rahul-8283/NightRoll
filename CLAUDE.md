# NightRoll

Hostel attendance marked from bed. Built for the Genesis hackathon at our college. Problem: hostellers on floors 1, 2, 3… walk down to the ground floor every night at 10:00 PM to mark attendance. NightRoll lets them mark it from their bed on their phone, while still proving they are who they say, in their own room, on their own device, inside the warden's window.

## Current status

- Built and on `feat/native`: the API (gates, scoring, review, windows, enrollment, exports, audit, System status), the scheduler, the face worker, the warden dashboard, the Expo app, and the Supabase migrations. Phases 1 to 11 are done; Phase 12 is done except the release app build (task 8) and the demo environment (task 9).
- Phase 12 added: Dockerfiles and `infra/docker-compose.yml` (nginx, api, scheduler, face-worker), HTTPS and the real client address through nginx, startup safety checks (`APP_ENV` is `local`, `demo`, `pilot` or `production`), Redis rate limits, JSON logs with a request ID from nginx to the face worker, `/v1/metrics`, the admin System page and alert banner, the `NetworkVerifier.locate` contract, `docs/runbook.md`, and a release-build plugin that pins the app to the server's certificate authority.
- Still to do: the signed release build and the two demo phones (Phase 12 tasks 8 and 9), then Phase 13 (load, security checks, timed demo rehearsals). The Docker images were built once to check the Dockerfiles; the full stack has not yet been run from Compose.
- Plan lives in the Claude Docs pages "NightRoll: Hostel Attendance From Your Bed" and "NightRoll Geofencing", the "NightRoll Architecture" artifact, and in `docs/` (PRD, TRD, architecture, runbook, network adapter). Those are the sources; this file is the working summary.
- Start each service from its own README; run the whole server side with `docker compose -f infra/docker-compose.yml up -d --build` (see `infra/README.md`).

## Core idea

Three things must be proven at once; no single factor is enough:

1. **Right person:** face match plus a liveness challenge.
2. **Right place:** the phone is on the student's own room network, checked server-side (source IP / controller / RADIUS), with a WiFi-fingerprint check as a supporting signal.
3. **Right device, right now:** a hardware-bound Keystore key signs a one-time nonce issued for tonight's window.

Scores are fused into a trust decision instead of a single yes/no, with hard gates that run first.

## Architecture

- **Phone (Android first):** Expo app (React Native, TypeScript) with Kotlin Expo Modules, run as a development build. Liveness challenge, face capture (ML Kit + TFLite for on-device pre-check), WiFi scan (BSSID, SSID, RSSI, band), Play Integrity token, Keystore signer. Sends a signed payload `{sid, nonce, bssid, rssi, frames, ts}`.
- **Network:** the request goes out through the room AP, so source IP identifies the room subnet. A VPN or proxy fails here.
- **Backend (FastAPI):** API gateway → verification orchestrator with crypto verifier (signature + nonce freshness), integrity verifier (Play Integrity), network verifier (source IP / controller / RADIUS), face verifier (InsightFace ArcFace + anti-spoof), fusion engine. Upstash Redis (hosted, TLS) holds nonces and window state. Supabase PostgreSQL + pgvector holds students, rooms, AP map, embeddings, logs. Supabase Auth handles warden and admin login (with MFA). Supabase Storage holds encrypted frames on a private bucket, deleted after 24 hours.
- **Outputs:** warden dashboard (React, WebSocket, live floor heatmap, review queue, absentees, CSV export), students open the app at window time to see status and mark, student result screen with a reason.
- **Enrollment (once, warden's office):** verified face → ArcFace embedding (store the vector, not the photo); device keypair registered; 3–5 room WiFi scans → room fingerprint; room ↔ BSSID ↔ subnet mapping.

### Hard gates (any fail = rejected)

- Server-clock inside the window
- Signature valid and nonce fresh (single use)
- Play Integrity pass
- No VPN / proxy / mock location
- Source IP inside the room subnet

### Scored factors (after gates pass)

Face match, liveness + anti-spoof, room WiFi fingerprint, own-AP RSSI check, AP-side RSSI agreement. Weights and thresholds are **provisional**; see Open decisions.

## Geofencing (WiFi as the fence)

GPS is not used for the decision: it is inaccurate indoors and easy to fake. GPS may only be a warning signal, and only if it is accurate (about 20 m) and clearly outside the hostel.

- **Fingerprint:** each room's pattern of visible BSSIDs and signal strengths (dBm, 2.4 vs 5 GHz), from 3–5 scans at enrollment.
- **Check each night:** own room router present and strong; expected neighbours mostly present; relative strengths similar to usual; no unexpected outside networks.
- **5 GHz:** an effect, not an enforceable rule. Phones pick their own band. Use it only if the walk test shows it helps.
- **Walk test:** set limits by measurement, not guesswork. Stand inside several rooms, then outside the compound wall, in the corridor, next door, and on the floor below. Put limits between the two groups. Edge rooms near the wall get stricter limits.
- **Drift:** blend in confident "present" scans slowly; warden can trigger a re-scan after a router change; repeated reviews from one room flag the fingerprint as stale.
- **Android:** WiFi scans need location permission and location turned on; scans are throttled (about 4 per 2 minutes), so one scan per night.
- **iOS:** no full WiFi scan; iPhone users stay on the ground-floor scanner for now.

## Night flow

1. Warden sets the window (default 22:00–22:30) and any off days.
2. Window opens: server issues one nonce per student (Redis, TTL = window end). Students open the app themselves; nothing is pushed.
3. Student opens app in bed. VPN / proxy / mock location → blocked.
4. Liveness challenge → face frames → WiFi scan → integrity token → Keystore signs the payload.
5. POST to verify endpoint through the room AP. Gates run, then scoring, then fusion.
6. PRESENT → room tile turns green on dashboard. NEEDS REVIEW → warden queue. REJECTED → student sees the reason and is pointed to the ground-floor scanner.
7. Window closes: absentee list to warden.
8. Optional later: random spot-checks after the window (not in MVP).

## MVP scope (hackathon)

Build first:
- Keystore-signed nonce, one per student per night
- Source-IP / subnet check (demo with two real routers)
- Face match with a basic liveness challenge
- Warden dashboard with a room tile view and absentee list

Defer (name them on a "next" slide, don't build them):
- Anti-spoof model beyond the liveness challenge
- WiFi fingerprinting and walk test (unless time allows; it's a strong demo beat)
- Spot-checks, anomaly detection, auto-updating fingerprints
- iOS

## Hackathon demo

Two routers standing in for Room 101 and Room 102.

1. Mark from Room 101 → PRESENT.
2. Switch to the 102 router → network gate fails → REJECTED.
3. Hold up a photo or phone video → liveness / anti-spoof rejects.
4. Mark on a teammate's phone → signature fails.
5. (If built) walk out while on WiFi → fingerprint mismatch → REJECTED with reason.

Be honest in the demo: the subnet check needs real router subnets; phone hotspots won't show it.

## Open decisions

- **Window time:** settled at 22:00 to 22:30 (`WINDOW_DEFAULT_OPEN` and `WINDOW_DEFAULT_CLOSE`). The warden can change any night.
- **Trust weights and cutoffs:** set to 0.30 face, 0.30 fingerprint, 0.20 liveness, 0.15 own access point, 0.05 access point agreement, with PRESENT at 0.80 or more and review from 0.60. Still provisional until the walk test. A face or liveness score of zero rejects whatever the total, and a room with no learned Wi-Fi fingerprint is capped at review.
- **Face threshold:** 0.45 to 0.50 cosine similarity for ArcFace, to be tuned on our own enrollment data.
- **Network path:** the demo and first pilot use the subnet check. Whether the hostel offers per-room or per-floor subnets, controller API access, or RADIUS accounting is still unknown; `docs/network-adapter.md` says what to ask the network admin for.
- **Supabase backup plan:** not recorded. The runbook says where to check and where to write it down.
- **Team:** four people; split is app + liveness, backend + crypto + network, face service, dashboard + demo.

## Constraints and gotchas

- Android only for the hackathon.
- App: use Expo. Native code goes in Expo Modules. Expo Go is for screens only; anything native needs a development build made with EAS.
- No push notifications. Students open the app at window time. Do not add FCM or any other push service without asking.
- Privacy: store face embeddings only, never photos; delete captured frames after 24 hours; explicit consent at enrollment; say so on the pitch slide.
- Biometric data is sensitive. Don't log embeddings or raw frames.
- Redis is hosted on Upstash. Use the `rediss://` URL from `backend/.env` and never commit it.
- No new hardware in the core design. Optional: a spare phone for demos, a cheap router per demo room.
- Never hard-code hostel network details (BSSIDs, subnets, controller credentials). Keep them in config or env files that are not committed.
- Supabase: the service role key is server-side only and never shipped in the app or dashboard bundle. The app and dashboard use only the public anon key, with row-level security on every table. Keys live in env files that are not committed.
- Warden override exists for every auto-decision. The ground-floor scanner stays as the fallback for dead phones, no WiFi, or router outage.

## Git workflow

- After completing each phase or task the user specifies, stage and commit all changes.
- Use conventional commit format: `feat:`, `fix:`, `chore:`, `refactor:`, `docs:`, `test:`.
- Keep commit messages short and precise. Describe only what changed, nothing extra.
- Never add Claude (or any AI model) as a co-author. No `Co-Authored-By` trailers.
- Every commit must be pushed to GitHub. Never leave commits only local.
- Push to the branch the user specifies (`git push origin <branch>`). Create it if it doesn't exist (`git checkout -b <branch>`).
- Never open a PR or merge unless asked.

Example: `feat: add GA mutation operators and population seeding`

## Conventions for working in this repo

- Keep the plan documents as the source of truth for product decisions; update this file when a decision is made.
- Don't introduce hardware dependencies without asking.
- Don't commit credentials, BSSID or subnet maps from the real hostel, or student data.
- Test factors separately (signature, nonce, subnet, face, liveness) so each gate's failure is visible in the logs.
