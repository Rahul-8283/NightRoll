# Phase 4: Mobile App Foundation and Device Key

| | |
|---|---|
| **Type** | Implementation |
| **Depends on** | Phases 0, 3 |
| **Unlocks** | Phases 6, 7 |
| **Lead** | App |

## Goal

An Expo app (React Native, TypeScript) that installs on the test phones, holds a hardware-backed signing key, shows tonight's window status when a student opens it, and signs requests to the backend. The Kotlin code lives in Expo Modules inside the project.

Screens without native code can be viewed in Expo Go. Anything that uses the key, Wi-Fi or Play Integrity runs in a development build made with EAS.

## Outcome

- `npx expo start` runs the app. Welcome, Consent and Home open in Expo Go on a phone, with mock status.
- A development build from EAS installs on both test phones.
- The `DeviceKey` Expo Module creates a non-exportable key in the Android Keystore and signs bytes with it.
- Home shows the window state from the server, including the next opening time when no window is open.
- The API client attaches device signatures to requests.
- Screens exist for every step, with placeholders where later phases fill in.

## Scope

**In:** Expo project setup, the `DeviceKey` Expo Module, development build, navigation, permissions through a config plugin, API client, local storage, Home screen status, screen shells.
**Out:** camera, liveness, Wi-Fi scan, Play Integrity (Phase 7), enrollment logic (Phase 6). No push notifications of any kind.

---

## Tasks

### 1. Project setup

| # | Task |
|---|---|
| 1.1 | Create the app in `app/` with `npx create-expo-app@latest` using the TypeScript template with expo-router. Keep the generated layout and remove the demo screens. |
| 1.2 | In `app.config.ts`, set the name to `NightRoll`, the Android package to `com.zerolatency.nightroll`, and the URL scheme to `nightroll` |
| 1.3 | Set Android `minSdkVersion` to 28 with `expo-build-properties` |
| 1.4 | Add `expo-dev-client` so the app runs as a development build |
| 1.5 | Add `expo-secure-store` for sensitive local values (section 5). It works in Expo Go. |
| 1.6 | Add no Firebase, push or background-messaging package. The app talks only to the NightRoll API. |
| 1.7 | Add ESLint and Prettier with Expo's defaults |
| 1.8 | Write `app/README.md` with install, run and build steps |
| 1.9 | Do not commit generated `android/` or `ios/` folders. Native builds run on EAS. |

```text
app/
├── app/                      expo-router screens (file-based routes)
│   ├── _layout.tsx
│   ├── index.tsx             Home
│   ├── welcome.tsx
│   ├── consent.tsx
│   ├── enroll.tsx
│   ├── mark.tsx
│   ├── result.tsx
│   └── fallback.tsx
├── src/
│   ├── api/                  client, signing, error mapping
│   ├── state/                app state store
│   └── theme/
├── modules/
│   └── device-key/           Expo Module (Kotlin): DeviceKey
│       ├── index.ts          TypeScript API
│       └── android/src/main/java/expo/modules/devicekey/
├── plugins/                  config plugins: permissions, dev-only cleartext HTTP
├── app.config.ts
├── eas.json                  development, preview and production profiles
├── .env.example
└── README.md
```

### 2. DeviceKey Expo Module

Create it inside `app/` with `npx create-expo-module@latest --local device-key`. The module is written in Kotlin and exposed to JavaScript as `DeviceKey`.

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
- Calling `DeviceKey` in Expo Go fails with a clear "needs a development build" message, not a crash.

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
| 3.2 | Wrap `fetch` in `src/api/client.ts`: base URL from `EXPO_PUBLIC_API_BASE_URL`, 10-second timeout, signing for student routes |
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
| Student ID, room ID, room number | `expo-secure-store` | Set at enrollment |
| Enrollment state | `expo-secure-store` | `none`, `enrolled` |
| Last window status and its time | AsyncStorage | Non-sensitive; shown when offline |

Nothing biometric is stored on the phone: no photo, no embedding, no frame.

### 6. Navigation and screens

