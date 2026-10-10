# NightRoll

Hostel attendance marked from bed. Built for the Genesis hackathon at our college. Problem: hostellers on floors 1, 2, 3… walk down to the ground floor every night at 10:00 PM to mark attendance. NightRoll lets them mark it from their bed on their phone, while still proving they are who they say, in their own room, on their own device, inside the warden's window.

## Current status

- Repo contains only README.md, LICENSE, and .git. No code yet.
- Plan lives in the Claude Docs pages "NightRoll: Hostel Attendance From Your Bed" and "NightRoll Geofencing", and in the "NightRoll Architecture" artifact. Those are the sources; this file is the working summary.
- Two versions of the design currently conflict (see Open decisions). Resolve them before building.

## Core idea

Three things must be proven at once; no single factor is enough:

1. **Right person:** face match plus a liveness challenge.
2. **Right place:** the phone is on the student's own room network, checked server-side (source IP / controller / RADIUS), with a WiFi-fingerprint check as a supporting signal.
3. **Right device, right now:** a hardware-bound Keystore key signs a one-time nonce issued for tonight's window.

Scores are fused into a trust decision instead of a single yes/no, with hard gates that run first.

## Architecture

- **Phone (Android first):** React Native or Flutter app. Liveness challenge, face capture (ML Kit + TFLite for on-device pre-check), WiFi scan (BSSID, SSID, RSSI, band), Play Integrity token, Keystore signer. Sends a signed payload `{sid, nonce, bssid, rssi, frames, ts}`.
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

- **Window time:** 22:00–22:30 (diagram artifact) vs 9:55–10:15 (architecture text). The user's own problem is 10 PM, so default to 22:00–22:30 unless told otherwise.
- **Trust weights and cutoffs:** diagram says 0.30 / 0.20 / 0.30 / 0.15 / 0.05 with PRESENT ≥ 0.80, REVIEW 0.60–0.80, REJECT < 0.60. Text says 0.35 / 0.25 / 0.25 / 0.10 / 0.05 with PRESENT ≥ 0.85. Pick one set and mark it provisional until the walk test.
- **Face threshold:** ~0.45–0.50 cosine similarity for ArcFace, to be tuned on our own enrollment data.
- **Network path:** does the hostel give per-room or per-floor subnets, controller API access, or RADIUS accounting? Unknown. Confirm with the network admin before promising production.
- **Team:** four people; split is app + liveness, backend + crypto + network, face service, dashboard + demo.

## Constraints and gotchas

- Android only for the hackathon.
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
