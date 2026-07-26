import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/auth";
import { getSupabaseServerClient } from "@/lib/supabase";
import { broadcastEvent } from "@/lib/events";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ ok: false, error: "unauthorized" }, { status: 401 });
  }
  const userId = (session.user as any).id;
  const { searchParams } = new URL(req.url);
  const limit = Math.min(100, Math.max(1, Number(searchParams.get("limit") || 20)));
  const offset = Math.max(0, Number(searchParams.get("offset") || 0));
  const unreadOnly = searchParams.get("unread") === "true";

  const sb = getSupabaseServerClient();
  if (!sb) {
    return NextResponse.json({ ok: true, notifications: [], count: 0 });
  }

  try {
    let query = sb
      .from("notifications")
      .select("*", { count: "exact" })
      .eq("user_id", userId)
      .order("created_at", { ascending: false })
      .range(offset, offset + limit - 1);

    if (unreadOnly) {
      query = query.eq("read", false);
    }

    const { data, error, count } = await query;
    if (error) throw error;

    // Get unread count
    const { count: unreadCount } = await sb
      .from("notifications")
      .select("*", { count: "exact", head: true })
      .eq("user_id", userId)
      .eq("read", false);

    return NextResponse.json({
      ok: true,
      notifications: data || [],
      count: count || 0,
      unread_count: unreadCount || 0,
    });
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e?.message || String(e) }, { status: 500 });
  }
}

export async function POST(req: NextRequest) {
  const session = await auth();
  // Only admins or the app itself should create notifications
  // For simplicity, allow any authenticated user to create their own
  if (!session?.user) {
    return NextResponse.json({ ok: false, error: "unauthorized" }, { status: 401 });
  }
  const userId = (session.user as any).id;

  const sb = getSupabaseServerClient();
  if (!sb) {
    return NextResponse.json({ ok: false, error: "Supabase not configured" }, { status: 503 });
  }

  try {
    const body = await req.json();
    const { type, title, body: notifBody, icon, link, workspace_id } = body;

    if (!type || !title) {
      return NextResponse.json({ ok: false, error: "type and title required" }, { status: 400 });
    }

    const { data, error } = await sb
      .from("notifications")
      .insert({
        user_id: body.user_id || userId,
        workspace_id: workspace_id || null,
        type,
        title,
        body: notifBody || null,
        icon: icon || "🔔",
        link: link || null,
        metadata: body.metadata || {},
      })
      .select()
      .single();

    if (error) throw error;

    // Push to any connected SSE clients for this user
    broadcastEvent({
      type: "notification",
      payload: data,
      user_id: data.user_id,
      workspace_id: data.workspace_id,
      timestamp: new Date().toISOString(),
    });

    return NextResponse.json({ ok: true, notification: data });
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e?.message || String(e) }, { status: 500 });
  }
}

export async function PATCH(req: NextRequest) {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ ok: false, error: "unauthorized" }, { status: 401 });
  }
  const userId = (session.user as any).id;

  const sb = getSupabaseServerClient();
  if (!sb) {
    return NextResponse.json({ ok: false, error: "Supabase not configured" }, { status: 503 });
  }

  try {
    const body = await req.json();
    const { id, read_all } = body;

    if (read_all) {
      const { error } = await sb
        .from("notifications")
        .update({ read: true })
        .eq("user_id", userId)
        .eq("read", false);
      if (error) throw error;

      broadcastEvent({
        type: "notification_read",
        payload: { read_all: true },
        user_id: userId,
        timestamp: new Date().toISOString(),
      });

      return NextResponse.json({ ok: true, message: "All notifications marked read" });
    }

    if (!id) {
      return NextResponse.json({ ok: false, error: "id or read_all required" }, { status: 400 });
    }

    const { data: updated, error } = await sb
      .from("notifications")
      .update({ read: true })
      .eq("id", id)
      .eq("user_id", userId)
      .select()
      .single();

    if (error) throw error;

    if (updated) {
      broadcastEvent({
        type: "notification_read",
        payload: updated,
        user_id: userId,
        workspace_id: updated.workspace_id,
        timestamp: new Date().toISOString(),
      });
    }

    return NextResponse.json({ ok: true });
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e?.message || String(e) }, { status: 500 });
  }
}