| Screen | Route | Purpose | State after this phase | Runs in Expo Go |
|---|---|---|---|---|
| Welcome | `welcome` | First launch, explains what the app does | Complete | Yes |
| Consent | `consent` | Privacy notice and consent | Shell, finished in Phase 6 | Yes |
| Enrollment | `enroll` | Code entry, face capture, room scan | Shell, finished in Phase 6 | No (camera) |
| Home | `index` | Window status and the "Mark attendance" button | Shows window state from the server | Yes, with mock status |
| Marking | `mark` | Guard checks, liveness, capture | Shell, finished in Phase 7 | No |
| Result | `result` | Verdict and reason | Shell with sample data | Yes |
| Fallback | `fallback` | "Use the ground-floor scanner" with the reason | Complete | Yes |
| Settings | `settings` | Device info, key security level, re-enroll | Complete | Partly (key info needs a dev build) |

Flow: a phone with no key goes to Welcome, then Consent, then Enrollment. An enrolled phone goes straight to Home.

### 7. Permissions

Declared in `app.config.ts` and added by a config plugin in `plugins/`. Requested at the moment of need.

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
| 8.7 | With `EXPO_PUBLIC_MOCK_STATUS=true`, Home uses fixed sample states, so the screen can be checked in Expo Go without the backend |

### 9. Running in Expo Go and in a development build

| # | Task |
|---|---|
| 9.1 | Run `npx expo start` and open the screens in Expo Go on a phone. Only screens without native code are expected to work there. |
| 9.2 | Build the development profile once: `npx eas-cli build --profile development --platform android`. Install the APK from the link EAS gives. |
| 9.3 | Run `npx expo start --dev-client` and open the development build on the phone. The phone and laptop must be on the same Wi-Fi. |
| 9.4 | Set `EXPO_PUBLIC_API_BASE_URL` to the laptop's LAN address. `10.0.2.2` works only in the Android emulator. |
| 9.5 | Cleartext HTTP to the LAN is allowed in the development build only, through a config plugin. Release builds use HTTPS (Phase 12). |
| 9.6 | Keep `eas.json` with `development`, `preview` and `production` profiles. Only `production` is used for the demo build. |

---

## Files

```text
app/app/index.tsx
app/src/api/client.ts
app/src/api/signing.ts
app/modules/device-key/
app/plugins/
app/app.config.ts
app/eas.json
```

## Exit criteria

- [ ] `npx expo start` runs, and Welcome, Consent and Home open in Expo Go with mock status.
- [ ] A development build from EAS installs on both test phones.
- [ ] `DeviceKey.generate()` returns a public key, and `securityLevel()` reports `strongbox` or `tee` on a real phone.
- [ ] A signature made on the phone verifies in a Python script using the returned public key.
- [ ] Calling `generate()` twice does not replace the first key.
- [ ] Opening the app during a test window (development build, real backend) shows "Mark attendance" enabled, with the closing time.
- [ ] Opening the app before the window shows the opening time.
- [ ] Home refreshes on its own within 60 seconds of a state change.
- [ ] A production build from EAS installs and runs.
- [ ] The app requests no notification permission and contains no push library.

## Deferred to Phase 13

- Tests for the signing string builder against fixed vectors.
- Home refresh behaviour on weak networks.

## Risks

| Risk | What to do |
|---|---|
| Expo Go cannot run native code | Use the development build for anything native. Expo Go is for screens only. |
| An Expo SDK upgrade breaks the native module | Pin the SDK. Upgrade only at a phase boundary, and rebuild the development build after. |
| The phone cannot reach the laptop's API | Same Wi-Fi, the LAN address in `EXPO_PUBLIC_API_BASE_URL`, and the firewall allows port 8000 |
| Student forgets to open the app at window time | Warden announcement. Home shows the opening time. Reminder method is an open question in the PRD. |
| Key is lost when the app is reinstalled | Expected. The student re-enrolls at the warden's desk. |
| StrongBox missing on older phones | Fall back to the trusted execution environment and record the level |

## Hand-off to Phase 5 and Phase 6

Phase 6 needs the `DeviceKey` module, the API client and the Enrollment shell. Phase 5 is independent and can run alongside this phase.
