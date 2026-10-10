# Student app (Android)

React Native app for students: device key, enrollment, Home status, nightly marking. Android only for the hackathon. Built in Phases 4 to 7.

## Status

Phase 0 creates only the environment file. There is no project yet. The React Native project is created in Phase 4.

## Requirements

- Node.js 20 LTS
- JDK 17
- Android Studio with an Android SDK (API 34 or newer)
- An Android phone with USB debugging on, or an emulator
- A filled-in `app/.env`

## Setup (from Phase 4)

```bash
cd app
cp .env.example .env
npm install
```

## Run (from Phase 4)

```bash
npx react-native start                # Metro bundler, one terminal
npx react-native run-android          # build and install on the phone or emulator
```

Release build (Phase 12): `cd android && ./gradlew assembleRelease`.
