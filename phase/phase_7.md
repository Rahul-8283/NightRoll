# Phase 7: Nightly Capture and Signed Payload

| | |
|---|---|
| **Type** | Implementation |
| **Depends on** | Phases 3, 4, 6 |
| **Unlocks** | Phase 8 |
| **Lead** | App |

## Goal

The phone side of a nightly mark. When the student taps "Mark attendance", the app checks the phone's environment, runs a random liveness challenge, captures frames, scans Wi-Fi, obtains a Play Integrity token, signs everything, and sends one request. This phase ends when the app produces a complete, correctly signed submission.

## Outcome

- The marking screen runs the full capture sequence in under 30 seconds.
- The app refuses to start if a VPN, proxy or mock location is active.
- The submission envelope is defined and documented, and the app builds it correctly.
- The result and fallback screens show real responses.

## Scope

**In:** guard checks, liveness challenge, frame capture, Wi-Fi scan, Play Integrity token, payload building, signing, upload, result display.
**Out:** the server's checks on the submission (Phases 8 and 9).

---

## Tasks

### 1. Guard checks (native)

Written in Kotlin and exposed as `Environment`.

| Check | How | Blocks marking |
|---|---|---|
| VPN active | The active network reports a VPN transport | Yes |
| Proxy set | A system HTTP proxy is configured | Yes |
| Mock location | A test location provider is feeding the phone's location | Yes |
| Developer options on | System setting | No, reported only |
| Connected to Wi-Fi | Active network is Wi-Fi, not mobile data | Yes |
| Location setting on | Needed for the scan | Yes, with a prompt to turn it on |

| # | Task |
|---|---|
| 1.1 | Run the checks before the camera opens |
| 1.2 | A blocking check shows what is wrong and how to fix it, for example "Turn off your VPN and try again" |
| 1.3 | Run the checks again just before upload, in case something was switched on mid-flow |
| 1.4 | Include the results in the payload |

These are the phone's own claims. The server does not rely on them alone; Play Integrity and the network gate are the independent checks.

### 2. Liveness challenge

| # | Task |
|---|---|
| 2.1 | Fetch the nonce from `GET /v1/attendance/nonce`. The response also carries a `challenge`: an ordered list of two actions chosen by the server from `blink`, `turn_left`, `turn_right`, `smile`. |
| 2.2 | Show one action at a time with a simple picture and text |
| 2.3 | Detect each action on the phone with ML Kit: eye-open probability for a blink, head turn angle for left and right, smile probability for a smile |
| 2.4 | Each action must complete within 5 seconds. Three failed tries ends the attempt with a retry option. |
| 2.5 | Record, for each action, when it started and when it was detected |

The server chooses the actions so a pre-recorded video cannot know them in advance. Backend change: the nonce endpoint from Phase 3 gains the `challenge` field, stored beside the nonce in Redis.

### 3. Frame capture

Reuses the camera component from Phase 6.

| # | Task |
|---|---|
| 3.1 | Capture one frame at the moment each challenge action is detected, plus two neutral, front-facing frames: 4 frames in total |
| 3.2 | Run the on-device quality checks first: one face, large enough, sharp enough. Retake a failed frame once. |
| 3.3 | Resize and compress as in enrollment |
| 3.4 | Compute the SHA-256 of each frame's final bytes |
| 3.5 | Guide the student: "Hold the phone upright at arm's length" and "Turn on a light" if the frame is too dark |

### 4. Wi-Fi scan

| # | Task |
|---|---|
| 4.1 | Read the current connection: BSSID, signal strength, band |
| 4.2 | Trigger one scan while the student does the liveness challenge, so it adds no waiting time |
| 4.3 | If the system refuses a fresh scan, use the last results and include their age |
| 4.4 | Include every visible network's BSSID, signal strength and band |

### 5. Play Integrity token (native)

Written in Kotlin and exposed as `Integrity`.

| # | Task |
|---|---|
| 5.1 | Add the Play Integrity library and prepare the token provider at app start, using `GOOGLE_CLOUD_PROJECT_NUMBER` |
| 5.2 | `requestToken(requestHash)` returns a token bound to the given hash |
| 5.3 | On failure, return the error code. The app still submits, and the server decides. |

### 6. Submission envelope

To avoid any mismatch between what the phone signs and what the server checks, the phone signs an exact string of bytes and sends that same string. The server verifies the signature over the bytes it received, and only then reads them as JSON.

**Step 1.** Build the core payload and serialise it once to a UTF-8 string, `payload`:

