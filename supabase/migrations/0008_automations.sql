-- AEON OS Phase 18: Event-Driven Automations
-- Stores automation rules and execution logs.

CREATE TABLE IF NOT EXISTS automation_rules (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  name TEXT NOT NULL,
  event_type TEXT NOT NULL,
  condition JSONB DEFAULT '{}'::jsonb,
  action_type TEXT NOT NULL CHECK (action_type IN ('webhook', 'swarm', 'workflow')),
  action_config JSONB DEFAULT '{}'::jsonb,
  enabled BOOLEAN DEFAULT true,
  workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
  created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
  updated_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_automation_rules_workspace
  ON automation_rules(workspace_id, event_type);

CREATE INDEX IF NOT EXISTS idx_automation_rules_event_enabled
  ON automation_rules(event_type, enabled);

CREATE TABLE IF NOT EXISTS automation_executions (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  rule_id UUID REFERENCES automation_rules(id) ON DELETE CASCADE,
  event_type TEXT NOT NULL,
  event_payload JSONB DEFAULT '{}'::jsonb,
  status TEXT NOT NULL CHECK (status IN ('triggered', 'failed')),
  result JSONB DEFAULT '{}'::jsonb,
  workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
  user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_automation_executions_rule
  ON automation_executions(rule_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_automation_executions_workspace
  ON automation_executions(workspace_id, created_at DESC);

ALTER TABLE automation_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE automation_executions ENABLE ROW LEVEL SECURITY;

-- Members of a workspace can view/manage rules in that workspace.
CREATE POLICY "Workspace members can manage automation rules"
  ON automation_rules
  USING (
    workspace_id IS NULL
    OR EXISTS (
      SELECT 1 FROM memberships
      WHERE memberships.workspace_id = automation_rules.workspace_id
        AND memberships.user_id = auth.uid()
    )
  );

CREATE POLICY "Workspace members can view automation executions"
  ON automation_executions
  FOR SELECT
  USING (
    workspace_id IS NULL
    OR EXISTS (
      SELECT 1 FROM memberships
      WHERE memberships.workspace_id = automation_executions.workspace_id
        AND memberships.user_id = auth.uid()
    )
  );
