import { NextResponse } from "next/server";
import { auth } from "@/auth";
import { requireRole } from "@/lib/auth";
import { getSupabaseServerClient } from "@/lib/supabase";
import { pythonUrl } from "@/lib/kernel";
import { demoAdminStats } from "@/lib/demo-data";

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
    // Supabase not configured — serve demo stats so the admin page renders.
    return NextResponse.json(demoAdminStats);
  }

  try {
    // Gather system stats
    const { count: userCount } = await sb.from("users").select("*", { count: "exact", head: true });
    const { count: workspaceCount } = await sb
      .from("workspaces")
      .select("*", { count: "exact", head: true });
    const { count: membershipCount } = await sb
      .from("memberships")
      .select("*", { count: "exact", head: true });

    // Role distribution
    const { data: roleDist } = await sb.from("users").select("role");

    let admins = 0,
      operators = 0,
      viewers = 0;
    for (const u of roleDist || []) {
      if (u.role === "ADMIN") admins++;
      else if (u.role === "OPERATOR") operators++;
      else viewers++;
    }

    // Plan distribution
    const { data: planDist } = await sb.from("workspaces").select("plan");
    let free = 0,
      team = 0,
      enterprise = 0;
    for (const w of planDist || []) {
      if (w.plan === "free") free++;
      else if (w.plan === "team") team++;
      else if (w.plan === "enterprise") enterprise++;
    }

    // Try to get audit log count from the Python backend
    let recentAudits = 0;
    const url = pythonUrl();
    if (url) {
      try {
        const res = await fetch(`${url}/governance/audit?limit=1`, { cache: "no-store" });
        const data = await res.json();
        recentAudits = data.count || 0;
      } catch {
        /* stats are best-effort */
      }
    }

    return NextResponse.json({
      ok: true,
      stats: {
        total_users: userCount ?? 0,
        total_workspaces: workspaceCount ?? 0,
        total_memberships: membershipCount ?? 0,
        role_distribution: { ADMIN: admins, OPERATOR: operators, VIEWER: viewers },
        plan_distribution: { free, team, enterprise },
        total_audit_entries: recentAudits,
      },
    });
  } catch (e: any) {
    // Supabase unreachable — serve demo stats so the admin page renders.
    return NextResponse.json(demoAdminStats);
  }
}
