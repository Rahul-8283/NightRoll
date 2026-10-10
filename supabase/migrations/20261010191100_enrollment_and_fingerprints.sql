-- Phase 6: Enrollment consent version and room fingerprint reset support.

alter table students add column if not exists consent_version text;

alter table rooms add column if not exists fingerprint_reset_pending boolean not null default false;
