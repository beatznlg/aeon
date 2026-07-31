import { NextResponse } from "next/server";
import { pythonUrl } from "@/lib/kernel";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const days = Math.min(365, Math.max(1, Number(searchParams.get("days") || 30)));

  const url = pythonUrl();
  if (!url) {
    return NextResponse.json({
      ok: true,
      metrics: { period_days: days, total_events: 0, by_day: {} },
    });
  }

  try {
    const res = await fetch(`${url}/metrics?days=${days}`, { cache: "no-store" });
    const data = await res.json();
    return NextResponse.json(data);
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e?.message || String(e) }, { status: 503 });
  }
}
