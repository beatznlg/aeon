import { NextResponse } from "next/server";
import { auth } from "@/auth";
import { pythonUrl } from "@/lib/kernel";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const session = await auth();
  const { searchParams } = new URL(req.url);
  const workspaceId = searchParams.get("workspace_id") || ((session?.user as any)?.workspaceId as string) || "default";
  const days = Math.min(365, Math.max(1, Number(searchParams.get("days") || 30)));

  const url = pythonUrl();
  if (!url) {
    return NextResponse.json({ ok: true, summary: { period_days: days, workspace_id: workspaceId, total_events: 0, total_quantity: 0, total_cost: 0, by_action: {}, by_module: {}, by_day: {} } });
  }

  try {
    const res = await fetch(`${url}/usage/summary?workspace_id=${encodeURIComponent(workspaceId)}&days=${days}`, {
      cache: "no-store",
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e?.message || String(e) }, { status: 503 });
  }
}