```json
{
  "v": 1,
  "student_id": "uuid",
  "window_id": "uuid",
  "nonce": "base64url",
  "client_time": "2026-10-10T22:01:14+05:30",
  "challenge": [
    {"action": "blink", "started_ms": 0, "detected_ms": 1180},
    {"action": "turn_right", "started_ms": 1400, "detected_ms": 2950}
  ],
  "frames": [
    {"index": 0, "sha256": "hex", "tag": "blink"},
    {"index": 1, "sha256": "hex", "tag": "turn_right"},
    {"index": 2, "sha256": "hex", "tag": "neutral"},
    {"index": 3, "sha256": "hex", "tag": "neutral"}
  ],
  "wifi": {
    "connected": {"bssid": "aa:bb:cc:00:01:05", "rssi": -52, "band": "5GHz"},
    "scan_age_ms": 800,
    "scan": [
      {"bssid": "aa:bb:cc:00:01:05", "rssi": -52, "band": "5GHz"},
      {"bssid": "aa:bb:cc:00:02:05", "rssi": -71, "band": "5GHz"}
    ]
  },
  "environment": {
    "vpn": false, "proxy": false, "mock_location": false,
    "developer_options": false, "on_wifi": true
  },
  "app_version": "0.1.0"
}
```

**Step 2.** Compute `payload_hash`, the SHA-256 of the `payload` bytes.

**Step 3.** Request a Play Integrity token with `requestHash` set to `payload_hash`. This ties the token to this exact payload.

**Step 4.** Sign the `payload` bytes with the device key.

**Step 5.** Send `POST /v1/attendance/verify` as multipart:

| Part | Content |
|---|---|
| `payload` | The exact string from step 1 |
| `signature` | Base64 signature from step 4 |
| `integrity_token` | Token from step 3, or empty with `integrity_error` set |
| `frame_0` to `frame_3` | JPEG bytes |

This replaces the "canonical JSON" wording in `docs/TRD.md` section 6.2. Update the TRD in this phase.

| # | Task |
|---|---|
| 6.1 | Build the envelope in `src/marking/envelope.ts`, with no step skippable |
| 6.2 | Never serialise the payload twice. The signed string and the sent string are the same variable. |
| 6.3 | Add the envelope format to `docs/TRD.md` |

### 7. Upload and retry

| # | Task |
|---|---|
| 7.1 | 15-second timeout for the upload |
| 7.2 | On a network failure, retry once with the identical envelope. The server treats a repeat as the same submission. |
| 7.3 | After a second failure, show the Fallback screen |
| 7.4 | Show a progress state for each stage: "Checking phone", "Face check", "Sending" |

### 8. Result and fallback screens

| Verdict | Screen |
|---|---|
| `PRESENT` | Green confirmation with the time. The Home screen shows "Marked present". |
| `NEEDS_REVIEW` | "Sent to your warden for review" with the reason in plain words |
| `REJECTED`, retry allowed | The reason and a "Try again" button |
| `REJECTED`, no retry | The reason and directions to the ground-floor scanner |
| Service unavailable | "Could not reach the hostel server" and directions to the scanner |

Each reason code from the server maps to one plain sentence, kept in one file. For example, `WIFI_PATTERN_MISMATCH` becomes "Your phone does not appear to be in your room."

### 9. Marking flow timing

Target: under 30 seconds from tap to result.

| Stage | Budget |
|---|---|
| Guard checks and nonce fetch | 2 s |
| Liveness challenge and frames | 10 s |
| Integrity token and signing | 3 s |
| Upload and verdict | 5 s |

---

## Exit criteria

- [ ] With a VPN on, the app stops before the camera and says why.
- [ ] On mobile data, the app asks the student to join the room Wi-Fi.
- [ ] The challenge shows the two actions the server chose, and completes only when they are actually performed.
- [ ] Holding a still photo in front of the camera does not complete a blink or head-turn action.
- [ ] Four frames are captured and each one's hash matches the hash in the payload.
- [ ] The payload contains the connected network and the scan list.
- [ ] A Play Integrity token is obtained on a real phone, with the payload hash as its request hash.
- [ ] A Python script verifies the envelope's signature using the enrolled public key and the received payload bytes.
- [ ] A dropped connection leads to one retry, then the Fallback screen.
- [ ] The whole flow completes in under 30 seconds on a test phone.

## Deferred to Phase 13

- Tests for the envelope builder against fixed inputs.
- Liveness detection across lighting conditions and with glasses.
- Timing on a low-end phone.

## Risks

| Risk | What to do |
|---|---|
| Liveness actions hard to detect lying down in dim light | Lighting prompt, generous time limit, and a different action on retry |
| Play Integrity quota or errors | Submit with the error code; the server's enforcement setting decides |
| Scan refused by Android | Send the last results with their age; the server lowers the score for stale scans |
| Upload too large on weak Wi-Fi | Frames are resized and compressed to keep the upload small |

## Hand-off to Phase 8

Phase 8 needs the envelope format and a test phone that produces real submissions.
