-- Phase 1.3: students, their devices and face embeddings.
create table students (
  id uuid primary key default gen_random_uuid(),
  roll_number text not null unique,
  name text not null,
  room_id uuid not null references rooms(id),
  consent_at timestamptz not null,
  enrolled_at timestamptz,
  active boolean not null default true
);

-- Phase 1, section 3: used to build room tiles.
create index students_room_id_idx on students (room_id);

-- Supabase installs pgvector into the extensions schema, not public, so the type
-- is schema-qualified here.
create table face_embeddings (
  student_id uuid primary key references students(id),
  embedding extensions.vector(512) not null,
  model_version text not null,
  created_at timestamptz not null default now()
);

create table devices (
  id uuid primary key default gen_random_uuid(),
  student_id uuid not null references students(id),
  public_key bytea not null,
  key_alias text not null,
  active boolean not null default true,
  enrolled_at timestamptz not null default now()
);

-- Phase 1, section 2: a student has at most one active device at a time.
create unique index one_active_device on devices (student_id) where active;
