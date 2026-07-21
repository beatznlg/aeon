-- AEON OS Phase 3 Seed
-- Creates the first admin user, a default workspace, and assigns admin membership.
-- Run this in Supabase SQL Editor after applying 0001_workspace_rbac.sql.

-- Ensure the user exists (insert-or-ignore style via ON CONFLICT)
INSERT INTO public.users (id, email, name, password, role, created_at)
VALUES (
  gen_random_uuid(),
  'beatznlg@gmail.com',
  'Admin User',
  '$2b$10$n79MZxoeDA5.LA/yuCls9uRW79bqhbvhMAk02QQgyS78QoGywTmSK',
  'ADMIN',
  now()
)
ON CONFLICT (email) DO UPDATE SET
  password = EXCLUDED.password,
  role = EXCLUDED.role,
  name = EXCLUDED.name;

-- Default workspace
INSERT INTO public.workspaces (id, slug, name, plan, created_at)
VALUES (
  '00000000-0000-0000-0000-000000000000',
  'default',
  'Default Workspace',
  'enterprise',
  now()
)
ON CONFLICT (slug) DO NOTHING;

-- Membership linking the admin to the default workspace
INSERT INTO public.memberships (workspace_id, user_id, role, created_at)
SELECT
  w.id,
  u.id,
  'ADMIN',
  now()
FROM public.workspaces w, public.users u
WHERE w.slug = 'default'
  AND u.email = 'beatznlg@gmail.com'
ON CONFLICT (workspace_id, user_id) DO UPDATE SET
  role = EXCLUDED.role;
