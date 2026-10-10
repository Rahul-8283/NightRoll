# Phase 4: Mobile App Foundation and Device Key

| | |
|---|---|
| **Type** | Implementation |
| **Depends on** | Phases 0, 3 |
| **Unlocks** | Phases 6, 7 |
| **Lead** | App |

## Goal

A React Native Android app that installs on the test phones, holds a hardware-backed signing key, shows tonight's window status when a student opens it, and can make a signed request to the backend. This is the shell that enrollment and marking are built into.

## Outcome

- The app builds and runs on both test phones.
- A native module creates a non-exportable key in the Android Keystore and signs bytes with it.
- The Home screen shows the window state fetched from the server, including the next opening time when no window is open.
- An API client attaches a device signature to requests.
- Screens exist for every step, with placeholders where later phases fill in.

## Scope

**In:** project setup, navigation, native Keystore module, API client, permissions, local storage, Home screen status, screen shells.
**Out:** camera, liveness, Wi-Fi scan, Play Integrity (Phase 7), enrollment logic (Phase 6). No push notifications of any kind.

---

## Tasks

### 1. Project setup

| # | Task |
|---|---|
| 1.1 | Create the app in `app/` with the React Native CLI and TypeScript |
| 1.2 | Set the Android package to `com.zerolatency.nightroll` |
| 1.3 | Set `minSdkVersion` to 28 (Android 9) |
| 1.4 | Add `react-native-config` to read `app/.env` |
| 1.5 | Add no Firebase or push plugin. The app talks only to the NightRoll API. |
| 1.6 | Add ESLint and Prettier |
| 1.7 | Write `app/README.md` with install, run and release-build steps |

```text
app/
├── android/
│   └── app/src/main/java/com/zerolatency/nightroll/
│       └── keystore/        Native signing module (Kotlin)
├── src/
│   ├── api/                 Client, signing, error mapping
│   ├── native/              TypeScript wrappers for native modules
│   ├── navigation/
│   ├── screens/
│   ├── state/               App state store
│   ├── theme/
│   └── components/
├── .env.example
└── README.md
```

### 2. Native Keystore module

Written in Kotlin and exposed to JavaScript as `DeviceKey`.

| Method | Behaviour |
|---|---|
| `generate()` | Create an EC P-256 key pair in the Android Keystore under the alias `nightroll_device_key`, for signing only, digest SHA-256. Return the public key as base64 DER. |
| `getPublicKey()` | Return the public key, or null if no key exists |
| `sign(data)` | Sign the given bytes with SHA256withECDSA. Return the signature as base64 DER. |
| `exists()` | True if the key is present |
| `delete()` | Remove the key. Used on re-enrollment. |
| `securityLevel()` | Report `strongbox`, `tee` or `software` |

Rules:
- Ask for StrongBox first. If the phone lacks it, fall back to the trusted execution environment.
- The key is not exportable. The private key never reaches JavaScript.
- Do not require a fingerprint or PIN prompt for each signature. Marking has to work in one tap. Identity is proven by the face check.
- `generate()` refuses to overwrite an existing key unless `delete()` was called first.
- `securityLevel()` is sent at enrollment so the backend can record it. A `software` level is logged as a warning.

### 3. Signed request format

Every request from the app that acts for a student carries three headers.

| Header | Value |
|---|---|
| `X-Student-Id` | Student UUID |
| `X-Timestamp` | Current time, Unix seconds |
| `X-Signature` | Base64 signature over the string below |

String to sign, joined with newlines:

```text
<HTTP method>
<path with query>
<X-Timestamp>
<SHA-256 hex of the request body, or of the empty string>
```

The backend rejects a timestamp more than 60 seconds from its own clock. This format covers the status and nonce fetch and the enrollment steps. The marking request has its own stronger envelope, defined in Phase 7.

| # | Task |
|---|---|
| 3.1 | Build the string and sign it in `src/api/signing.ts` |
| 3.2 | Wrap `fetch` in `src/api/client.ts`: base URL from env, 10-second timeout, signing for student routes |
| 3.3 | Map the backend's error shape to typed errors the screens can show |
| 3.4 | Document the format in `docs/TRD.md` |

### 4. No push notifications

