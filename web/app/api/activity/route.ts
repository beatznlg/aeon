import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/auth";
import { getSupabaseServerClient } from "@/lib/supabase";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ ok: false, error: "unauthorized" }, { status: 401 });
  }

  const userId = (session.user as any).id as string;
  const { searchParams } = new URL(req.url);
  const limit = Math.min(100, Math.max(1, Number(searchParams.get("limit") || 50)));
  const offset = Math.max(0, Number(searchParams.get("offset") || 0));

  const sb = getSupabaseServerClient();
  if (!sb) {
    return NextResponse.json({ ok: true, events: [] });
  }

  try {
    const { data, error, count } = await sb
      .from("activity_events")
      .select("*", { count: "exact" })
      .or(`user_id.eq.${userId},workspace_id.in.(SELECT workspace_id FROM memberships WHERE user_id = '${userId}')`)
      .order("created_at", { ascending: false })
      .range(offset, offset + limit - 1);

    if (error) throw error;

    return NextResponse.json({
      ok: true,
      events: data || [],
      count: count || 0,
    });
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e?.message || String(e) }, { status: 500 });
  }
}
