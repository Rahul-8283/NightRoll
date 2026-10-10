-- Phase 1, section 4: the backend is the only thing that reads or writes these tables.
-- Enabling row-level security with no policy for anon/authenticated denies both roles.
-- The backend connects with the database connection string, which bypasses RLS entirely,
-- so no policy is defined here on purpose.
alter table rooms enable row level security;
alter table access_points enable row level security;
alter table students enable row level security;
alter table face_embeddings enable row level security;
alter table devices enable row level security;
alter table room_fingerprints enable row level security;
alter table attendance_windows enable row level security;
alter table attendance_marks enable row level security;
alter table reviews enable row level security;
alter table enrollment_codes enable row level security;
alter table audit_log enable row level security;
