# Supabase

Hosted Supabase holds the database (PostgreSQL with pgvector), warden login and the private `frames` bucket. Schema changes are made only through migration files in `migrations/`.

## One-time setup (Phase 0)

1. Install the Supabase CLI (see the main README).
2. From the repo root:

   ```bash
   supabase login
   supabase init                       # creates supabase/config.toml
   supabase link --project-ref <your-project-ref>
   ```

3. In the Supabase dashboard for `nightroll-dev`:
   - Database, Extensions: enable `vector`.
   - Storage: create a private bucket named `frames`.
   - Authentication: turn off public sign-ups; turn on TOTP MFA.
   - Create one test warden account.

`supabase/.temp/` and `supabase/.branches/` are git-ignored by the repo `.gitignore`.

## Later

- Phase 1 adds the migrations and applies them with `supabase db push`.
