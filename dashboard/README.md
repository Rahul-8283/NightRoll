# Warden dashboard

React web app for wardens and admins: live room view, review queue, window controls, enrollment desk. Built in Phase 10.

## Status

Phase 0 creates only the environment file. There is no code yet.

## Requirements

- Node.js 20 LTS
- A filled-in `dashboard/.env` (public values only: the anon key, never the service role key)

## Setup

```bash
cd dashboard
cp .env.example .env
npm install                           # Phase 10 creates package.json
```

## Run

```bash
npm run dev                           # http://localhost:5173, from Phase 10
npm run build                         # static build for nginx, Phase 12
```
