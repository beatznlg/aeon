-- AEON OS Phase 3 Seed
-- Creates the first admin user, a default workspace, and assigns admin membership.
-- Run this in Supabase SQL Editor after applying 0001_workspace_rbac.sql.
--
-- ⚠️  DEVELOPMENT ONLY: The password below is intentionally weak and documented.
--    Default login: beatznlg@gmail.com / AeonDevAdmin2024!
--    Change it immediately in production or use the /auth/login password reset flow.

-- Ensure the user exists (insert-or-ignore style via ON CONFLICT)
INSERT INTO public.users (id, email, name, password, role, created_at)
VALUES (
  gen_random_uuid(),
  'beatznlg@gmail.com',
  'Admin User',
  'pbkdf2:sha256:1000000$7VbM7rUtm23OJaVs$1ee921d1fce63129eb43f5cf3b1b36e41b58bdf6949adef75ecd63582d1f7243',
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
