-- Phase 1.5: the attendance window lifecycle, marks and warden reviews.
create table attendance_windows (
  id uuid primary key default gen_random_uuid(),
  night date not null unique,
  opens_at timestamptz not null,
  closes_at timestamptz not null,
  off boolean not null default false,
  check (closes_at > opens_at)
);

create table attendance_marks (
  id uuid primary key default gen_random_uuid(),
  window_id uuid not null references attendance_windows(id),
  student_id uuid not null references students(id),
  verdict text not null check (verdict in ('PRESENT', 'NEEDS_REVIEW', 'REJECTED', 'ABSENT', 'MANUAL')),
  score numeric(4,3),
  reasons text[] not null default '{}',
  scores jsonb,
  -- Phase 1, section 2: a retry inside the same window is kept as its own attempt, not overwritten.
  attempt int not null default 1,
  -- Phase 1, section 2: the frames bucket folder for this mark; cleared once the face worker deletes them.
  frames_path text,
  marked_at timestamptz not null default now()
);

-- Phase 1, section 3: dashboard room counts and the duplicate-mark check.
create index attendance_marks_window_student_idx on attendance_marks (window_id, student_id);
-- Phase 1, section 3: the review queue and the absentee list.
create index attendance_marks_window_verdict_idx on attendance_marks (window_id, verdict);

-- At most one PRESENT mark per student per window.
create unique index one_present_per_window
  on attendance_marks (window_id, student_id)
  where verdict = 'PRESENT';

create table reviews (
  mark_id uuid primary key references attendance_marks(id),
  decision text not null check (decision in ('APPROVED', 'DECLINED', 'OVERRIDDEN')),
  reviewed_by text not null,
  note text,
  reviewed_at timestamptz not null default now()
);
