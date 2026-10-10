# Phase 6: Enrollment End to End

| | |
|---|---|
| **Type** | Implementation |
| **Depends on** | Phases 2, 4, 5 |
| **Unlocks** | Phases 7, 8, 9 |
| **Leads** | App, Backend |

## Goal

A student sitting at the warden's desk goes from "just installed the app" to "fully enrolled" in one sitting: consent recorded, face embedding stored, phone's public key registered, and the room's Wi-Fi fingerprint captured. Everything the nightly check compares against is created here.

## Outcome

- The warden issues a one-time enrollment code.
- The app completes consent, face capture and key registration with that code.
- The room's Wi-Fi fingerprint is captured and stored.
- A student can be re-enrolled on a new phone, which retires the old one.

## Scope

**In:** enrollment codes, consent, enrollment endpoint, face capture for enrollment, Wi-Fi scan module, room fingerprint capture and storage, re-enrollment, consent withdrawal.
**Out:** nightly capture and liveness (Phase 7), fingerprint matching (Phase 9), the dashboard screens that drive this (Phase 10 adds the UI; this phase provides the endpoints).

---

## Tasks

### 1. Enrollment codes (backend)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/v1/enrollment-codes` | Warden | Create a code for one student |
| GET | `/v1/students/{id}/enrollment` | Warden | Enrollment status: face, device, room fingerprint |

Rules:
- The code is 8 characters from an alphabet without look-alike characters.
- It is shown to the warden once. Only its SHA-256 is stored.
- It expires after 15 minutes and works once.
- Creating a new code for a student cancels any unused earlier one.
- Five wrong attempts against one student within 15 minutes locks code entry for that student until the warden issues a new code.

### 2. Consent (app)

