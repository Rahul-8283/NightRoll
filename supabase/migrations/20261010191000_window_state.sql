-- Phase 3.2: the window lifecycle is stored as one state column; the off flag is folded into it.
alter table attendance_windows
  add column state text not null default 'scheduled'
  check (state in ('scheduled', 'open', 'closed', 'off'));

update attendance_windows set state = 'off' where off;

alter table attendance_windows drop column off;
