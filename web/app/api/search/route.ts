import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/auth";
import { getSupabaseServerClient } from "@/lib/supabase";

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
  metadata?: Record<string, any>;
}

export async function GET(req: NextRequest) {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ ok: false, error: "unauthorized" }, { status: 401 });
  }

  const userId = (session.user as any).id as string;
  const { searchParams } = new URL(req.url);
  const query = (searchParams.get("q") || "").trim().toLowerCase();
  const limit = Math.min(50, Math.max(1, Number(searchParams.get("limit") || 20)));

  if (!query || query.length < 2) {
    return NextResponse.json({ ok: true, results: [], query });
  }

  const sb = getSupabaseServerClient();
  if (!sb) {
    return NextResponse.json({ ok: true, results: [], query });
  }

  try {
    // Get all workspace IDs where the user is a member
    const { data: memberships, error: membershipError } = await sb
      .from("memberships")
      .select("workspace_id, role")
      .eq("user_id", userId);

    if (membershipError) throw membershipError;

    const workspaceIds = (memberships || []).map((m: any) => m.workspace_id);
    const isAdmin = (session.user as any).role === "ADMIN";

    const results: SearchResult[] = [];

    // ── Workspaces ─────────────────────────────────────────────────
    if (workspaceIds.length > 0) {
      const { data: workspaces, error: wsError } = await sb
        .from("workspaces")
        .select("id, slug, name, plan, created_at")
        .in("id", workspaceIds)
        .ilike("name", `%${query}%`)
        .limit(limit);

      if (!wsError && workspaces) {
        for (const w of workspaces) {
          results.push({
            id: w.id,
            type: "workspace",
            title: w.name,
            subtitle: `Workspace · ${w.plan}`,
            href: `/os?workspace=${w.slug}`,
            icon: "🏢",
            metadata: { plan: w.plan, slug: w.slug },
          });
        }
      }
    }

    // ── Users in shared workspaces ───────────────────────────────────
    if (workspaceIds.length > 0) {
      const { data: members, error: membersError } = await sb
        .from("memberships")
        .select("workspace_id, user_id, role")
        .in("workspace_id", workspaceIds)
        .neq("user_id", userId);

      if (!membersError && members) {
        const userIds = Array.from(new Set(members.map((m: any) => m.user_id)));
        const { data: users, error: usersError } = await sb
          .from("users")
          .select("id, email, name, role, created_at")
          .in("id", userIds)
          .or(`name.ilike.%${query}%,email.ilike.%${query}%`)
          .limit(limit);

        if (!usersError && users) {
          for (const u of users) {
            results.push({
              id: u.id,
              type: "user",
              title: u.name || u.email,
              subtitle: `User · ${u.email}`,
              href: `/admin?tab=users`,
              icon: "👤",
              metadata: { role: u.role, email: u.email },
            });
          }
        }
      }
    }

    // ── Audit logs (workspace admins/operators only) ───────────────
    if (workspaceIds.length > 0) {
      const { data: audit, error: auditError } = await sb
        .from("audit_logs")
        .select("id, action, module, metadata, timestamp, workspace_id")
        .in("workspace_id", workspaceIds)
        .or(`action.ilike.%${query}%,module.ilike.%${query}%`)
        .order("timestamp", { ascending: false })
        .limit(limit);

      if (!auditError && audit) {
        for (const a of audit) {
          results.push({
            id: a.id,
            type: "audit_log",
            title: `${a.action}`,
            subtitle: `Audit · ${a.module || "system"} · ${new Date(a.timestamp).toLocaleString()}`,
            href: `/os/governance`,
            icon: "📋",
            metadata: { module: a.module, workspace_id: a.workspace_id },
          });
        }
      }
    }

    // ── Connector configs (integrations) ───────────────────────────
    if (workspaceIds.length > 0) {
      const { data: connectors, error: connectorError } = await sb
        .from("connector_configs")
        .select("id, workspace_id, name, type, enabled")
        .in("workspace_id", workspaceIds)
        .ilike("name", `%${query}%`)
        .limit(limit);

      if (!connectorError && connectors) {
        for (const c of connectors) {
          results.push({
            id: c.id,
            type: "connector",
            title: c.name,
            subtitle: `Integration · ${c.type} · ${c.enabled ? "Enabled" : "Disabled"}`,
            href: `/os/integrations`,
            icon: "🔗",
            metadata: { type: c.type, enabled: c.enabled },
          });
        }
      }
    }

    // ── Knowledge base chunks ────────────────────────────────────────
    if (workspaceIds.length > 0) {
      const { data: chunks, error: chunksError } = await sb
        .from("kb_chunks")
        .select("id, kb_id, doc_id, text")
        .in(
          "kb_id",
          workspaceIds.map((id) => String(id))
        )
        .ilike("text", `%${query}%`)
        .limit(limit);

      if (!chunksError && chunks) {
        for (const c of chunks) {
          results.push({
            id: c.id,
            type: "knowledge",
            title: c.doc_id || "Knowledge Document",
            subtitle: `Knowledge · ${c.text.slice(0, 80)}${c.text.length > 80 ? "..." : ""}`,
            href: `/os/knowledge`,
            icon: "📚",
            metadata: { kb_id: c.kb_id, doc_id: c.doc_id },
          });
        }
      }
    }

    // ── Notifications ────────────────────────────────────────────────
    const { data: notifications, error: notifError } = await sb
      .from("notifications")
      .select("id, type, title, body, link, created_at")
      .eq("user_id", userId)
      .or(`title.ilike.%${query}%,body.ilike.%${query}%`)
      .order("created_at", { ascending: false })
      .limit(limit);

    if (!notifError && notifications) {
      for (const n of notifications) {
        results.push({
          id: n.id,
          type: "notification",
          title: n.title,
          subtitle: `Notification · ${n.type}`,
          href: n.link || "/os/notifications",
          icon: "🔔",
          metadata: { type: n.type, body: n.body },
        });
      }
    }

    // Simple relevance sort: title starts with query first, then includes
    results.sort((a, b) => {
      const aTitle = a.title.toLowerCase();
      const bTitle = b.title.toLowerCase();
      const aStarts = aTitle.startsWith(query) ? 0 : 1;
      const bStarts = bTitle.startsWith(query) ? 0 : 1;
      if (aStarts !== bStarts) return aStarts - bStarts;
      return aTitle.localeCompare(bTitle);
    });

    return NextResponse.json({
      ok: true,
      query,
      results: results.slice(0, limit),
    });
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e?.message || String(e) }, { status: 500 });
  }
}
