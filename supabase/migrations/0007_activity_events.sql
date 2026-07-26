-- AEON OS Phase 17: Real-time Activity Feed
-- Stores historical activity events for the activity stream.
-- Live events are also broadcast via SSE from the Next.js event bus.

CREATE TABLE IF NOT EXISTS activity_events (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  type TEXT NOT NULL,
  payload JSONB DEFAULT '{}'::jsonb NOT NULL,
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

-- Indexes for fast paginated lookups by workspace or user
CREATE INDEX IF NOT EXISTS idx_activity_events_workspace_created
  ON activity_events(workspace_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_activity_events_user_created
  ON activity_events(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_activity_events_type
  ON activity_events(type, created_at DESC);

-- Row Level Security: users can read activity for their own workspace memberships.
ALTER TABLE activity_events ENABLE ROW LEVEL SECURITY;

-- Policy: users can view activity events in workspaces they belong to.
CREATE POLICY "Workspace members can view activity events"
  ON activity_events
  FOR SELECT
  USING (
    workspace_id IS NULL
    OR EXISTS (
      SELECT 1 FROM memberships
      WHERE memberships.workspace_id = activity_events.workspace_id
        AND memberships.user_id = auth.uid()
    )
  );

-- Service-role writes bypass RLS; this migration only creates the table.
-- The Python backend uses the service role key to insert events.
