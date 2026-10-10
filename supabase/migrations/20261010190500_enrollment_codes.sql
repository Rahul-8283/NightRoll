-- Phase 1.6: one-time codes a warden issues so a student can enroll a device.
-- The code itself is never stored, only its SHA-256 hash.
create table enrollment_codes (
  code_hash text primary key,
  student_id uuid references students(id),
  created_by uuid,
  expires_at timestamptz not null,
  used_at timestamptz
);
