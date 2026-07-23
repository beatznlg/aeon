-- AEON OS Phase 8: Audit, Compliance & Governance
-- Run after 0002_vector_store.sql.

-- Enhance audit_logs with workspace, PII, archival, and review status
ALTER TABLE public.audit_logs
  ADD COLUMN IF NOT EXISTS workspace_id UUID REFERENCES public.workspaces(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS pii_redacted BOOLEAN NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS review_status TEXT NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending', 'approved', 'rejected')),
  ADD COLUMN IF NOT EXISTS reviewer_id UUID REFERENCES public.users(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_audit_logs_workspace ON public.audit_logs (workspace_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON public.audit_logs (action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_module ON public.audit_logs (module);
CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON public.audit_logs (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_review ON public.audit_logs (review_status);

-- Retention policies per workspace
CREATE TABLE IF NOT EXISTS public.retention_policies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
  table_name TEXT NOT NULL DEFAULT 'audit_logs',
  retention_days INTEGER NOT NULL DEFAULT 365,
  action TEXT NOT NULL DEFAULT 'archive' CHECK (action IN ('delete', 'archive')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (workspace_id, table_name)
);

-- Consent logs for privacy compliance
CREATE TABLE IF NOT EXISTS public.consent_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  workspace_id UUID REFERENCES public.workspaces(id) ON DELETE SET NULL,
  consent_type TEXT NOT NULL CHECK (consent_type IN ('terms_of_service', 'privacy_policy', 'data_processing', 'marketing')),
  granted BOOLEAN NOT NULL DEFAULT true,
  timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE (user_id, consent_type)
);

-- Compliance check results
CREATE TABLE IF NOT EXISTS public.compliance_checks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID REFERENCES public.workspaces(id) ON DELETE CASCADE,
  check_type TEXT NOT NULL CHECK (check_type IN ('pii_scan', 'retention_run', 'consent_audit', 'role_review')),
  status TEXT NOT NULL CHECK (status IN ('success', 'warning', 'failed')),
  findings JSONB NOT NULL DEFAULT '{}'::jsonb,
  run_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- RLS policies
ALTER TABLE public.retention_policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.consent_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.compliance_checks ENABLE ROW LEVEL SECURITY;

-- Refresh audit_logs RLS to allow workspace admins
DROP POLICY IF EXISTS audit_logs_select_own ON public.audit_logs;
CREATE POLICY audit_logs_select_own ON public.audit_logs
  FOR SELECT USING (
    user_id = auth.uid()
    OR EXISTS (
      SELECT 1 FROM public.memberships m
      WHERE m.workspace_id = audit_logs.workspace_id
        AND m.user_id = auth.uid()
        AND m.role IN ('ADMIN', 'OPERATOR')
    )
  );

DROP POLICY IF EXISTS retention_policy_select ON public.retention_policies;
CREATE POLICY retention_policy_select ON public.retention_policies
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM public.memberships m
      WHERE m.workspace_id = retention_policies.workspace_id AND m.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS consent_logs_select ON public.consent_logs;
CREATE POLICY consent_logs_select ON public.consent_logs
  FOR SELECT USING (
    user_id = auth.uid()
    OR EXISTS (
      SELECT 1 FROM public.memberships m
      WHERE m.workspace_id = consent_logs.workspace_id AND m.user_id = auth.uid() AND m.role IN ('ADMIN', 'OPERATOR')
    )
  );

DROP POLICY IF EXISTS compliance_checks_select ON public.compliance_checks;
CREATE POLICY compliance_checks_select ON public.compliance_checks
  FOR SELECT USING (
    workspace_id IS NULL
    OR EXISTS (
      SELECT 1 FROM public.memberships m
      WHERE m.workspace_id = compliance_checks.workspace_id AND m.user_id = auth.uid()
    )
  );
