-- AEON OS Phase: Global Search Full-Text Search
-- Run after 0005_notifications.sql.
-- Adds generated tsvector columns + GIN indexes and ranked RPCs.

-- ── Workspaces ───────────────────────────────────────────────────────────────
ALTER TABLE public.workspaces
  ADD COLUMN IF NOT EXISTS search_tsv tsvector
    GENERATED ALWAYS AS (to_tsvector('english',
      coalesce(name, '') || ' ' ||
      coalesce(slug, '') || ' ' ||
      coalesce(plan, ''))) STORED;

CREATE INDEX IF NOT EXISTS idx_workspaces_search_tsv
  ON public.workspaces USING GIN (search_tsv);

-- ── Users ────────────────────────────────────────────────────────────────────
ALTER TABLE public.users
  ADD COLUMN IF NOT EXISTS search_tsv tsvector
    GENERATED ALWAYS AS (to_tsvector('english',
      coalesce(name, '') || ' ' ||
      coalesce(email, '') || ' ' ||
      coalesce(role, ''))) STORED;

CREATE INDEX IF NOT EXISTS idx_users_search_tsv
  ON public.users USING GIN (search_tsv);

-- ── Connector configs ────────────────────────────────────────────────────────
ALTER TABLE public.connector_configs
  ADD COLUMN IF NOT EXISTS search_tsv tsvector
    GENERATED ALWAYS AS (to_tsvector('english',
      coalesce(name, '') || ' ' ||
      coalesce(type, ''))) STORED;

CREATE INDEX IF NOT EXISTS idx_connector_configs_search_tsv
  ON public.connector_configs USING GIN (search_tsv);

-- ── Audit logs ───────────────────────────────────────────────────────────────
ALTER TABLE public.audit_logs
  ADD COLUMN IF NOT EXISTS search_tsv tsvector
    GENERATED ALWAYS AS (to_tsvector('english',
      coalesce(action, '') || ' ' ||
      coalesce(module, '') || ' ' ||
      coalesce(metadata::text, ''))) STORED;

CREATE INDEX IF NOT EXISTS idx_audit_logs_search_tsv
  ON public.audit_logs USING GIN (search_tsv);

-- ── Notifications ────────────────────────────────────────────────────────────
ALTER TABLE public.notifications
  ADD COLUMN IF NOT EXISTS search_tsv tsvector
    GENERATED ALWAYS AS (to_tsvector('english',
      coalesce(title, '') || ' ' ||
      coalesce(body, '') || ' ' ||
      coalesce(type, ''))) STORED;

CREATE INDEX IF NOT EXISTS idx_notifications_search_tsv
  ON public.notifications USING GIN (search_tsv);

-- kb_chunks already has idx_kb_chunks_fts in 0002_vector_store.sql

-- ── Ranked search RPCs ───────────────────────────────────────────────────────

-- Search workspaces the user belongs to
CREATE OR REPLACE FUNCTION public.search_workspaces(
  p_user_id UUID,
  p_query TEXT,
  p_limit INT DEFAULT 20
)
RETURNS TABLE (
  id UUID,
  slug TEXT,
  name TEXT,
  plan TEXT,
  rank FLOAT
)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public
AS $$
  SELECT
    w.id,
    w.slug,
    w.name,
    w.plan,
    ts_rank(w.search_tsv, websearch_to_tsquery('english', p_query))::FLOAT AS rank
  FROM public.workspaces w
  JOIN public.memberships m ON m.workspace_id = w.id
  WHERE m.user_id = p_user_id
    AND w.search_tsv @@ websearch_to_tsquery('english', p_query)
  ORDER BY rank DESC
  LIMIT p_limit;
$$;

-- Search users in the same workspaces as the requesting user
CREATE OR REPLACE FUNCTION public.search_users(
  p_user_id UUID,
  p_query TEXT,
  p_limit INT DEFAULT 20
)
RETURNS TABLE (
  id UUID,
  email TEXT,
  name TEXT,
  role TEXT,
  rank FLOAT
)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public
AS $$
  SELECT
    u.id,
    u.email,
    u.name,
    u.role,
    ts_rank(u.search_tsv, websearch_to_tsquery('english', p_query))::FLOAT AS rank
  FROM public.users u
  JOIN public.memberships m ON m.user_id = u.id
  WHERE m.workspace_id IN (
    SELECT m2.workspace_id FROM public.memberships m2 WHERE m2.user_id = p_user_id
  )
    AND u.id != p_user_id
    AND u.search_tsv @@ websearch_to_tsquery('english', p_query)
  ORDER BY rank DESC
  LIMIT p_limit;
