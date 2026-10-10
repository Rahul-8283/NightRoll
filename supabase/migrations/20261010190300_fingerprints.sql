-- Phase 1.4: the WiFi fingerprint captured for each room, versioned.
create table room_fingerprints (
  id uuid primary key default gen_random_uuid(),
  room_id uuid not null references rooms(id),
  version int not null,
  pattern jsonb not null,
  created_at timestamptz not null default now(),
  unique (room_id, version)
);
