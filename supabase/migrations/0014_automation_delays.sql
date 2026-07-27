-- AEON OS Phase 30: Automation Time Delays (Wait Steps)
-- Adds durable sleeping state and resume_at tracking so multi-step automations
-- can pause and resume across scheduler ticks.

-- Expand automation_executions status to include sleeping and completed.
ALTER TABLE automation_executions DROP CONSTRAINT IF EXISTS automation_executions_status_check;
ALTER TABLE automation_executions ADD CONSTRAINT automation_executions_status_check
  CHECK (status IN ('triggered', 'failed', 'pending_approval', 'throttled', 'sleeping', 'completed'));

-- Timestamp when a sleeping execution should resume.
ALTER TABLE automation_executions ADD COLUMN IF NOT EXISTS resume_at TIMESTAMPTZ;

-- Optional persisted state for resumable executions (current step, accumulated steps, etc.).
ALTER TABLE automation_executions ADD COLUMN IF NOT EXISTS state JSONB DEFAULT '{}'::jsonb;

-- Index to efficiently find executions that are due to resume.
CREATE INDEX IF NOT EXISTS idx_automation_executions_sleeping
  ON automation_executions(status, resume_at)
  WHERE status = 'sleeping';
