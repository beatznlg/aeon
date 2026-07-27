-- AEON OS Phase 26 — Sequential Multi-Step Action Chains
-- Adds an ordered list of actions to automation rules.
-- Legacy rules continue to use action_type/action_config; the engine falls back
-- to those fields when actions is empty or missing.

ALTER TABLE automation_rules
    ADD COLUMN IF NOT EXISTS actions JSONB DEFAULT '[]'::jsonb;
