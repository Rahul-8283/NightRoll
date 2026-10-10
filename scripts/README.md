# Scripts

One-off tools and risk spikes.

- `spikes/`: Phase 0 throwaway checks. Results go in `spikes/RESULTS.md`.
- Later: `seed.py` (Phase 1), `create_warden.py` (Phase 1).

Scripts that talk to Supabase need `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` in the environment. Load them from `backend/.env`; never hard-code them.
