-- AEON OS Phase 21: Inbound Webhooks & Omnichannel HITL Approvals
-- Adds externally-triggered webhooks and Slack workspace configuration.

-- Workspace-level Slack configuration for interactive approval messages.
ALTER TABLE workspaces
  ADD COLUMN IF NOT EXISTS slack_webhook_url TEXT DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS slack_signing_secret TEXT DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS slack_channel TEXT DEFAULT NULL;

-- Inbound webhook tokens that external systems can POST to.
CREATE TABLE IF NOT EXISTS inbound_webhooks (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE NOT NULL,
  name TEXT NOT NULL DEFAULT 'Inbound Webhook',
  token TEXT UNIQUE NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_inbound_webhooks_token
  ON inbound_webhooks(token);

CREATE INDEX IF NOT EXISTS idx_inbound_webhooks_workspace
  ON inbound_webhooks(workspace_id, created_at DESC);

ALTER TABLE inbound_webhooks ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Workspace members can view inbound webhooks"
  ON inbound_webhooks
  FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM memberships
      WHERE memberships.workspace_id = inbound_webhooks.workspace_id
        AND memberships.user_id = auth.uid()
    )
  );

CREATE POLICY "Workspace operators can manage inbound webhooks"
  ON inbound_webhooks
  FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM memberships
      WHERE memberships.workspace_id = inbound_webhooks.workspace_id
        AND memberships.user_id = auth.uid()
        AND memberships.role IN ('OPERATOR', 'ADMIN', 'SUPER_ADMIN')
    )
  );

-- Add inbound webhook as a triggerable event type.  The condition matcher can
-- filter on payload.webhook_id or payload.webhook_name if desired.
-- (No enum constraint exists; automation_rules.event_type is TEXT.)
