-- AEON OS Baseline: users + audit_logs
-- Run this first in a fresh Supabase project, before 0001_workspace_rbac.sql.

-- User accounts used by NextAuth credentials provider
CREATE TABLE IF NOT EXISTS public.users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  name TEXT,
  password TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'VIEWER' CHECK (role IN ('ADMIN', 'OPERATOR', 'VIEWER')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Audit trail for chat, tick, dashboard and live module requests
CREATE TABLE IF NOT EXISTS public.audit_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
  email TEXT,
  action TEXT NOT NULL,
  module TEXT,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  timestamp TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Row Level Security
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;

-- Idempotent policy creation
DROP POLICY IF EXISTS users_select_own ON public.users;
CREATE POLICY users_select_own ON public.users
  FOR SELECT USING (auth.uid() = id);

DROP POLICY IF EXISTS audit_logs_select_own ON public.audit_logs;
CREATE POLICY audit_logs_select_own ON public.audit_logs
  FOR SELECT USING (auth.uid() = user_id);
