# Student app (Expo, Android)

Expo app for students: device key, enrollment, Home status, nightly marking. Android only for the hackathon. Built in Phases 4 to 7.

## Status

Phase 4 is done: the `DeviceKey` Expo Module (Kotlin, Android Keystore, StrongBox with a TEE
fallback), a signed API client, Home showing live window status with a 60-second refresh and
an offline fallback, Welcome/Fallback/Settings screens, and the dev-only cleartext HTTP config
plugin for LAN testing. Consent, Enrollment and Marking stay shells until Phases 6 and 7.

## Stack

| Package | Used for |
|---|---|
| expo, expo-router | App runtime and file-based routing (`src/app`) |
| react-native 0.86, react 19 | UI |
| expo-dev-client | Development build, needed for any native code |
| expo-secure-store | Sensitive local values (student and room IDs) |
| @react-native-async-storage/async-storage | Non-sensitive local state |
| expo-build-properties | Android `minSdkVersion` 28 |
| expo-crypto | SHA-256 for the signed-request body hash (`src/api/signing.ts`) |
| @expo/config-plugins | `plugins/withDevCleartextHttp.js`, dev-build-only cleartext HTTP |
| eslint, eslint-config-expo, prettier | Lint and format |

`modules/device-key` is the Kotlin Expo Module for the Keystore-backed signing key. Later
phases add `react-native-vision-camera` for enrollment and marking.

## How it runs

| What | Runs in Expo Go | Runs in a development build |
|---|---|---|
| Welcome, Consent and Home (`EXPO_PUBLIC_MOCK_STATUS=true` for Home) | Yes | Yes |
| Settings (device info needs a dev build; the rest works) | Partly | Yes |
| Device key, Wi-Fi scan, Play Integrity, camera checks | No | Yes |

Expo Go is for quick checks of screens on a phone. The test phones use a development build made with EAS.

## Requirements

- Node.js 20 LTS
- An Expo account (free) for EAS builds
- For local Android builds only: JDK 17 and Android Studio with an Android SDK
- A filled-in `app/.env`, with the values as `EXPO_PUBLIC_` variables

## Setup

```bash
cd app
cp .env.example .env
npm install
```

## Scripts

```bash
npm run typecheck     # tsc --noEmit
npm run lint          # expo lint
npx prettier --write "src/**/*.{ts,tsx}"
```

## Run

```bash
npx expo start                                               # Metro; scan with Expo Go for screens
npx eas-cli build --profile development --platform android   # once: development build for the phones
npx expo start --dev-client                                  # use the development build on the phone
```

The phone and the laptop must be on the same Wi-Fi. Use the laptop's LAN address for `EXPO_PUBLIC_API_BASE_URL`.

## Release build (Phase 12)

```bash
npx eas-cli build --profile production --platform android
```
