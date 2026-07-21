import { NextResponse } from "next/server";
import { pythonUrl } from "@/lib/kernel";

export const dynamic = "force-dynamic";

export async function GET() {
  const url = pythonUrl();
  if (!url) {
    return NextResponse.json({
      ok: true,
      timestamp: Date.now(),
      kernel: { status: "ok", backend: "ts_stub" },
      agents: [],
      queue: { size: 0, status: "healthy" },
      integrations: [],
      storage: { usage_events_bytes: 0, usage_events_mb: 0 },
    });
  }

  try {
    const res = await fetch(`${url}/health/detailed`, { cache: "no-store" });
    const data = await res.json();
    return NextResponse.json(data);
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e?.message || String(e) }, { status: 503 });
  }
}
