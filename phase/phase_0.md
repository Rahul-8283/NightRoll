# Phase 0: Base Setup

| | |
|---|---|
| **Type** | Setup (no feature code) |
| **Depends on** | Nothing |
| **Unlocks** | Every other phase |
| **Leads** | Whole team |

## Goal

Every teammate can clone the repo, fill in one env file per service, start the local services, and reach every external account the project needs. No feature is built here. The phase ends when nothing outside the code can block Phase 1.

## Outcome

- The repo has its final folder structure, with a placeholder in each service folder.
- `.gitignore` and a `.env.example` per service are committed. No real secret is in git.
- Supabase and Google Cloud projects exist, and every credential is shared with the team outside git.
- Redis is hosted on Upstash (TLS). The team shares one development database and uses a separate one for tests.
- Two test Android phones and two routers are ready for the demo network.
- Four risk spikes are done and their results are written down.

---

## 1. Accounts and access

| # | Task | Result |
|---|---|---|
| 1.1 | Create one team Google account (or pick one owner account) for Google Cloud | Shared login in the team password manager |
| 1.2 | Create a Supabase organisation and a project named `nightroll-dev` | Project URL and keys |
| 1.3 | Create a Google Cloud project named `nightroll`. Record the Android package name `com.zerolatency.nightroll` for the Play Integrity setup. | Project ID and number noted |
| 1.4 | In the linked Google Cloud project, enable the Play Integrity API | API enabled, project number noted |
| 1.5 | Give all four teammates write access to the GitHub repo | Everyone can push to `base` |
| 1.6 | Create an Upstash Redis database for development (TLS on, region closest to the hostel). Copy its `rediss://` URL. | URL in the team password manager |
| 1.7 | Ask the campus network admin the three network questions (section 10) | Written answer, or a date for one |
| 1.8 | Create a free Expo account for EAS builds and add the team to it | Team account in the password manager |

The package name is fixed here. Changing it later breaks Play Integrity.

## 2. Tooling versions

Everyone installs the same versions so builds match.

| Tool | Version | Used for |
|---|---|---|
| Python | 3.12 | Backend, face worker |
| Node.js | 20 LTS | App, dashboard |
| JDK | 17 | Android build |
| Android Studio | Current stable, with SDK Platform 34 or newer | Emulator and local builds (optional if you only use EAS cloud builds) |
| Docker Desktop | Current stable | Later services (Phase 12) |
| Supabase CLI | Current stable | Migrations |
| Git | Any recent | Version control |
| Expo account and EAS CLI | Current | Development and production builds of the app | Free Expo account, then `npx eas-cli login` (no global install needed) |

The app is an Expo project. Expo Go runs only screens without native code. The Keystore, Wi-Fi and Play Integrity code is Kotlin in Expo Modules, so the test phones run a development build made with EAS.

## 3. Folder structure

Create these folders. Each gets a short `README.md` saying what goes there, so git keeps the folder.

```text
NightRoll/
├── app/                  Expo app (TypeScript) with Kotlin modules for Android
├── backend/              FastAPI service: gates, scoring, windows, reviews
│   └── app/
├── face/                 Face worker: embeddings and anti-spoof
│   └── models/           Model files (gitignored)
├── dashboard/            React warden dashboard
├── supabase/             Supabase CLI project
│   └── migrations/       SQL migrations
├── infra/                Docker Compose, nginx config, deploy scripts
├── config/               Non-secret config and example room map
├── scripts/              One-off scripts and Phase 0 spikes
│   └── spikes/
├── docs/                 PRD, TRD, architecture
├── phase/                Phase plans (this folder)
├── .gitignore
├── CLAUDE.md
├── LICENSE
└── README.md
```

`supabase/` sits at the repo root because the Supabase CLI expects it there.

## 4. `.gitignore`

Commit this file at the repo root before any service code exists.

```gitignore
# Secrets and credentials
.env
.env.*
!.env.example
*.pem
*.p12
*.jks
*.keystore
!debug.keystore
*service-account*.json

# Real hostel data
config/rooms.local.json
config/*.local.*

# Python
__pycache__/
*.py[cod]
.venv/
venv/
.pytest_cache/
.ruff_cache/
.mypy_cache/

# Node
node_modules/
dist/
build/
.vite/
npm-debug.log*
yarn-error.log*

# Expo and Android (generated native folders, only if created locally)
app/android/.gradle/
app/android/app/build/
app/android/build/
app/android/local.properties
app/android/.cxx/
*.apk
*.aab
*.hprof
.metro-health-check*

# Models and biometric data
face/models/*
!face/models/README.md
*.onnx
*.tflite
frames/
captures/

# Supabase CLI
supabase/.temp/
supabase/.branches/

# Editors and OS
.DS_Store
.idea/
.vscode/*
!.vscode/extensions.json
*.log
```

