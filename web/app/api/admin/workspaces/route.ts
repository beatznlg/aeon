import { NextResponse } from "next/server";
import { auth } from "@/auth";
import { requireRole } from "@/lib/auth";
import { getSupabaseServerClient } from "@/lib/supabase";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const session = await auth();
    requireRole(session, ["ADMIN"]);
  } catch {
    return NextResponse.json({ ok: false, error: "forbidden" }, { status: 403 });
  }

  const sb = getSupabaseServerClient();
  if (!sb) {
    return NextResponse.json({ ok: false, error: "Supabase not configured" }, { status: 503 });
  }

  try {
    const { data: workspaces, error } = await sb
      .from("workspaces")
      .select("id, slug, name, plan, created_at, tenant_id")
      .order("created_at", { ascending: false })
      .limit(100);

    if (error) throw error;

    // Get member counts per workspace
    const workspaceIds = (workspaces || []).map((w) => w.id);
    let memberships: any[] = [];
    if (workspaceIds.length > 0) {
      const { data: m } = await sb
        .from("memberships")
        .select("workspace_id")
        .in("workspace_id", workspaceIds);
      memberships = m || [];
    }

    const countMap = new Map<string, number>();
    for (const m of memberships) {
      countMap.set(m.workspace_id, (countMap.get(m.workspace_id) || 0) + 1);
    }

    const enriched = (workspaces || []).map((w) => ({
      ...w,
      member_count: countMap.get(w.id) || 0,
    }));

    return NextResponse.json({ ok: true, workspaces: enriched });
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e?.message || String(e) }, { status: 500 });
  }
}
