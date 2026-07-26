import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/auth";
import { getSupabaseServerClient } from "@/lib/supabase";
import { ALL_NAV_LINKS } from "@/lib/nav";

export const dynamic = "force-dynamic";

export interface SearchResult {
  id: string;
  type:
    | "nav"
    | "workspace"
    | "user"
    | "audit_log"
    | "connector"
    | "knowledge"
    | "notification";
  title: string;
  subtitle?: string;
  href?: string;
  icon?: string;
  rank?: number;
  metadata?: Record<string, any>;
}

const STATIC_NAV: SearchResult[] = ALL_NAV_LINKS.map((item) => ({
  id: `nav-${item.href}`,
  type: "nav",
  title: item.label,
  subtitle: `Navigation · ${item.section}`,
  href: item.href,
  icon: item.icon,
}));

function sanitizeQuery(q: string) {
  // Strip leading/trailing noise; remove characters that break tsquery
  return q
    .replace(/[^\w\s\-:\/]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function fallbackIlike(query: string) {
  return `%${query}%`;
}

export async function GET(req: NextRequest) {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ ok: false, error: "unauthorized" }, { status: 401 });
  }

  const userId = (session.user as any).id as string;
  const { searchParams } = new URL(req.url);
  const rawQuery = (searchParams.get("q") || "").trim();
  const limit = Math.min(50, Math.max(1, Number(searchParams.get("limit") || 20)));

  if (!rawQuery || rawQuery.length < 2) {
    return NextResponse.json({ ok: true, results: [], query: rawQuery });
  }

  const sb = getSupabaseServerClient();
  if (!sb) {
    return NextResponse.json({ ok: true, results: [], query: rawQuery });
  }

  try {
    const query = sanitizeQuery(rawQuery);
    const results: SearchResult[] = [];

    // ── Static navigation ────────────────────────────────────────────
    const qLower = rawQuery.toLowerCase();
    const navMatches = STATIC_NAV.filter(
      (item) =>
        item.title.toLowerCase().includes(qLower) ||
        (item.href && item.href.toLowerCase().includes(qLower))
    ).map((item) => ({ ...item, rank: 1 }));
    results.push(...navMatches);

    if (!query) {
      results.sort((a, b) => a.title.localeCompare(b.title));
      return NextResponse.json({
        ok: true,
        query: rawQuery,
        results: results.slice(0, limit),
      });
    }

    // ── FTS-backed dynamic search via RPCs ────────────────────────────
    const [
      { data: workspaces, error: wsError },
      { data: users, error: usersError },
      { data: connectors, error: connectorError },
      { data: audit, error: auditError },
      { data: notifications, error: notifError },
      { data: chunks, error: chunksError },
    ] = await Promise.all([
      sb.rpc("search_workspaces", { p_user_id: userId, p_query: query, p_limit: limit }),
      sb.rpc("search_users", { p_user_id: userId, p_query: query, p_limit: limit }),
      sb.rpc("search_connectors", { p_user_id: userId, p_query: query, p_limit: limit }),
      sb.rpc("search_audit_logs", { p_user_id: userId, p_query: query, p_limit: limit }),
      sb.rpc("search_notifications", { p_user_id: userId, p_query: query, p_limit: limit }),
      sb.rpc("search_kb_chunks_visible", { p_user_id: userId, p_query: query, p_limit: limit }),
    ]);

    if (wsError) throw wsError;
    if (usersError) throw usersError;
    if (connectorError) throw connectorError;
    if (auditError) throw auditError;
    if (notifError) throw notifError;
    if (chunksError) throw chunksError;

    // ── Workspaces ───────────────────────────────────────────────────
    for (const w of workspaces || []) {
      results.push({
        id: w.id,
        type: "workspace",
        title: w.name,
        subtitle: `Workspace · ${w.plan}`,
        href: `/os?workspace=${w.slug}`,
        icon: "🏢",
        rank: w.rank,
        metadata: { plan: w.plan, slug: w.slug },
      });
    }

    // ── Users ────────────────────────────────────────────────────────
    for (const u of users || []) {
      results.push({
        id: u.id,
        type: "user",
        title: u.name || u.email,
        subtitle: `User · ${u.email}`,
        href: `/admin?tab=users`,
        icon: "👤",
        rank: u.rank,
        metadata: { role: u.role, email: u.email },
      });
    }

    // ── Audit logs ─────────────────────────────────────────────────────
    for (const a of audit || []) {
      results.push({
        id: a.id,
        type: "audit_log",
        title: a.action,
        subtitle: `Audit · ${a.module || "system"} · ${new Date(a.timestamp).toLocaleString()}`,
        href: `/os/governance`,
        icon: "📋",
        rank: a.rank,
        metadata: { module: a.module, workspace_id: a.workspace_id },
      });
    }

    // ── Connectors ─────────────────────────────────────────────────────
    for (const c of connectors || []) {
      results.push({
        id: c.id,
        type: "connector",
        title: c.name,
        subtitle: `Integration · ${c.type} · ${c.enabled ? "Enabled" : "Disabled"}`,
        href: `/os/integrations`,
        icon: "🔗",
        rank: c.rank,
        metadata: { type: c.type, enabled: c.enabled },
      });
    }

    // ── Knowledge base chunks ──────────────────────────────────────────
    for (const c of chunks || []) {
      results.push({
        id: c.id,
        type: "knowledge",
        title: c.doc_id || "Knowledge Document",
        subtitle: `Knowledge · ${c.text.slice(0, 80)}${c.text.length > 80 ? "..." : ""}`,
        href: `/os/knowledge`,
        icon: "📚",
        rank: c.rank,
        metadata: { kb_id: c.kb_id, doc_id: c.doc_id },
      });
    }

    // ── Notifications ──────────────────────────────────────────────────
    for (const n of notifications || []) {
      results.push({
        id: n.id,
        type: "notification",
        title: n.title,
        subtitle: `Notification · ${n.type}`,
        href: n.link || "/os/notifications",
        icon: "🔔",
        rank: n.rank,
        metadata: { type: n.type, body: n.body },
      });
    }

    // ── Fallback ILIKE when FTS returns nothing ──────────────────────
    const hasDynamic =
      (workspaces?.length || 0) +
      (users?.length || 0) +
      (connectors?.length || 0) +
      (audit?.length || 0) +
      (notifications?.length || 0) +
      (chunks?.length || 0);

    if (hasDynamic === 0) {
      const like = fallbackIlike(rawQuery);

      const { data: memberRows } = await sb
        .from("memberships")
        .select("workspace_id")
        .eq("user_id", userId);
      const userWorkspaceIds = (memberRows || []).map((m: any) => m.workspace_id);

      const [{ data: wsFb }, { data: userFb }, { data: connFb }, { data: notifFb }] =
        await Promise.all([
          sb
            .from("workspaces")
            .select("id, slug, name, plan")
            .in("id", userWorkspaceIds.length > 0 ? userWorkspaceIds : [""])
            .ilike("name", like)
            .limit(limit),
          sb
            .from("users")
            .select("id, email, name, role")
            .neq("id", userId)
            .or(`name.ilike.${like},email.ilike.${like}`)
            .limit(limit),
          sb
            .from("connector_configs")
            .select("id, workspace_id, name, type, enabled")
            .in("workspace_id", userWorkspaceIds.length > 0 ? userWorkspaceIds : [""])
            .ilike("name", like)
            .limit(limit),
          sb
            .from("notifications")
            .select("id, type, title, body, link, created_at")
            .eq("user_id", userId)
            .or(`title.ilike.${like},body.ilike.${like}`)
            .limit(limit),
        ]);

      for (const w of wsFb || []) {
        results.push({
          id: w.id,
          type: "workspace",
          title: w.name,
          subtitle: `Workspace · ${w.plan}`,
          href: `/os?workspace=${w.slug}`,
          icon: "",
          rank: 0.01,
          metadata: { plan: w.plan, slug: w.slug },
        });
      }

      for (const u of userFb || []) {
        results.push({
          id: u.id,
          type: "user",
          title: u.name || u.email,
          subtitle: `User · ${u.email}`,
          href: `/admin?tab=users`,
          icon: "👤",
          rank: 0.01,
          metadata: { role: u.role, email: u.email },
        });
      }

      for (const c of connFb || []) {
        results.push({
          id: c.id,
          type: "connector",
          title: c.name,
          subtitle: `Integration · ${c.type} · ${c.enabled ? "Enabled" : "Disabled"}`,
          href: `/os/integrations`,
          icon: "🔗",
          rank: 0.01,
          metadata: { type: c.type, enabled: c.enabled },
        });
      }

      for (const n of notifFb || []) {
        results.push({
          id: n.id,
          type: "notification",
          title: n.title,
          subtitle: `Notification · ${n.type}`,
          href: n.link || "/os/notifications",
          icon: "🔔",
          rank: 0.01,
          metadata: { type: n.type, body: n.body },
        });
      }
    }

    // Sort by rank descending, then title ascending
    results.sort((a, b) => {
      const rankA = a.rank ?? 0;
      const rankB = b.rank ?? 0;
      if (rankB !== rankA) return rankB - rankA;
      return a.title.localeCompare(b.title);
    });

    return NextResponse.json({
      ok: true,
      query: rawQuery,
      results: results.slice(0, limit),
    });
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e?.message || String(e) }, { status: 500 });
  }
}