$$;

-- Search connector configs visible to the user
CREATE OR REPLACE FUNCTION public.search_connectors(
  p_user_id UUID,
  p_query TEXT,
  p_limit INT DEFAULT 20
)
RETURNS TABLE (
  id UUID,
  workspace_id UUID,
  name TEXT,
  type TEXT,
  enabled BOOLEAN,
  rank FLOAT
)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public
AS $$
  SELECT
    cc.id,
    cc.workspace_id,
    cc.name,
    cc.type,
    cc.enabled,
    ts_rank(cc.search_tsv, websearch_to_tsquery('english', p_query))::FLOAT AS rank
  FROM public.connector_configs cc
  WHERE cc.workspace_id IN (
    SELECT m.workspace_id FROM public.memberships m WHERE m.user_id = p_user_id
  )
    AND cc.search_tsv @@ websearch_to_tsquery('english', p_query)
  ORDER BY rank DESC
  LIMIT p_limit;
$$;

-- Search audit logs visible to the user
CREATE OR REPLACE FUNCTION public.search_audit_logs(
  p_user_id UUID,
  p_query TEXT,
  p_limit INT DEFAULT 20
)
RETURNS TABLE (
  id UUID,
  action TEXT,
  module TEXT,
  metadata JSONB,
  timestamp TIMESTAMPTZ,
  workspace_id UUID,
  rank FLOAT
)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public
AS $$
  SELECT
    al.id,
    al.action,
    al.module,
    al.metadata,
    al.timestamp,
    al.workspace_id,
    ts_rank(al.search_tsv, websearch_to_tsquery('english', p_query))::FLOAT AS rank
  FROM public.audit_logs al
  WHERE al.workspace_id IN (
    SELECT m.workspace_id FROM public.memberships m WHERE m.user_id = p_user_id
  )
    AND al.search_tsv @@ websearch_to_tsquery('english', p_query)
  ORDER BY rank DESC, al.timestamp DESC
  LIMIT p_limit;
$$;

-- Search notifications for the user
CREATE OR REPLACE FUNCTION public.search_notifications(
  p_user_id UUID,
  p_query TEXT,
  p_limit INT DEFAULT 20
)
RETURNS TABLE (
  id UUID,
  type TEXT,
  title TEXT,
  body TEXT,
  link TEXT,
  created_at TIMESTAMPTZ,
  rank FLOAT
)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public
AS $$
  SELECT
    n.id,
    n.type,
    n.title,
    n.body,
    n.link,
    n.created_at,
    ts_rank(n.search_tsv, websearch_to_tsquery('english', p_query))::FLOAT AS rank
  FROM public.notifications n
  WHERE n.user_id = p_user_id
    AND n.search_tsv @@ websearch_to_tsquery('english', p_query)
  ORDER BY rank DESC, n.created_at DESC
  LIMIT p_limit;
$$;

-- Search knowledge base chunks visible through workspace membership
CREATE OR REPLACE FUNCTION public.search_kb_chunks_visible(
  p_user_id UUID,
  p_query TEXT,
  p_limit INT DEFAULT 20
)
RETURNS TABLE (
  id UUID,
  kb_id TEXT,
  doc_id TEXT,
  text TEXT,
  rank FLOAT
)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public
AS $$
  SELECT
    kc.id,
    kc.kb_id,
    kc.doc_id,
    kc.text,
    ts_rank(to_tsvector('english', kc.text), websearch_to_tsquery('english', p_query))::FLOAT AS rank
  FROM public.kb_chunks kc
  WHERE kc.kb_id IN (
    SELECT w.slug::text
    FROM public.workspaces w
    JOIN public.memberships m ON m.workspace_id = w.id
    WHERE m.user_id = p_user_id
  )
    AND to_tsvector('english', kc.text) @@ websearch_to_tsquery('english', p_query)
  ORDER BY rank DESC
  LIMIT p_limit;
$$;

-- Grants
GRANT EXECUTE ON FUNCTION public.search_workspaces(UUID, TEXT, INT) TO authenticated;
GRANT EXECUTE ON FUNCTION public.search_users(UUID, TEXT, INT) TO authenticated;
GRANT EXECUTE ON FUNCTION public.search_connectors(UUID, TEXT, INT) TO authenticated;
GRANT EXECUTE ON FUNCTION public.search_audit_logs(UUID, TEXT, INT) TO authenticated;
GRANT EXECUTE ON FUNCTION public.search_notifications(UUID, TEXT, INT) TO authenticated;
GRANT EXECUTE ON FUNCTION public.search_kb_chunks_visible(UUID, TEXT, INT) TO authenticated;
