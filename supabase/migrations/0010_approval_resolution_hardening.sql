-- AEON OS Phase 19.1: atomic approval resolution hardening
-- Adds a short approval lifetime and a processing lease marker so a request
-- cannot be executed twice by concurrent resolvers.

ALTER TABLE approval_requests
  ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ DEFAULT (now() + interval '24 hours'),
  ADD COLUMN IF NOT EXISTS claimed_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS claimed_by TEXT;

-- Backfill legacy rows before enforcing the new lifecycle semantics.
UPDATE approval_requests
SET expires_at = created_at + interval '24 hours'
WHERE expires_at IS NULL;

ALTER TABLE approval_requests
  ALTER COLUMN expires_at SET DEFAULT (now() + interval '24 hours');

ALTER TABLE approval_requests
  DROP CONSTRAINT IF EXISTS approval_requests_status_check;

ALTER TABLE approval_requests
  ADD CONSTRAINT approval_requests_status_check
  CHECK (status IN ('pending', 'processing', 'approved', 'rejected', 'cancelled', 'expired'));

CREATE INDEX IF NOT EXISTS idx_approval_requests_expiry
  ON approval_requests(status, expires_at);
