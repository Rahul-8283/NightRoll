# Scripts

One-off tools and risk spikes. Run from the `backend` folder so its uv environment has
`asyncpg` and `httpx`:

```bash
cd backend
uv run python ../scripts/seed.py
uv run python ../scripts/create_warden.py --email warden@example.com --role warden
```

- `spikes/`: Phase 0 throwaway checks. Results go in `spikes/RESULTS.md`.
- `check_setup.py`: Phase 0 environment and connection check.
- `seed.py`: Phase 1. Loads demo rooms, access points and test students from
  `config/rooms.local.json` (or the example). Safe to run twice; it upserts by room
  number, BSSID and roll number.
- `create_warden.py`: Phase 1. Creates or updates a Supabase Auth user with
  `app_metadata.role` set to `warden` or `admin`. The password is read from
  `NIGHTROLL_WARDEN_PASSWORD` or prompted for; it is never printed or passed as a
  command-line argument.

Scripts that talk to Supabase read `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` from
`backend/.env`. Never hard-code them.
