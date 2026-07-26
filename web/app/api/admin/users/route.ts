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
    const { data: users, error } = await sb
      .from("users")
      .select("id, email, name, role, created_at, tenant_id")
      .order("created_at", { ascending: false })
      .limit(200);

    if (error) throw error;

    // Get membership info for each user
    const userIds = (users || []).map((u) => u.id);
    let memberships: any[] = [];
    if (userIds.length > 0) {
      const { data: m } = await sb
        .from("memberships")
        .select("user_id, workspace_id, role")
        .in("user_id", userIds);
      memberships = m || [];
    }

    const membershipMap = new Map<string, { workspace_id: string; role: string }[]>();
    for (const m of memberships) {
      const list = membershipMap.get(m.user_id) || [];
      list.push({ workspace_id: m.workspace_id, role: m.role });
      membershipMap.set(m.user_id, list);
    }

    const enriched = (users || []).map((u) => ({
      ...u,
      memberships: membershipMap.get(u.id) || [],
      member_count: membershipMap.get(u.id)?.length || 0,
    }));

    return NextResponse.json({ ok: true, users: enriched });
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e?.message || String(e) }, { status: 500 });
  }
}
