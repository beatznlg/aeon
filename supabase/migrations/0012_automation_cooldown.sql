-- AEON OS Phase 25: Automation Rule Cooldown / Throttling
-- Adds per-rule cooldown to prevent runaway executions.

ALTER TABLE automation_rules
  ADD COLUMN IF NOT EXISTS cooldown_minutes INTEGER NOT NULL DEFAULT 0 CHECK (cooldown_minutes >= 0),
  ADD COLUMN IF NOT EXISTS last_triggered_at TIMESTAMPTZ;

-- Index to efficiently find rules whose cooldown may have expired.
CREATE INDEX IF NOT EXISTS idx_automation_rules_cooldown
  ON automation_rules(enabled, cooldown_minutes, last_triggered_at);

-- The existing automation_executions status check only allows 'triggered' and 'failed'.
-- Expand it to support throttling and HITL approval states.
ALTER TABLE automation_executions DROP CONSTRAINT IF EXISTS automation_executions_status_check;
ALTER TABLE automation_executions ADD CONSTRAINT automation_executions_status_check
  CHECK (status IN ('triggered', 'failed', 'pending_approval', 'throttled'));
