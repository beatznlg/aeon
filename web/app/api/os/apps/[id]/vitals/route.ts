import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

/**
 * Vercel-compatible mock vitals for an AEON OS app.
 * Returns deterministic, realistic data without spawning Python.
 */
export async function GET(
  _req: Request,
  { params }: { params: { id: string } },
) {
  const id = params.id;
  const now = Date.now();
  const seed = id.split("").reduce((s, c) => s + c.charCodeAt(0), 0);

  return NextResponse.json({
    ok: true,
    app_id: id,
    vitals: {
      uptime_s: Math.floor(3600 + (now % 86400)),
      memory_mb: 256 + (seed % 128),
      cpu_pct: 5 + (seed % 35),
      active_workers: 2 + (seed % 4),
    },
    ledger_balance: 0.0125 + (seed % 100) / 10000,
    open_goals: [
      { title: "Monitor operational health", priority: 10 },
      { title: "Surface actionable alerts", priority: 8 },
      { title: "Optimize resource allocation", priority: 6 },
    ],
    tool_count: 6 + (seed % 10),
    ts: now,
  });
}