Before the first push after this change, run `git status` and confirm no env file, key or JSON credential is listed.

## 5. Env files

One `.env.example` per service, committed with empty or dummy values. Each teammate copies it to `.env` and fills it in. Real values never go in git.

### `backend/.env.example`

```dotenv
# Runtime
APP_ENV=local
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=info
TIMEZONE=Asia/Kolkata

# Supabase (server side only)
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_JWT_SECRET=
DATABASE_URL=

# Redis (Upstash, TLS)
REDIS_URL=rediss://default:<password>@<endpoint>.upstash.io:6379

# Face worker
FACE_WORKER_URL=http://localhost:8100
FACE_WORKER_TOKEN=

# Google service account (Play Integrity decode)
GOOGLE_APPLICATION_CREDENTIALS=./secrets/google-service-account.json

# Play Integrity
PLAY_INTEGRITY_PACKAGE_NAME=com.zerolatency.nightroll
PLAY_INTEGRITY_ENFORCE=false

# Attendance window defaults
WINDOW_DEFAULT_OPEN=22:00
WINDOW_DEFAULT_CLOSE=22:30

# Network gate: subnet | controller | radius | off
NETWORK_VERIFY_MODE=subnet
TRUSTED_PROXY_IPS=127.0.0.1

# Trust score (provisional, tuned in Phase 13)
WEIGHT_FACE=0.30
WEIGHT_FINGERPRINT=0.30
WEIGHT_LIVENESS=0.20
WEIGHT_OWN_AP=0.15
WEIGHT_AP_AGREEMENT=0.05
THRESHOLD_PRESENT=0.80
THRESHOLD_REVIEW=0.60
```

### `face/.env.example`

```dotenv
FACE_HOST=0.0.0.0
FACE_PORT=8100
FACE_WORKER_TOKEN=
FACE_MODEL_NAME=buffalo_l
FACE_MODEL_DIR=./models
ANTISPOOF_MODEL_PATH=./models/antispoof.onnx

SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
FRAMES_BUCKET=frames
FRAME_RETENTION_HOURS=24
```

### `dashboard/.env.example`

```dotenv
VITE_API_BASE_URL=http://localhost:8000/v1
VITE_WS_URL=ws://localhost:8000/v1/ws/rooms
VITE_SUPABASE_URL=
VITE_SUPABASE_ANON_KEY=
```

### `app/.env.example`

```dotenv
EXPO_PUBLIC_API_BASE_URL=http://10.0.2.2:8000/v1
EXPO_PUBLIC_GOOGLE_CLOUD_PROJECT_NUMBER=
```

Rules:
- The Supabase **service role key** appears only in `backend/.env` and `face/.env`. It never goes in the app or the dashboard.
- The dashboard gets only the **anon key**. The app gets no Supabase key at all; it talks only to the NightRoll API.
- `PLAY_INTEGRITY_ENFORCE=false` is for local work on emulators only. The demo and pilot run with `true`.

## 6. Credentials checklist

| Credential | Where to get it | Where it lives | In git? |
|---|---|---|---|
| Supabase project URL | Supabase dashboard, Project Settings, API | `backend/.env`, `face/.env`, `dashboard/.env` | No |
| Supabase anon key | Same page | `dashboard/.env` | No |
| Supabase service role key | Same page | `backend/.env`, `face/.env` | No |
| Supabase JWT secret | Project Settings, API, JWT settings | `backend/.env` | No |
| Database connection string | Project Settings, Database (use the pooled connection) | `backend/.env` | No |
| Google service account JSON (Play Integrity) | Google Cloud console, IAM, Service accounts | `backend/secrets/` | No |
| Google Cloud project number | Google Cloud console, project dashboard | `app/.env` as `EXPO_PUBLIC_GOOGLE_CLOUD_PROJECT_NUMBER` | No |
| Face worker token | Generate locally: `openssl rand -hex 32` | `backend/.env`, `face/.env` | No |
| Android release keystore | Generate once with `keytool`, one copy with the app lead | Password manager | No |

Share credentials through the team password manager or an encrypted note. Do not paste them in the group chat.

## 7. Redis (Upstash)

Redis is hosted, so there is no Redis container to run. Each teammate pastes the same development `rediss://` URL into `backend/.env`.

Check it from any machine with Docker:

```bash
docker run --rm redis:7 redis-cli --tls -u "<REDIS_URL>" ping   # expect PONG
```

Rules:
- Use `rediss://` (TLS). A plain `redis://` URL is refused by the Phase 2 startup check.
- Development and tests use different Upstash databases. Tests never touch the development data.
- The URL contains a password. It is treated like any other secret.

## 8. Supabase project setup

