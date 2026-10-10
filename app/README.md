# Student app (Expo, Android)

Expo app for students: device key, enrollment, Home status, nightly marking. Android only for the hackathon. Built in Phases 4 to 7.

## Status

The Expo project is created in Phase 4. Today this folder holds only the environment example.

## How it runs

| What | Runs in Expo Go | Runs in a development build |
|---|---|---|
| Welcome, consent and Home screens (with mock status) | Yes | Yes |
| Device key, Wi-Fi scan, Play Integrity, camera checks | No | Yes |

Expo Go is for quick checks of screens on a phone. The test phones use a development build made with EAS.

## Requirements

- Node.js 20 LTS
- An Expo account (free) for EAS builds
- For local Android builds only: JDK 17 and Android Studio with an Android SDK
- A filled-in `app/.env`, with the values as `EXPO_PUBLIC_` variables

## Setup (from Phase 4)

```bash
cd app
cp .env.example .env
npm install
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
