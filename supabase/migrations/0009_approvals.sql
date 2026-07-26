-- AEON OS Phase 19: Human-in-the-Loop (HITL) Approvals
-- Adds approval checkpoints to event-driven automations.

-- Extend automation rules with an approval-required flag.
ALTER TABLE automation_rules
  ADD COLUMN IF NOT EXISTS approval_required BOOLEAN DEFAULT false,
  ADD COLUMN IF NOT EXISTS approver_message TEXT DEFAULT '';

-- Pending approval requests created when an automation with approval_required fires.
CREATE TABLE IF NOT EXISTS approval_requests (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  rule_id UUID REFERENCES automation_rules(id) ON DELETE CASCADE,
  execution_id UUID REFERENCES automation_executions(id) ON DELETE SET NULL,
  event_type TEXT NOT NULL,
  event_payload JSONB DEFAULT '{}'::jsonb,
  action_type TEXT NOT NULL,
  action_config JSONB DEFAULT '{}'::jsonb,
  status TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'rejected', 'cancelled')) DEFAULT 'pending',
  workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
  user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  requested_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  approved_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  reason TEXT DEFAULT '',
  result JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
  resolved_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_approval_requests_workspace
  ON approval_requests(workspace_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_approval_requests_rule
  ON approval_requests(rule_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_approval_requests_status
  ON approval_requests(status, created_at DESC);

ALTER TABLE approval_requests ENABLE ROW LEVEL SECURITY;

-- Workspace members can view/manage approval requests in their workspace.
CREATE POLICY "Workspace members can view approval requests"
  ON approval_requests
  FOR SELECT
  USING (
    workspace_id IS NULL
    OR EXISTS (
      SELECT 1 FROM memberships
      WHERE memberships.workspace_id = approval_requests.workspace_id
        AND memberships.user_id = auth.uid()
    )
  );

CREATE POLICY "Workspace operators can resolve approval requests"
  ON approval_requests
  FOR UPDATE
  USING (
    workspace_id IS NULL
    OR EXISTS (
      SELECT 1 FROM memberships
      WHERE memberships.workspace_id = approval_requests.workspace_id
        AND memberships.user_id = auth.uid()
        AND memberships.role IN ('ADMIN', 'OPERATOR')
    )
  );

-- Allow automation executors to insert approval requests.
CREATE POLICY "Service role can insert approval requests"
  ON approval_requests
  FOR INSERT
  WITH CHECK (true);