| # | Task |
|---|---|
| 2.1 | The Consent screen states, in plain language: what is collected (a numeric face template, the phone's public key, nearby Wi-Fi names and signal strength), what is not kept (photos), how long nightly frames are kept (24 hours), and who can see attendance (the warden and hostel administration) |
| 2.2 | It states that the ground-floor scanner remains available to anyone who does not want to use the app |
| 2.3 | The student must tick a box and tap "I agree". There is no pre-ticked box. |
| 2.4 | The consent text has a version string, sent with the enrollment request and stored |

### 3. Enrollment endpoint (backend)

| Method | Path | Auth |
|---|---|---|
| POST | `/v1/enrollments` | Enrollment code |

Request, as multipart:

| Field | Content |
|---|---|
| `code` | The one-time code |
| `roll_number` | Student's roll number |
| `public_key` | Base64 DER public key from the Keystore |
| `key_security_level` | `strongbox`, `tee` or `software` |
| `consent_version` | Version of the text agreed to |
| `frames` | 3 to 5 JPEG frames |

Steps, in order:

| # | Step |
|---|---|
| 3.1 | Validate the code against the student. Count failed attempts. |
| 3.2 | Check the public key parses as a P-256 key |
| 3.3 | Send the frames to the face worker's `/enroll`. If it rejects them, return its reason so the app can ask for a retake. The code is not consumed on a retake. |
| 3.4 | In one transaction: mark the code used, set `consent_at` and consent version on the student, deactivate any earlier device, insert the new device, set `enrolled_at`, write the audit row |
| 3.5 | Return `{student_id, room_id, room_number}` |

If step 3.4 fails after the face worker stored an embedding, delete that embedding so no half-enrolled student is left behind.

### 4. Face capture for enrollment (app)

| # | Task |
|---|---|
| 4.1 | Add `react-native-vision-camera` and use the front camera. It needs the development build; Expo Go cannot run it. |
| 4.2 | Add ML Kit face detection as a frame processor |
| 4.3 | Show an oval guide. Give live hints: "Move closer", "Hold still", "More light", "Look straight" |
| 4.4 | Capture automatically when one face is centred, large enough and steady. Take 5 frames about 300 ms apart. |
| 4.5 | Resize frames to at most 720 pixels on the long side and compress as JPEG |
| 4.6 | Frames are held in memory only and discarded after upload |

This capture component is reused by Phase 7.

### 5. Enrollment screen flow (app)

1. Enter roll number and the code from the warden.
2. Generate the device key if none exists.
3. Capture the face frames.
4. Upload. Show progress.
5. On success, store student ID and room details.
6. Continue to the room scan step, or defer it with "Scan my room later".

A student who defers the room scan can open the app and see the window, but cannot mark attendance until the room has a fingerprint.

### 6. Wi-Fi scan module (app, native)

Written in Kotlin as an Expo Module in `app/modules/wifi-scanner` and exposed as `WifiScanner`.

| Method | Behaviour |
|---|---|
| `currentConnection()` | SSID, BSSID, signal strength and frequency of the connected network |
| `scan()` | Trigger one scan and return every visible network: BSSID, signal strength in dBm, frequency |
| `isLocationEnabled()` | Whether the phone's location setting is on, which Android requires for scan results |

Rules:
- Convert frequency to a band label: `2.4GHz` or `5GHz`.
- Android limits how often an app may scan. If the system refuses a new scan, return the most recent results with their age, and let the caller decide.
- Results older than 30 seconds are flagged as stale.
- Network names (SSIDs) are hashed before leaving the phone. BSSIDs are sent as they are, since the room map needs them.

### 7. Room fingerprint capture

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/v1/rooms/{room_id}/fingerprint` | Device signature, student must belong to the room | Submit room scans |
| POST | `/v1/rooms/{room_id}/fingerprint/reset` | Warden | Allow a fresh capture after a router change |
| GET | `/v1/rooms/{room_id}/fingerprint` | Warden | Version, age, number of access points seen |

App flow:
1. The screen asks the student to stand at three spots in turn: the bed, the desk, near the door.
2. At each spot the app takes one scan. Because of Android's scan limit, it waits at least 30 seconds between scans and shows a countdown.
3. The app sends all scans together.

Backend steps:

| # | Step |
|---|---|
| 7.1 | Reject if the room already has a fingerprint and no reset is pending |
| 7.2 | Require at least 3 scans, and require the room's own access point to appear in every one |
| 7.3 | Build the pattern: for each BSSID, the median signal strength, the band, and how many scans saw it |
| 7.4 | Label each BSSID: `own` if it is in the room map for this room, `hostel` if it belongs to another room in the map, `unknown` otherwise |
| 7.5 | Store as a new version in `room_fingerprints` and write an audit row |

Roommates share the room's fingerprint. Only the first enrolled student in a room is asked to scan.

### 8. Re-enrollment and withdrawal

| Case | Behaviour |
|---|---|
| New phone | Warden issues a new code. The old device is deactivated. The embedding is replaced. |
| App reinstalled | Same as a new phone, since the key is gone |
| Consent withdrawn | Warden action `POST /v1/students/{id}/withdraw`: deletes the embedding through the face worker, deactivates the device, writes an audit row. The student returns to the ground-floor scanner. |
| Room change | Warden updates the student's room. The device and face stay valid. |

---

## Exit criteria

- [ ] A warden token can create a code, and the response shows it once.
- [ ] A test phone completes enrollment with that code: the student row has consent and enrollment times, one active device, and an embedding.
- [ ] The same code cannot be used a second time.
- [ ] An expired code is refused.
- [ ] A blurry or faceless capture is refused with a reason the app shows, and the code still works for the retake.
- [ ] `WifiScanner.scan()` returns nearby networks with signal strengths on both test phones.
- [ ] A three-spot room scan stores a fingerprint with the room's own access point labelled `own`.
- [ ] A second fingerprint submission for the same room is refused until a warden resets it.
- [ ] Enrolling the same student on a second phone deactivates the first.
- [ ] Withdrawal removes the embedding and deactivates the device.

## Deferred to Phase 13

- Tests for code expiry, reuse and lockout.
- Tests for the fingerprint builder with recorded scans.
- A check that no enrollment photo is written to storage.

## Risks

| Risk | What to do |
|---|---|
| Enrollment done away from the warden's desk | The code is short-lived and handed over in person. The warden sees the student. |
| Scan limit makes the room scan slow | The countdown explains the wait. Three scans take about a minute and a half. |
| Location turned off on the phone | The app detects it and asks the student to turn it on, with the reason |
| Poor lighting at the desk | The capture hints handle it. The warden can retake. |

## Hand-off to Phase 7

Phase 7 needs the camera component, the Wi-Fi scan module and an enrolled test student with a room fingerprint.
