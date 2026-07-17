import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key =
    process.env.SUPABASE_SERVICE_ROLE_KEY ??
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key) {
    return NextResponse.json({ ok: false, error: "supabase env not set", rows: [] });
  }
  const sp = createClient(url, key, { auth: { persistSession: false } });
  const { searchParams } = new URL(req.url);
  const limit = Math.min(50, Math.max(1, Number(searchParams.get("limit") || 20)));
  const beforeId = Math.max(0, Number(searchParams.get("before_id") || 0));

  let q = sp
    .from("episodes")
    .select("id,ts,kind,text,ref")
    .order("id", { ascending: false })
    .limit(limit);
  if (beforeId > 0) q = q.lt("id", beforeId);

  const { data, error } = await q;
  if (error) {
    return NextResponse.json({ ok: false, error: error.message, rows: [] });
  }
  return NextResponse.json({ ok: true, rows: data || [] });
}
