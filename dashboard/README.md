# Warden dashboard

React web app for wardens and admins. Today it is a working shell: routes, layout, API client and Supabase client are in place. The screens are placeholders until Phase 10 builds them.

## Stack

| Library | Used for |
|---|---|
| React 19 with TypeScript | UI |
| Vite | Dev server and production build |
| react-router | Pages and navigation |
| TanStack Query | Fetching and caching API data |
| @supabase/supabase-js | Warden login only (attendance data goes through the NightRoll API) |

## Status

| Part | State |
|---|---|
| Project scaffold, build, lint | Done |
| Routes and layout | Done (placeholder pages) |
| API client and config check | Done |
| Login with MFA | Phase 10 |
| Tonight, room, windows and enrollment screens | Phase 10 |
| Live updates over WebSocket | Phase 10 |

## Requirements

- Node.js 20 LTS (Node 22 or newer also works)
- A filled-in `dashboard/.env` with public values only: the anon key, never the service role key

## Setup

```bash
cd dashboard
cp .env.example .env     # then fill in the values
npm install
```

Required variables (see `.env.example`):

| Variable | Purpose |
|---|---|
| `VITE_API_BASE_URL` | NightRoll API base, for example `http://localhost:8000/v1` |
| `VITE_WS_URL` | Live-update socket, used from Phase 10 |
| `VITE_SUPABASE_URL` | Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | Supabase public anon key |

If the Supabase values are missing, the app shows which ones to set instead of the pages.

## Run

```bash
npm run dev        # http://localhost:5173
npm run build      # type check and production build into dist/
npm run preview    # serve the built files locally
npm run lint       # oxlint
```

## Folders

```text
src/
├── main.tsx           App entry: query client, router, config check
├── routes.tsx         Route table
├── config.ts          Reads VITE_* variables
├── components/        Layout, shared pieces
├── lib/
│   ├── api.ts         NightRoll API client with the warden's token
│   └── supabase.ts    Supabase client (login only)
└── pages/             One file per screen
```

## Security rules

- Only `VITE_*` values reach the browser, and every one of them is public. Never put the service role key or any secret in `.env` for this app.
- Attendance data is never read from Supabase tables directly. The dashboard calls the NightRoll API, which enforces the warden role.
