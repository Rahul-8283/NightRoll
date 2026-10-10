<div align="center">

# NightRoll

### Hostel attendance, marked from your bed.

Prove the **right person**, in the **right room**, on the **right device**, inside the **warden's window** — with no new hardware.

![Status](https://img.shields.io/badge/status-design%20stage-B86E00?style=for-the-badge)
![Platform](https://img.shields.io/badge/platform-Android%20first-3DDC84?style=for-the-badge&logo=android&logoColor=white)
![License](https://img.shields.io/badge/license-Apache%202.0-blue?style=for-the-badge)
![Hackathon](https://img.shields.io/badge/built%20for-Genesis%20Hackathon-141B2E?style=for-the-badge)

</div>

---

## Table of contents

- [The problem](#the-problem)
- [The solution](#the-solution)
- [Tech stack](#tech-stack)
- [System architecture](#system-architecture)
- [Verification pipeline](#verification-pipeline)
- [One night, end to end](#one-night-end-to-end)
- [Enrollment](#enrollment)
- [Trust score](#trust-score)
- [Geofencing with WiFi](#geofencing-with-wifi)
- [Threat model](#threat-model)
- [Data model](#data-model)
- [Deployment](#deployment)
- [Privacy](#privacy)
- [Demo plan](#demo-plan)
- [Roadmap](#roadmap)
- [Getting started](#getting-started)
- [Repository layout](#repository-layout)
- [Project status](#project-status)
- [License](#license)

---

## The problem

Every night at 10:00 PM, every hosteller walks down to the ground floor to scan their face at a single attendance point. Students on the first, second, third and higher floors all queue at the same scanner.

- One scanner serves the whole hostel, so there is a queue every night.
- Students leave their rooms and climb back up just to prove they are in the building.
- The check proves you were at the ground floor at 10:00 PM. It says nothing about whether you stayed.

## The solution

NightRoll moves the check to the student's phone and the hostel's existing per-room WiFi. At 10 PM the student opens NightRoll and completes a short face check in bed, and the room tile turns green on the warden's dashboard.

A selfie alone would be easy to fake, so every mark has to prove three things at once:

| Proof | How | What it stops |
|---|---|---|
| **Right person** | Face match plus a random liveness challenge | Someone else marking for you, photos, replayed video |
| **Right place** | Request arrives from your room's subnet, backed by a WiFi fingerprint of the room | Marking from outside the hostel, VPN tunnelling |
| **Right device, right now** | A hardware-bound key signs a one-time nonce issued for tonight's window | Marking from a friend's phone, replaying yesterday's request |

No single factor is trusted on its own. The existing ground-floor scanner stays as the fallback.

```mermaid
flowchart LR
    subgraph Before["Today"]
        direction LR
        A1["Floors 1 to N"] --> A2["Walk down"] --> A3["Queue at one scanner"] --> A4["Walk back up"]
    end
    subgraph After["With NightRoll"]
        direction LR
        B1["Opens app at 22:00"] --> B2["Face check in bed"] --> B3["Marked present"]
    end
    Before -.-> After
```

---

## Tech stack

**Mobile app**

![React Native](https://img.shields.io/badge/React%20Native-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white)
![Android](https://img.shields.io/badge/Android%20Keystore-3DDC84?style=for-the-badge&logo=android&logoColor=white)
![ML Kit](https://img.shields.io/badge/ML%20Kit-4285F4?style=for-the-badge&logo=google&logoColor=white)
![TensorFlow Lite](https://img.shields.io/badge/TensorFlow%20Lite-FF6F00?style=for-the-badge&logo=tensorflow&logoColor=white)
![Play Integrity](https://img.shields.io/badge/Play%20Integrity-414141?style=for-the-badge&logo=googleplay&logoColor=white)

**Backend**

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Upstash Redis](https://img.shields.io/badge/Upstash%20Redis-00E9A3?style=for-the-badge&logo=upstash&logoColor=white)
![Celery](https://img.shields.io/badge/Celery-37814A?style=for-the-badge&logo=celery&logoColor=white)
![WebSocket](https://img.shields.io/badge/WebSocket-010101?style=for-the-badge)

**Face and liveness**

![InsightFace](https://img.shields.io/badge/InsightFace%20ArcFace-1F6FEB?style=for-the-badge)
![ONNX](https://img.shields.io/badge/ONNX%20Runtime-005CED?style=for-the-badge&logo=onnx&logoColor=white)
![Anti-spoof](https://img.shields.io/badge/Silent--Face%20Anti--Spoofing-6E40C9?style=for-the-badge)

**Data**

![Supabase](https://img.shields.io/badge/Supabase-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![pgvector](https://img.shields.io/badge/pgvector-336791?style=for-the-badge&logo=postgresql&logoColor=white)
![Supabase Auth](https://img.shields.io/badge/Supabase%20Auth-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)
![Supabase Storage](https://img.shields.io/badge/Supabase%20Storage-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)

**Dashboard and delivery**

![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)

| Layer | Choice | Why |
|---|---|---|
| App | React Native, VisionCamera, ML Kit | One codebase, fast camera pipeline, on-device face detection |
| On-device ML | TFLite MobileFaceNet | Quick pre-check so a bad capture fails before upload |
| Device trust | Android Keystore / StrongBox, Play Integrity | Key never leaves the chip; blocks root, emulators, virtual cameras |
| API | FastAPI | Async, typed, fast to build |
| State | Upstash Redis (hosted, TLS) | Nonces and window state with native TTL, no local server to run |
| Face | InsightFace `buffalo_l` on ONNX Runtime | Strong open ArcFace embeddings, runs on CPU |
| Database | Supabase (PostgreSQL with pgvector) | Relational data and 512-dimension embeddings in one managed database |
| Auth | Supabase Auth | Warden and admin login with MFA; student devices are bound by Keystore keys, not passwords |
| Frame storage | Supabase Storage (private bucket) | Encrypted, short-lived frames with a 24-hour deletion job |
| Network verify | Subnet check, then controller API or RADIUS accounting | Starts simple, upgrades without app changes |
| Dashboard | React over WebSocket | Room tiles update live |
| Window status | Pulled from the API when the app opens | No push service; students open the app at window time |

---

## System architecture

Four zones: the phone gathers evidence, the hostel network vouches for location, the backend decides, and the outputs inform the student and the warden.

```mermaid
flowchart LR
    subgraph Phone["1. Student phone"]
        direction TB
        P1["Guard checks<br/>VPN, proxy, mock location"]
        P2["Liveness challenge"]
        P3["Face frames"]
        P4["WiFi scan"]
        P5["Play Integrity token"]
        P6["Keystore signer"]
        P7["Signed payload"]
        P1 --> P2 --> P3 --> P4 --> P5 --> P6 --> P7
    end

    subgraph Net["2. Hostel network"]
        direction TB
        N1["Room access point"]
        N2["Room VLAN / subnet"]
        N3["WiFi controller / RADIUS"]
        N1 --> N2
        N1 -.-> N3
    end

    subgraph Back["3. NightRoll backend on campus LAN"]
        direction TB
        B0["Window service"]
        B1["API gateway"]
        B2["Hard gates"]
        B3["Scored checks"]
        B4["Fusion engine"]
        B5[("Supabase PostgreSQL + pgvector")]
        B6[("Upstash Redis")]
        B7["Network adapter"]
        B0 --> B1 --> B2 --> B3 --> B4
        B0 <--> B6
        B4 --> B5
        B7 --> B3
    end

    subgraph Out["4. Outputs"]
        direction TB
        O1["Window status on Home"]
        O2["Student result"]
        O3["Warden dashboard"]
    end

    P7 -- "HTTPS" --> N1
    N2 -- "source IP = room" --> B1
    N3 -.-> B7
    B0 --> O1
    O1 -- "shown when app opens" --> P1
    B4 --> O2
    B4 --> O3
```

### Backend components

```mermaid
flowchart TB
    GW["API gateway"] --> ORC["Verification orchestrator"]

    ORC --> CV["Crypto verifier<br/>signature, nonce freshness"]
    ORC --> IV["Integrity verifier<br/>Play Integrity decode"]
    ORC --> NV["Network verifier<br/>subnet, controller, RADIUS"]
    ORC --> FV["Face verifier<br/>ArcFace, anti-spoof"]
    ORC --> WV["Fingerprint verifier<br/>room WiFi pattern"]

    CV --> FE["Fusion engine"]
    IV --> FE
    NV --> FE
    FV --> FE
    WV --> FE

    WS["Window service"] --> RD[("Upstash Redis<br/>nonces, window state")]
    CV --> RD
    FV --> PG[("Supabase PostgreSQL + pgvector<br/>students, rooms, embeddings, logs")]
    WV --> PG
    FE --> PG
    FE --> RT["WebSocket hub"] --> DB["Warden dashboard"]
```

---

## Verification pipeline

Hard gates run first. Any single failure rejects the mark before a face is ever compared. Only marks that pass every gate are scored.

```mermaid
flowchart TD
    S(["Signed payload arrives"]) --> G1{"Inside window?<br/>server clock"}
    G1 -- no --> R["REJECTED"]
    G1 -- yes --> G2{"Signature valid<br/>and nonce unused?"}
    G2 -- no --> R
    G2 -- yes --> G3{"Play Integrity pass?"}
    G3 -- no --> R
    G3 -- yes --> G4{"No VPN, proxy<br/>or mock location?"}
    G4 -- no --> R
    G4 -- yes --> G5{"Source IP in<br/>room subnet?"}
    G5 -- no --> R
    G5 -- yes --> SC["Score: face, liveness,<br/>room fingerprint, RSSI"]
    SC --> F{"Trust score"}
    F -- "0.80 or above" --> P["PRESENT"]
    F -- "0.60 to 0.80" --> V["NEEDS REVIEW"]
    F -- "below 0.60" --> R
    V --> W["Warden review queue"]
    R --> FB["Fallback: ground-floor scanner"]
```

| Gate | Defeats |
|---|---|
| Server-clock window | Changing the phone's time |
| Signature and fresh nonce | A friend's phone, replayed requests |
| Play Integrity | Rooted devices, emulators, virtual cameras |
| No VPN, proxy or mock location | Tunnelling in from outside |
| Room subnet source IP | Any request from off the hostel network |

---

## One night, end to end

```mermaid
sequenceDiagram
    autonumber
    actor W as Warden
    participant D as Dashboard
    participant S as Backend
    participant R as Upstash Redis
    participant A as NightRoll app
    actor U as Student
    participant AP as Room AP

    W->>D: Set window, default 22:00 to 22:30
    D->>S: Save window and off days
    Note over S: 22:00 window opens
    S->>R: Store one nonce per student with TTL
    U->>A: Opens NightRoll in bed
    A->>A: Guard checks for VPN, proxy, mock location
    A->>U: Random liveness challenge
    U->>A: Blink, turn head
    A->>A: Capture frames, scan WiFi, fetch integrity token
    A->>A: Sign payload with Keystore key
    A->>AP: POST verify over HTTPS
    AP->>S: Forward, source IP is the room subnet
    S->>R: Check and consume nonce
    S->>S: Hard gates, then scoring, then fusion
    S-->>A: Verdict with reason
    S-->>D: Room tile updates live
    Note over S: 22:30 window closes
    S->>R: Nonces expire
    S-->>D: Absentee list and review queue
    W->>D: Review flagged marks, override if needed
```

### Attendance states

```mermaid
stateDiagram-v2
    [*] --> Pending: window opens
    Pending --> Present: gates pass and score is high
    Pending --> NeedsReview: gates pass and score is borderline
    Pending --> Rejected: a gate fails or score is low
    Pending --> Absent: window closes with no mark
    NeedsReview --> Present: warden approves
    NeedsReview --> Absent: warden declines
    Rejected --> Pending: student retries inside the window
    Rejected --> Present: ground-floor scanner or warden override
    Absent --> Present: warden override
    Present --> [*]
    Absent --> [*]
```

---

## Enrollment

Enrollment happens once, in person, at the warden's office. That is what makes the later remote checks trustworthy.

```mermaid
flowchart TD
    A(["Student at warden office"]) --> B["Consent recorded"]
    B --> C["Controlled face capture"]
    C --> D["ArcFace embedding, 512 dimensions"]
    D --> E[("Store vector in Supabase pgvector<br/>photo discarded")]
    B --> F["App generates keypair in Keystore"]
    F --> G[("Register public key to student")]
    B --> H["3 to 5 WiFi scans in the room<br/>bed, desk, door"]
    H --> I[("Room fingerprint")]
    J["Network admin"] --> K[("Room to BSSID to subnet map")]
    E --> L(["Enrolled"])
    G --> L
    I --> L
    K --> L
```

- **Face:** only the embedding is stored. The enrollment photo is discarded.
- **Device:** the private key is generated inside the phone's secure hardware and never leaves it. A new phone means re-enrolling the device.
- **Room:** one student scans the room; roommates share the same room fingerprint.

---

## Trust score

Marks that pass every gate are scored from five signals.

```mermaid
pie showData
    title Trust score weights (provisional)
    "Face match" : 30
    "Room WiFi fingerprint" : 30
    "Liveness and anti-spoof" : 20
    "Own-AP signal strength" : 15
    "AP-side signal agreement" : 5
```

| Signal | Weight | What it measures |
|---|---|---|
| Face match | 0.30 | Cosine similarity between tonight's embedding and the enrolled one |
| Room WiFi fingerprint | 0.30 | How closely tonight's scan matches the room's saved pattern |
| Liveness and anti-spoof | 0.20 | Challenge completed, and the face is not a photo or a screen |
| Own-AP signal strength | 0.15 | The room's own router is seen at room-level strength |
| AP-side signal agreement | 0.05 | The router's view of the phone agrees with the phone's report |

| Score | Verdict | What happens |
|---|---|---|
| 0.80 or above | **PRESENT** | Recorded; room tile turns green |
| 0.60 to 0.80 | **NEEDS REVIEW** | Goes to the warden's review queue |
| Below 0.60 | **REJECTED** | Student sees the reason and can retry or use the ground-floor scanner |

> [!NOTE]
> These weights and cutoffs are starting values. They will be tuned against real measurements from the hostel (see the walk test below) before anyone relies on them.

---

## Geofencing with WiFi

GPS cannot tell one room from the next indoors, and it is easy to fake. NightRoll uses the WiFi itself as the fence.

Every spot in the hostel sees the surrounding routers differently. Inside room 203, the room's own router is very strong, the neighbours are medium, the corridor is weak. Outside the compound wall, most hostel routers vanish and unfamiliar networks appear. That pattern is the room's fingerprint.

```mermaid
flowchart TD
    A(["Tonight's WiFi scan"]) --> B{"Own room router<br/>present and strong?"}
    B -- no --> X["Low fingerprint score"]
    B -- yes --> C{"Expected neighbour<br/>routers present?"}
    C -- "few" --> X
    C -- "most" --> D{"Relative strengths<br/>match the usual order?"}
    D -- no --> Y["Medium fingerprint score"]
    D -- yes --> E{"Unknown outside<br/>networks visible?"}
    E -- "several" --> Y
    E -- "none or few" --> Z["High fingerprint score"]
    X --> F(["Feeds trust score"])
    Y --> F
    Z --> F
```

### Calibrating with a walk test

Limits are measured, not guessed.

```mermaid
flowchart LR
    A["Scan inside<br/>several rooms"] --> C["Compare the<br/>two groups"]
    B["Scan outside:<br/>compound wall, corridor,<br/>next room, floor below"] --> C
    C --> D["Set limits<br/>between them"]
    D --> E["Stricter limits for<br/>rooms near the wall"]
```

### Keeping fingerprints fresh

- **Slow drift:** confident "present" marks are blended into the saved fingerprint. Borderline marks never are, so a cheater cannot teach the system a wrong pattern.
- **Router replaced:** the warden triggers a re-scan for that room.
- **Stale fingerprint:** repeated reviews from one room flag it on the dashboard.

### Supporting layers

| Layer | Role |
|---|---|
| Router minimum-signal setting | The router drops weak clients, so distant phones cannot stay connected |
| Router-side signal check | A large gap between the router's reading and the phone's report suggests a faked scan |
| 5 GHz signal | Blocked by walls more than 2.4 GHz; used as evidence if the walk test shows it helps, not as a rule |
| GPS | A warning only, and only when accurate and clearly outside the hostel |

---

## Threat model

```mermaid
flowchart LR
    T1["Friend marks for me<br/>on their phone"] --> D1["Device key signature"]
    T2["Friend marks for me<br/>on my phone"] --> D2["Face match"]
    T3["Photo or video<br/>of my face"] --> D3["Liveness and anti-spoof"]
    T4["Replay last<br/>night's request"] --> D4["One-time nonce"]
    T5["Mark from outside<br/>over VPN"] --> D5["VPN guard and<br/>room subnet gate"]
    T6["Catch weak WiFi from<br/>outside the wall"] --> D6["Room fingerprint<br/>and signal strength"]
    T7["Rooted phone, emulator<br/>or fake camera"] --> D7["Play Integrity"]
    T8["Change the<br/>phone clock"] --> D8["Server-clock window"]
```

| Limitation | Handling |
|---|---|
| Student marks present, then leaves | Out of scope for the first release; random spot-checks are on the roadmap |
| Phone dead, no WiFi, router down | Ground-floor scanner stays as the fallback |
| iPhones cannot do full WiFi scans | Android first; iPhone users keep the ground-floor scanner |
| Hostel network does not expose subnets or a controller API | Needs the network admin; the design degrades to fingerprint plus review |

---

## Data model

```mermaid
erDiagram
    STUDENT ||--o| DEVICE : registers
    STUDENT ||--|| FACE_EMBEDDING : has
    STUDENT }o--|| ROOM : lives_in
    ROOM ||--o{ ACCESS_POINT : served_by
    ROOM ||--o| ROOM_FINGERPRINT : has
    ATTENDANCE_WINDOW ||--o{ NONCE : issues
    STUDENT ||--o{ NONCE : receives
    STUDENT ||--o{ ATTENDANCE_MARK : makes
    ATTENDANCE_WINDOW ||--o{ ATTENDANCE_MARK : contains
    ATTENDANCE_MARK ||--o| REVIEW : may_need

    STUDENT {
        uuid id PK
        string roll_number
        string name
        uuid room_id FK
        timestamp consent_at
    }
    DEVICE {
        uuid id PK
        uuid student_id FK
        text public_key
        timestamp enrolled_at
    }
    FACE_EMBEDDING {
        uuid student_id PK
        vector embedding
    }
    ROOM {
        uuid id PK
        string number
        int floor
        string subnet
    }
    ACCESS_POINT {
        string bssid PK
        uuid room_id FK
        string band
    }
    ROOM_FINGERPRINT {
        uuid room_id PK
        json pattern
        timestamp updated_at
    }
    ATTENDANCE_WINDOW {
        uuid id PK
        date night
        timestamp opens_at
        timestamp closes_at
    }
    NONCE {
        string value PK
        uuid student_id FK
        uuid window_id FK
        boolean used
    }
    ATTENDANCE_MARK {
        uuid id PK
        uuid student_id FK
        uuid window_id FK
        float trust_score
        string verdict
        string reason
        timestamp marked_at
    }
    REVIEW {
        uuid mark_id PK
        string decision
        string reviewed_by
        timestamp reviewed_at
    }
```

Nonces live in Upstash Redis with a TTL that ends when the window closes. They are shown here for the relationships only.

---

## Deployment

The backend sits on the campus LAN so the source IP of every request is the student's real room address.

```mermaid
flowchart TB
    subgraph Rooms["Hostel rooms"]
        PH["Student phones"]
        AP["Room access points"]
        PH --> AP
    end

    subgraph LAN["Campus LAN"]
        CTRL["WiFi controller / RADIUS"]
        subgraph Host["NightRoll host"]
            API["FastAPI service"]
            WK["Face worker"]
            RDS[("Upstash Redis")]
            PGS[("Supabase PostgreSQL + pgvector")]
            WEB["Dashboard"]
            API --> RDS
            API --> PGS
            API --> WK
            WK --> PGS
        end
        WD["Warden desk"]
    end

    subgraph Cloud["Google services"]
        PIS["Play Integrity API"]
    end

    AP --> API
    CTRL -.-> API
    WD --> WEB
    WEB <--> API
    API --> PIS
```

---

## Privacy

Face data is sensitive, so the rules are fixed from the start.

- **Consent first.** Enrollment requires explicit, recorded consent.
- **Embeddings, not photos.** Only the numeric face embedding is stored.
- **Short-lived frames.** Frames captured for a nightly check are deleted within 24 hours.
- **No biometric logging.** Embeddings and raw frames never appear in logs.
- **Reasons shown.** A student always sees why a mark was rejected or sent to review.
- **A human decides the edge cases.** The warden can override any automatic verdict.

---

## Demo plan

Two ordinary routers stand in for Room 101 and Room 102, each on its own subnet.

| # | Action | Expected result |
|---|---|---|
| 1 | Mark from the Room 101 router | **PRESENT**; the tile turns green |
| 2 | Switch to the Room 102 router | **REJECTED** at the room subnet gate |
| 3 | Hold up a photo or a video of the face | **REJECTED** by liveness |
| 4 | Mark from a teammate's phone | **REJECTED**; signature does not match |
| 5 | Walk out of the building while still on WiFi | **REJECTED**; WiFi pattern does not match the room |

Production plugs into the hostel's existing WiFi controller or RADIUS. No new hardware is required.

---

## Roadmap

```mermaid
flowchart LR
    subgraph M1["MVP: hackathon"]
        direction TB
        a1["Signed nonce per student"]
        a2["Room subnet gate"]
        a3["Face match and liveness challenge"]
        a4["Dashboard with room tiles"]
    end
    subgraph M2["Next"]
        direction TB
        b1["WiFi fingerprint and walk test"]
        b2["Passive anti-spoof model"]
        b3["Controller or RADIUS adapter"]
    end
    subgraph M3["Later"]
        direction TB
        c1["Random spot-checks"]
        c2["Anomaly detection"]
        c3["ERP export, iOS support"]
    end
    M1 --> M2 --> M3
```

## Getting started

### Prerequisites

Install these once. The commands are for macOS with Homebrew; Windows and Linux users can use the official installers.

| Tool | Version | Needed for | Install |
|---|---|---|---|
| Git | any recent | Source control | `brew install git` |
| Python | 3.12 | Backend, face worker | `brew install python@3.12` |
| Node.js | 20 LTS | Dashboard, app tooling | `brew install node@20` |
| JDK | 17 | Android build | `brew install openjdk@17` |
| Android Studio | current stable | Android SDK, emulator | developer.android.com/studio |
| Docker Desktop | current stable | Later services (Phase 12); not needed for Redis | docker.com, then start it |
| Supabase CLI | current stable | Migrations, linking the project | `brew install supabase/tap/supabase` |

### First-time setup

1. Clone the repo and switch to the branch you are working on:

   ```bash
   git clone https://github.com/Rahul-8283/NightRoll.git
   cd NightRoll
   git checkout base
   ```

2. Create your local env files from the examples. Ask the team for the real values; never commit them.

   ```bash
   cp backend/.env.example backend/.env
   cp face/.env.example face/.env
   cp dashboard/.env.example dashboard/.env
   cp app/.env.example app/.env
   cp config/rooms.example.json config/rooms.local.json
   ```

3. Put the Google service account file at `backend/secrets/google-service-account.json` (from the team password manager).

4. Paste your Upstash `rediss://` URL into `backend/.env` as `REDIS_URL`, then check it (see below).

5. Link Supabase: follow [supabase/README.md](supabase/README.md).

### Running each service

| Service | Port | Start with | Available from |
|---|---|---|---|
| Upstash Redis | hosted, TLS | set `REDIS_URL` in `backend/.env` | Phase 0 (now) |
| Supabase | hosted | `supabase link --project-ref <ref>` | Phase 0 (now) |
| Backend API | 8000 | `cd backend && uvicorn app.main:app --reload --port 8000` | Phase 2 |
| Window scheduler | none | `cd backend && python -m app.scheduler` | Phase 3 |
| Face worker | 8100 | `cd face && uvicorn worker.main:app --port 8100` | Phase 5 |
| Warden dashboard | 5173 | `cd dashboard && npm run dev` | Shell now; screens in Phase 10 |
| Student app | Metro 8081 | `cd app && npx react-native run-android` | Phase 4 |

Start order once everything exists: face worker, backend API, scheduler, dashboard, then the phone app. Upstash Redis is always on.

**Redis (works now, hosted on Upstash)**

Redis runs in the cloud, so there is no server to start. Check the connection with the Redis client in a container, so nothing needs installing on the laptop:

```bash
docker run --rm redis:7 redis-cli --tls -u "<your REDIS_URL>" ping   # expect PONG
```

Use the same `rediss://` URL as in `backend/.env`. Do not commit it.

**Backend API (from Phase 2)**

```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
curl http://localhost:8000/v1/health
```

**Window scheduler (from Phase 3)** runs in its own terminal, with the same virtual environment: `python -m app.scheduler`.

**Face worker (from Phase 5)**

```bash
cd face
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python scripts/download_models.py
uvicorn worker.main:app --port 8100
```

**Warden dashboard (shell available now)**

```bash
cd dashboard
cp .env.example .env     # fill in the Supabase URL and anon key
npm install
npm run dev              # open http://localhost:5173
```

The pages are placeholders until Phase 10. The dashboard shows which variables are missing if `.env` is incomplete.

**Student app (from Phase 4)**

```bash
cd app
npm install
npx react-native start                # terminal 1
npx react-native run-android          # terminal 2, with the phone connected or an emulator running
```

### Stopping everything

Press `Ctrl+C` in each terminal. Upstash Redis keeps running in the cloud, so there is nothing to stop for it.

## Repository layout

```text
NightRoll/
├── app/          React Native student app (Android)
├── backend/      FastAPI service: windows, nonces, gates, scoring, review
├── face/         Face worker: embeddings and anti-spoof (internal)
├── dashboard/    React warden dashboard
├── supabase/     Supabase CLI project and SQL migrations
├── infra/        Docker Compose and deployment files
├── config/       Room map example (real map stays local, git-ignored)
├── scripts/      One-off tools and Phase 0 risk spikes
├── docs/         PRD, TRD, architecture
└── phase/        Build plan, one file per phase
```

## Project status

The design is settled (see `docs/` and `phase/`). Phase 0, base setup, is in progress: folders, env examples, the Upstash Redis setup and the setup steps are in place. No feature code exists yet.

## License

Released under the [Apache License 2.0](LICENSE).

## Team

**Team Zero_Latency**

<table align="center">
  <tr>
    <td align="center" width="25%">
      <a href="https://github.com/Rahul-8283"><img src="https://github.com/Rahul-8283.png?size=200" width="100" alt="Rahul L S"></a><br>
      <b>Rahul L S</b><br>
      <a href="https://github.com/Rahul-8283">@Rahul-8283</a>
    </td>
    <td align="center" width="25%">
      <a href="https://github.com/djivites"><img src="https://github.com/djivites.png?size=200" width="100" alt="Jivites"></a><br>
      <b>Jivites</b><br>
      <a href="https://github.com/djivites">@djivites</a>
    </td>
    <td align="center" width="25%">
      <a href="https://github.com/sukanthan06"><img src="https://github.com/sukanthan06.png?size=200" width="100" alt="Sukanthan"></a><br>
      <b>Sukanthan</b><br>
      <a href="https://github.com/sukanthan06">@sukanthan06</a>
    </td>
    <td align="center" width="25%">
      <a href="https://github.com/kesavvvvvv"><img src="https://github.com/kesavvvvvv.png?size=200" width="100" alt="Kesav Satya Sai Nimmagadda"></a><br>
      <b>Kesav Satya Sai Nimmagadda</b><br>
      <a href="https://github.com/kesavvvvvv">@kesavvvvvv</a>
    </td>
  </tr>
</table>
