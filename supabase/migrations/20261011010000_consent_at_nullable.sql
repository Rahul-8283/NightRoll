-- Phase 6: consent is given at enrollment and can be withdrawn, so a student row exists before it.
-- consent_at is therefore empty until the student agrees, and cleared again on withdrawal.
alter table students alter column consent_at drop not null;

-- The Phase 1 seed filled consent_at only to satisfy the old constraint. Nobody who has not enrolled
-- has consented, so remove the placeholder value.
update students set consent_at = null where enrolled_at is null;
