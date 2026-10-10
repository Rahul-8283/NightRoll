-- Phase 1, section 5: the frames bucket, created idempotently so a clean project needs
-- no manual dashboard step. Kept private; no policy is added for anon/authenticated, so
-- storage.objects' own row-level security denies both roles by default. Only the service
-- role (which bypasses RLS) can read or write.
insert into storage.buckets (id, name, public)
values ('frames', 'frames', false)
on conflict (id) do update set public = false;
