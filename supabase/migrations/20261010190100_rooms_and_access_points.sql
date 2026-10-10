-- Phase 1.2: rooms and their access points.
create table rooms (
  id uuid primary key default gen_random_uuid(),
  number text not null unique,
  floor int not null,
  subnet cidr,
  created_at timestamptz not null default now()
);

create table access_points (
  bssid macaddr primary key,
  room_id uuid references rooms(id),
  band text check (band in ('2.4GHz', '5GHz'))
);

-- Phase 1, section 3: used by the fingerprint and network checks.
create index access_points_room_id_idx on access_points (room_id);
