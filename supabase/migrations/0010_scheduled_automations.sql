-- AEON OS Phase 20: Scheduled Automations (Cron Triggers)
-- Adds time-based triggers to automation rules.

-- Extend automation rules with schedule type, cron expression, and run tracking.
ALTER TABLE automation_rules
  ADD COLUMN IF NOT EXISTS schedule_type TEXT NOT NULL DEFAULT 'event' CHECK (schedule_type IN ('event', 'cron')),
  ADD COLUMN IF NOT EXISTS cron_expression TEXT DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS last_run_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS next_run_at TIMESTAMPTZ;

-- Index for efficiently finding due scheduled rules.
CREATE INDEX IF NOT EXISTS idx_automation_rules_schedule
  ON automation_rules(enabled, schedule_type, next_run_at)
  WHERE schedule_type = 'cron';
