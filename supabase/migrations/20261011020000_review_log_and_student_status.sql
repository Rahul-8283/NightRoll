-- Phase 11: reviews become an append-only log, and one view decides each student's status in each window.
-- Marks are never edited. A decision is a new reviews row; the latest decision of each kind wins.

alter table reviews drop constraint reviews_pkey;
alter table reviews add column id bigserial primary key;
create index reviews_mark_reviewed_idx on reviews (mark_id, reviewed_at desc);

alter table reviews drop constraint reviews_decision_check;
alter table reviews
  add constraint reviews_decision_check check (decision in ('APPROVED', 'DECLINED', 'OVERRIDDEN', 'MANUAL'));

-- An override sets the status the warden chose. A manual mark carries its note in a MANUAL review row.
alter table reviews add column status text check (status in ('PRESENT', 'ABSENT'));
alter table reviews
  add constraint reviews_override_status_check check (decision <> 'OVERRIDDEN' or status is not null);

-- The single source of a student's status in a window. Every screen, the export and the room counts read it.
-- Precedence: override, manual mark, automatic present, approved, declined, pending review, absent, off, not marked.
create or replace view student_window_status as
with decisions as (
  select distinct on (m.window_id, m.student_id, r.decision)
         m.window_id, m.student_id, r.decision, r.status, r.reviewed_by, r.note, r.reviewed_at
  from reviews r
  join attendance_marks m on m.id = r.mark_id
  order by m.window_id, m.student_id, r.decision, r.reviewed_at desc, r.id desc
),
decided as (
  select distinct on (d.window_id, d.student_id)
         d.window_id, d.student_id, d.decision, d.status, d.reviewed_by, d.note, d.reviewed_at
  from decisions d
  order by d.window_id, d.student_id,
           case d.decision when 'OVERRIDDEN' then 1 when 'MANUAL' then 2 when 'APPROVED' then 3 when 'DECLINED' then 4 end
),
marked as (
  select m.window_id, m.student_id,
         bool_or(m.verdict = 'MANUAL') as has_manual,
         bool_or(m.verdict = 'PRESENT') as has_present,
         bool_or(m.verdict = 'ABSENT') as has_absent
  from attendance_marks m
  group by m.window_id, m.student_id
),
awaiting as (
  select distinct m.window_id, m.student_id
  from attendance_marks m
  where m.verdict = 'NEEDS_REVIEW'
    and not exists (select 1 from reviews r where r.mark_id = m.id)
),
facts as (
  select w.id as window_id, w.state as window_state, w.closes_at,
         s.id as student_id, s.room_id,
         coalesce(mk.has_manual, false) as has_manual,
         coalesce(mk.has_present, false) as has_present,
         coalesce(mk.has_absent, false) as has_absent,
         (aw.student_id is not null) as awaiting,
         dc.decision, dc.status as decision_status, dc.reviewed_by, dc.note, dc.reviewed_at
  from attendance_windows w
  cross join (select id, room_id from students where active and enrolled_at is not null) s
  left join marked mk on mk.window_id = w.id and mk.student_id = s.id
  left join awaiting aw on aw.window_id = w.id and aw.student_id = s.id
  left join decided dc on dc.window_id = w.id and dc.student_id = s.id
),
judged as (
  select f.*,
         case
           when f.decision = 'OVERRIDDEN' then 'override'
           when f.has_manual then 'manual'
           when f.has_present then 'automatic'
           when f.decision = 'APPROVED' then 'approved'
           when f.decision = 'DECLINED' then 'declined'
         end as how
  from facts f
)
select window_id, student_id, room_id, window_state, closes_at,
       case
         when how = 'override' then decision_status
         when how in ('manual', 'automatic', 'approved') then 'PRESENT'
         when how = 'declined' then 'ABSENT'
         when awaiting then 'PENDING'
         when window_state = 'off' then 'OFF'
         when has_absent or window_state = 'closed' then 'ABSENT'
         else 'NOT_MARKED'
       end as status,
       how as decided_how,
       case when how in ('override', 'manual', 'approved', 'declined') then reviewed_by end as decided_by,
       case when how in ('override', 'manual', 'approved', 'declined') then note end as decided_note,
       case when how in ('override', 'manual', 'approved', 'declined') then reviewed_at end as decided_at
from judged;
