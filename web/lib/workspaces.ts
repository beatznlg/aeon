import { getSupabaseServerClient } from "@/lib/supabase";

export interface Workspace {
  id: string;
  slug: string;
  name: string;
  plan: "free" | "team" | "enterprise";
  created_at: string;
}

export interface Membership {
  id: string;
  workspace_id: string;
  user_id: string;
  role: "ADMIN" | "OPERATOR" | "VIEWER";
  created_at: string;
}

export async function getWorkspacesForUser(userId: string): Promise<Workspace[]> {
  const sb = getSupabaseServerClient();
  if (!sb) return [];

  const { data, error } = await sb
    .from("memberships")
    .select("workspace_id, role")
    .eq("user_id", userId);

  if (error || !data?.length) return [];

  const ids = data.map((m: any) => m.workspace_id);
  const { data: workspaces, error: wsError } = await sb
    .from("workspaces")
    .select("id, slug, name, plan, created_at")
    .in("id", ids);

  if (wsError || !workspaces) return [];
  return workspaces as Workspace[];
}

export async function getDefaultWorkspace(userId: string): Promise<Workspace | null> {
  const workspaces = await getWorkspacesForUser(userId);
  return workspaces[0] || null;
}

export async function createWorkspace(
  ownerId: string,
  name: string,
  slug: string,
): Promise<Workspace | null> {
  const sb = getSupabaseServerClient();
  if (!sb) return null;

  const { data: ws, error } = await sb
    .from("workspaces")
    .insert({ name, slug, plan: "free" })
    .select("id, slug, name, plan, created_at")
    .single();

  if (error || !ws) return null;

  await sb.from("memberships").insert({
    workspace_id: ws.id,
    user_id: ownerId,
    role: "ADMIN",
  });

  return ws as Workspace;
}
