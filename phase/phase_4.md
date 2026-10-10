# Phase 4: Mobile App Foundation and Device Key

| | |
|---|---|
| **Type** | Implementation |
| **Depends on** | Phases 0, 3 |
| **Unlocks** | Phases 6, 7 |
| **Lead** | App |

## Goal

A React Native Android app that installs on the test phones, holds a hardware-backed signing key, receives the window push, and can make a signed request to the backend. This is the shell that enrollment and marking are built into.

## Outcome

- The app builds and runs on both test phones.
- A native module creates a non-exportable key in the Android Keystore and signs bytes with it.
- The app receives the window-open push in the foreground, background and when closed.
- An API client attaches a device signature to requests.
- Screens exist for every step, with placeholders where later phases fill in.

## Scope

**In:** project setup, navigation, native Keystore module, push handling, API client, permissions, local storage, screen shells.
**Out:** camera, liveness, Wi-Fi scan, Play Integrity (all Phase 7), enrollment logic (Phase 6).

---

## Tasks

### 1. Project setup

| # | Task |
|---|---|
| 1.1 | Create the app in `app/` with the React Native CLI and TypeScript |
| 1.2 | Set the Android package to `com.zerolatency.nightroll` |
| 1.3 | Set `minSdkVersion` to 28 (Android 9) |
| 1.4 | Add `react-native-config` to read `app/.env` |
| 1.5 | Put `google-services.json` in `app/android/app/` and apply the Google services Gradle plugin |
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
│   ├── push/                FCM handlers
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

The backend rejects a timestamp more than 60 seconds from its own clock. This format covers the nonce fetch and the push-token update. The marking request has its own stronger envelope, defined in Phase 7.

| # | Task |
|---|---|
| 3.1 | Build the string and sign it in `src/api/signing.ts` |
| 3.2 | Wrap `fetch` in `src/api/client.ts`: base URL from env, 10-second timeout, signing for student routes |
| 3.3 | Map the backend's error shape to typed errors the screens can show |
| 3.4 | Document the format in `docs/TRD.md` |

### 4. Push handling

| # | Task |
|---|---|
| 4.1 | Add `@react-native-firebase/app` and `@react-native-firebase/messaging` |
| 4.2 | Ask for notification permission on Android 13 and newer |
| 4.3 | Get the FCM token at startup and whenever it refreshes. Send it to `PUT /v1/devices/push-token` once the device is enrolled. |
| 4.4 | Handle `type=window_open` data messages in the foreground, in the background and from a closed state |
| 4.5 | In the background or closed state, show a local notification: "Attendance is open until 10:30 PM. Tap to mark." |
| 4.6 | Tapping the notification opens the app on the marking screen |
| 4.7 | Create a high-importance notification channel named "Attendance" |

### 5. Local storage

| Stored | Where | Notes |
|---|---|---|
| Student ID, room ID, room number | Encrypted app storage | Set at enrollment |
| Enrollment state | Encrypted app storage | `none`, `enrolled` |
| Last result | App storage | For the home screen |

Nothing biometric is stored on the phone: no photo, no embedding, no frame.

### 6. Navigation and screens

| Screen | Purpose | State after this phase |
|---|---|---|
| Welcome | First launch, explains what the app does | Complete |
| Consent | Privacy notice and consent | Shell, finished in Phase 6 |
| Enrollment | Code entry, face capture, room scan | Shell, finished in Phase 6 |
| Home | Window status and the "Mark attendance" button | Shows window state from the backend |
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
| `POST_NOTIFICATIONS` | First launch, Android 13 and newer |
| `CAMERA` | Start of enrollment or marking |
| `ACCESS_FINE_LOCATION` | Before the first Wi-Fi scan, with a plain explanation of why |
| `ACCESS_WIFI_STATE`, `CHANGE_WIFI_STATE` | Granted at install |
| `NEARBY_WIFI_DEVICES` | Before the first Wi-Fi scan, Android 13 and newer |

Each request is preceded by one screen saying what the permission is for. The location text must say that the app reads nearby Wi-Fi names to confirm the room, and does not track where the student goes.

### 8. Home screen behaviour

| # | Task |
|---|---|
| 8.1 | On open, call the nonce endpoint. If a window is open, show the closing time and enable "Mark attendance". |
| 8.2 | If no window is open, show when the next one is expected |
| 8.3 | If already marked present tonight, show that and disable the button |
| 8.4 | Show a clear message with no network, and a retry button |

---

## Exit criteria

- [ ] A debug build installs and opens on both test phones.
- [ ] `DeviceKey.generate()` returns a public key, and `securityLevel()` reports `strongbox` or `tee` on a real phone.
- [ ] A signature made on the phone verifies in a Python script using the returned public key.
- [ ] Calling `generate()` twice does not replace the first key.
- [ ] A window-open push arrives with the app in the foreground, in the background and fully closed.
- [ ] Tapping the notification lands on the marking screen.
- [ ] The Home screen shows the open window's closing time.
- [ ] A release build runs on a test phone, signed with the release keystore.

## Deferred to Phase 13

- Tests for the signing string builder against fixed vectors.
- Push behaviour across phone brands with aggressive battery saving.

## Risks

| Risk | What to do |
|---|---|
| Some phone brands block background pushes | The app works when opened by hand. Note affected brands for the pitch. |
| Key is lost when the app is reinstalled | Expected. The student re-enrolls at the warden's desk. |
| StrongBox missing on older phones | Fall back to the trusted execution environment and record the level |

## Hand-off to Phase 5 and Phase 6

Phase 6 needs the Keystore module, the API client and the Enrollment shell. Phase 5 is independent and can run alongside this phase.