| # | Task |
|---|---|
| 8.1 | Run `supabase init` at the repo root and `supabase link` to `nightroll-dev` |
| 8.2 | Enable the `vector` extension (Database, Extensions) |
| 8.3 | Create a private Storage bucket named `frames`. Public access off. |
| 8.4 | In Auth settings, turn off public sign-ups. Warden accounts are created by an admin only. |
| 8.5 | Turn on TOTP multi-factor authentication |
| 8.6 | Create one test warden account for development |

Tables and policies are Phase 1. This phase only prepares the project.

## 9. Play Integrity setup

| # | Task |
|---|---|
| 9.1 | Enable the Play Integrity API in the Google Cloud project |
| 9.2 | Give the backend's service account permission to call the API's token decode method |
| 9.3 | Note the Cloud project number for the app |

Whether full verdicts work for an app that is installed directly on a phone, without going through the Play Store, is checked in spike 11.2.

## 10. Demo network kit and network questions

**Kit**
- Two Wi-Fi routers, labelled Room 101 and Room 102, both plugged into the network the laptop is on.
- Two Android phones (Android 9 or newer), one per "student". One spare if possible.
- One laptop that runs the backend and stays on the upstream network.

Record each router's SSID, BSSIDs for both bands, and the address the laptop sees its traffic coming from. Put real values in `config/rooms.local.json` (ignored by git). Commit `config/rooms.example.json` with made-up values showing the shape:

```json
{
  "rooms": [
    {
      "number": "101",
      "floor": 1,
      "subnet": "192.168.101.0/24",
      "access_points": [
        {"bssid": "aa:bb:cc:00:01:01", "band": "2.4GHz"},
        {"bssid": "aa:bb:cc:00:01:05", "band": "5GHz"}
      ]
    }
  ]
}
```

**Questions for the campus network admin**
1. Does each room, or each floor, have its own subnet or VLAN?
2. Does the Wi-Fi controller have an API that reports which access point a device is on?
3. Does hostel Wi-Fi use per-student login, and can we read the RADIUS accounting log?

The answers decide what the network gate can prove in production. The demo does not depend on them.

## 11. Risk spikes

Each spike is a throwaway script or app in `scripts/spikes/`. The aim is a yes or no, not clean code. Write the result in `scripts/spikes/RESULTS.md`. Spikes 11.1, 11.2 and 11.4 use a development build, because Expo Go cannot run the native code they test.

| # | Spike | Question | Pass looks like |
|---|---|---|---|
| 11.1 | Keystore signing | Can a test phone create a non-exportable P-256 key and sign bytes that Python verifies? | Python verifies a signature made on the phone |
| 11.2 | Play Integrity | Does a directly installed build get a token the backend can decode, and what verdict fields come back? | Decoded verdict printed on the laptop |
| 11.3 | Face latency | How long does `buffalo_l` take per frame on the demo laptop's CPU? | Under about 300 ms per frame; record the number |
| 11.4 | Wi-Fi scan | Does a test phone return BSSIDs and signal strength for nearby networks? | List of networks with RSSI printed |
| 11.5 | Source address | Does the laptop see a different source address for each router? | Two different addresses logged |

If a spike fails, stop and decide the workaround before Phase 1 starts. Likely workarounds: run Play Integrity in a warn-only mode for the demo, or run anti-spoof on one frame instead of all.

## 12. Repo conventions

- Work on `base`. Follow the git workflow in `CLAUDE.md`: conventional commits, short messages, every commit pushed.
- One phase file is the unit of work. A phase is finished when its exit criteria are all true.
- Config that changes behaviour (weights, thresholds, window times) goes in env, never in code.

---

## Exit criteria

- [ ] A fresh clone has the full folder structure.
- [ ] `.gitignore` and all four `.env.example` files are committed.
- [ ] `git log -p` shows no secret, key or credential file in history.
- [ ] Every teammate has a filled `.env` for the service they own.
- [ ] `PONG` comes back from the Upstash URL on every teammate's machine.
- [ ] The Supabase project has the `vector` extension, the `frames` bucket, sign-ups off, and one test warden.
- [ ] The Google service account file is in place locally and ignored by git.
- [ ] All five spikes have a written result.
- [ ] The network admin has been asked the three questions.

## Risks

| Risk | What to do |
|---|---|
| A secret gets committed | Rotate that key at once, then remove the file. Rewriting history is not enough on its own. |
| Play Integrity does not give a usable verdict for a directly installed app | Demo with enforcement in warn-only mode and say so on stage |
| Face model too slow on the demo laptop | Score fewer frames, or borrow a faster machine for the demo |
| Routers hide phones behind one address | Use each router's upstream address as the room identity for the demo |

## Hand-off to Phase 1

Phase 1 needs the linked Supabase project, the `vector` extension, and the example room map.
