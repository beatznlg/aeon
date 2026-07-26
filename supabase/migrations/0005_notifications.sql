-- AEON OS Phase: Notifications & Event System
-- Run after 0004_phase0_foundation.sql.

-- Notifications table
CREATE TABLE IF NOT EXISTS public.notifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  workspace_id UUID REFERENCES public.workspaces(id) ON DELETE SET NULL,
  type TEXT NOT NULL CHECK (type IN (
    'swarm_completed', 'swarm_failed', 'workflow_completed', 'workflow_failed',
    'chat_response', 'invoice_due', 'payment_succeeded', 'payment_failed',
    'api_key_created', 'api_key_revoked', 'member_added', 'member_removed',
    'integration_activated', 'integration_error', 'system_alert', 'admin_broadcast'
  )),
  title TEXT NOT NULL,
  body TEXT,
  icon TEXT DEFAULT '🔔',
  link TEXT,
  read BOOLEAN NOT NULL DEFAULT false,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_notifications_user ON public.notifications (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notifications_unread ON public.notifications (user_id, read) WHERE read = false;

-- Row Level Security
ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;

-- Users can read their own notifications
DROP POLICY IF EXISTS notifications_select_own ON public.notifications;
CREATE POLICY notifications_select_own ON public.notifications
  FOR SELECT USING (user_id = auth.uid());

-- Users can update their own notifications (mark read)
DROP POLICY IF EXISTS notifications_update_own ON public.notifications;
CREATE POLICY notifications_update_own ON public.notifications
  FOR UPDATE USING (user_id = auth.uid());

-- Service role can insert notifications for any user
DROP POLICY IF EXISTS notifications_insert_service ON public.notifications;
CREATE POLICY notifications_insert_service ON public.notifications
  FOR INSERT WITH CHECK (true);
