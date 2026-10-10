# Migrations

Every database change lives here as a SQL file, applied in order with `npx supabase db push`.

- File names: `YYYYMMDDHHMMSS_short_name.sql`, for example `20261010120000_init_rooms.sql`.
- Never edit a migration that has already been applied to `nightroll-dev`. Add a new one instead.
- Never change tables by hand in the dashboard. Run `npx supabase db diff` to find any drift.

Phase 1 adds the first migrations (rooms, students, attendance, audit and row-level security).
