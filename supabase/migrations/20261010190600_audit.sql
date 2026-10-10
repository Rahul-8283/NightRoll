-- Phase 1.7: an append-only record of every action taken on the system.
-- Insert only. No update or delete is ever issued against this table.
create table audit_log (
  id bigserial primary key,
  actor text not null,
  action text not null,
  target_id uuid,
  payload jsonb,
  created_at timestamptz not null default now()
);

-- Phase 1, section 3: the audit view, read newest first.
create index audit_log_created_at_idx on audit_log (created_at);
