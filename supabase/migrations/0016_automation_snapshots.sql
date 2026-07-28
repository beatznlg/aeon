-- Phase 38: Automation Versioning & Rollback
-- Stores historical snapshots of automation rules so users can restore
-- previous configurations.

CREATE TABLE IF NOT EXISTS automation_rule_snapshots (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  rule_id UUID NOT NULL REFERENCES automation_rules(id) ON DELETE CASCADE,
  workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  event_type TEXT NOT NULL,
  condition JSONB DEFAULT '{}'::jsonb,
  action_type TEXT NOT NULL,
  action_config JSONB DEFAULT '{}'::jsonb,
  actions JSONB DEFAULT '[]'::jsonb,
  enabled BOOLEAN DEFAULT true,
  approval_required BOOLEAN DEFAULT false,
  approver_message TEXT DEFAULT '',
  schedule_type TEXT DEFAULT 'event',
  cron_expression TEXT,
  cooldown_minutes INTEGER DEFAULT 0,
  created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_automation_rule_snapshots_rule
  ON automation_rule_snapshots(rule_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_automation_rule_snapshots_workspace
  ON automation_rule_snapshots(workspace_id, created_at DESC);

ALTER TABLE automation_rule_snapshots ENABLE ROW LEVEL SECURITY;

-- Workspace members can view/manage snapshots in their workspace.
CREATE POLICY "Workspace members can manage automation rule snapshots"
  ON automation_rule_snapshots
  USING (
    workspace_id IS NULL
    OR EXISTS (
      SELECT 1 FROM memberships
      WHERE memberships.workspace_id = automation_rule_snapshots.workspace_id
        AND memberships.user_id = auth.uid()
    )
  );
