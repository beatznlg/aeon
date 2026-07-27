-- Phase 32: Persistent Automation State (Key-Value Variables)
-- Allows automations to set/get/delete/increment variables that persist
-- across executions and can be referenced via {{ state.KEY }} templates.

CREATE TABLE IF NOT EXISTS automation_variables (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
    key TEXT NOT NULL,
    value JSONB NOT NULL DEFAULT '{}'::jsonb,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, key)
);

-- Index for fast lookup by workspace and key
CREATE INDEX IF NOT EXISTS idx_automation_variables_workspace_key
    ON automation_variables (workspace_id, key);

-- Index for cleanup of expired variables
CREATE INDEX IF NOT EXISTS idx_automation_variables_expires_at
    ON automation_variables (expires_at);
