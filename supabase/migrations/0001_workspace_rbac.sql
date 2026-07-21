-- AEON OS Phase 3: Enterprise Identity & Data Connectors
-- Tables: workspaces, memberships, connector_configs
-- Run this in Supabase SQL Editor after 0000_users_and_audit.sql.

-- Multi-tenant workspaces
CREATE TABLE IF NOT EXISTS public.workspaces (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  plan TEXT NOT NULL DEFAULT 'free' CHECK (plan IN ('free', 'team', 'enterprise')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- User-to-workspace memberships with RBAC role
CREATE TABLE IF NOT EXISTS public.memberships (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('ADMIN', 'OPERATOR', 'VIEWER')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (workspace_id, user_id)
);

-- Enterprise connector configuration per workspace
CREATE TABLE IF NOT EXISTS public.connector_configs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  type TEXT NOT NULL CHECK (type IN ('mock', 'http', 'postgres', 'snowflake', 'sharepoint')),
  enabled BOOLEAN NOT NULL DEFAULT false,
  secrets JSONB NOT NULL DEFAULT '{}'::jsonb,
  options JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- RLS policies
ALTER TABLE public.workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.connector_configs ENABLE ROW LEVEL SECURITY;

-- Idempotent policy creation: drop then recreate so reruns are safe
DROP POLICY IF EXISTS workspace_members_select ON public.workspaces;
CREATE POLICY workspace_members_select ON public.workspaces
  FOR SELECT USING (
    EXISTS (SELECT 1 FROM public.memberships m WHERE m.workspace_id = id AND m.user_id = auth.uid())
  );

DROP POLICY IF EXISTS membership_select ON public.memberships;
CREATE POLICY membership_select ON public.memberships
  FOR SELECT USING (user_id = auth.uid());

DROP POLICY IF EXISTS connector_config_select ON public.connector_configs;
CREATE POLICY connector_config_select ON public.connector_configs
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM public.memberships m
      WHERE m.workspace_id = connector_configs.workspace_id
        AND m.user_id = auth.uid()
    )
  );