| # | Task |
|---|---|
| 4.1 | Do not add Firebase, FCM, or any push or background-messaging library. Students open the app themselves. |
| 4.2 | The app does not request notification permission and does not register a push token. |
| 4.3 | The app sends no reminders. The warden's announcement and the student's own habit carry the 10 PM start. |
| 4.4 | The Home screen makes the opening time plain, so a student who opens the app early knows when to come back. |

### 5. Local storage

| Stored | Where | Notes |
|---|---|---|
| Student ID, room ID, room number | Encrypted app storage | Set at enrollment |
| Enrollment state | Encrypted app storage | `none`, `enrolled` |
| Last window status and its time | App storage | Shown when offline |

Nothing biometric is stored on the phone: no photo, no embedding, no frame.

### 6. Navigation and screens

| Screen | Purpose | State after this phase |
|---|---|---|
| Welcome | First launch, explains what the app does | Complete |
| Consent | Privacy notice and consent | Shell, finished in Phase 6 |
| Enrollment | Code entry, face capture, room scan | Shell, finished in Phase 6 |
| Home | Window status and the "Mark attendance" button | Shows window state from the server |
| Marking | Guard checks, liveness, capture | Shell, finished in Phase 7 |
| Result | Verdict and reason | Shell with sample data |
| Fallback | "Use the ground-floor scanner" with the reason | Complete |
| Settings | Device info, key security level, re-enroll | Complete |

Flow: a phone with no key goes to Welcome, then Consent, then Enrollment. An enrolled phone goes straight to Home.

### 7. Permissions

Declare now, request at the moment of need.

| Permission | Requested when |
|---|---|
| `INTERNET`, `ACCESS_NETWORK_STATE` | Granted at install |
| `CAMERA` | Start of enrollment or marking |
| `ACCESS_FINE_LOCATION` | Before the first Wi-Fi scan, with a plain explanation of why |
| `ACCESS_WIFI_STATE`, `CHANGE_WIFI_STATE` | Granted at install |
| `NEARBY_WIFI_DEVICES` | Before the first Wi-Fi scan, Android 13 and newer |

Each request is preceded by one screen saying what the permission is for. The location text must say that the app reads nearby Wi-Fi names to confirm the room, and does not track where the student goes.

### 8. Home screen behaviour

| # | Task |
|---|---|
| 8.1 | On open, and every 60 seconds while Home is visible, call `GET /v1/attendance/nonce` |
| 8.2 | `open`: show the closing time and enable "Mark attendance" |
| 8.3 | `scheduled`: show "Attendance opens at [time]. Open NightRoll then." |
| 8.4 | `marked`: show "Marked present tonight" and disable the button |
| 8.5 | `off` or `closed`: show the state and what to do next. A student with no mark is directed to the warden. |
| 8.6 | When offline, show the last known state with its time, and a retry button |

---

## Files

```text
app/src/screens/Home.tsx
app/src/api/client.ts
app/src/api/signing.ts
app/src/native/DeviceKey.ts
app/android/app/src/main/java/com/zerolatency/nightroll/keystore/
```

## Exit criteria

- [ ] A debug build installs and opens on both test phones.
- [ ] `DeviceKey.generate()` returns a public key, and `securityLevel()` reports `strongbox` or `tee` on a real phone.
- [ ] A signature made on the phone verifies in a Python script using the returned public key.
- [ ] Calling `generate()` twice does not replace the first key.
- [ ] Opening the app during a test window shows "Mark attendance" enabled, with the closing time.
- [ ] Opening the app before the window shows the opening time.
- [ ] Home refreshes on its own within 60 seconds of a state change.
- [ ] A release build runs on a test phone, signed with the release keystore.
- [ ] The app requests no notification permission and contains no push library.

## Deferred to Phase 13

- Tests for the signing string builder against fixed vectors.
- Home refresh behaviour on weak networks.

## Risks

| Risk | What to do |
|---|---|
| Student forgets to open the app at window time | Warden announcement. Home shows the opening time. Reminder method is an open question in the PRD. |
| Key is lost when the app is reinstalled | Expected. The student re-enrolls at the warden's desk. |
| StrongBox missing on older phones | Fall back to the trusted execution environment and record the level |

## Hand-off to Phase 5 and Phase 6

Phase 6 needs the Keystore module, the API client and the Enrollment shell. Phase 5 is independent and can run alongside this phase.
