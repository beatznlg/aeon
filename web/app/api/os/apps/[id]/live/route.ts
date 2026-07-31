import { NextResponse } from "next/server";
import { auth } from "@/auth";
import { logAudit } from "@/lib/audit";
import { logUsage } from "@/lib/usage";

export const dynamic = "force-dynamic";
export const revalidate = 0;

/**
 * Deterministic time-varying mock data for live monitoring.
 * Values change every call based on a hash of the current timestamp,
 * simulating a live Python backend on Railway.
 */
function timeVaryingValue(seed: number, min: number, max: number): number {
  const h = (seed * 9301 + 49297) % 233280;
  const r = h / 233280;
  return Math.round((min + r * (max - min)) * 100) / 100;
}

function timeVaryingString(seed: number, options: string[]): string {
  return options[Math.abs(seed) % options.length];
}

const STATUS_OPTIONS = [
  "healthy",
  "healthy",
  "healthy",
  "warning",
  "healthy",
  "healthy",
  "critical",
  "healthy",
];

export async function GET(req: Request, { params }: { params: { id: string } }) {
  const id = params.id;
  const session = await auth();
  const userId = (session?.user as any)?.id;
  const workspaceId = (session?.user as any)?.workspaceId;
  const now = Date.now();
  // Change values every 3 seconds so the dashboard looks alive
  const tick = Math.floor(now / 3000);
  const seed = tick * 31 + id.length * 7;

  // ── System-wide metrics (always present) ────────────────────────
  const live = {
    ok: true,
    ts: now,
    app_id: id,
    system: {
      uptime_s: timeVaryingValue(seed, 120, 99999),
      requests_per_min: timeVaryingValue(seed + 1, 12, 89),
      avg_response_ms: timeVaryingValue(seed + 2, 45, 320),
      memory_mb: timeVaryingValue(seed + 3, 128, 768),
      cpu_pct: timeVaryingValue(seed + 4, 5, 95),
      active_goals: Math.floor(timeVaryingValue(seed + 5, 1, 8)),
      tool_success_rate: timeVaryingValue(seed + 6, 0.72, 0.99),
      status: timeVaryingString(seed + 7, STATUS_OPTIONS),
    },
    // ── App-specific live metrics ──────────────────────────────────
    metrics: getAppMetrics(id, seed),
  };

  logAudit({
    userId,
    email: session?.user?.email ?? undefined,
    action: "LIVE",
    module: id,
    metadata: { endpoint: req.url },
  });

  logUsage({
    userId,
    workspaceId,
    action: "live_sync",
    module: id,
    quantity: 1,
  });

  return NextResponse.json(live, {
    headers: {
      "Cache-Control": "no-cache, no-store, must-revalidate",
      Pragma: "no-cache",
      Expires: "0",
    },
  });
}

function getAppMetrics(appId: string, seed: number): Record<string, number | string>[] {
  const generate = (count: number, labelKey: string, labels: string[]) =>
    Array.from({ length: count }, (_, i) => ({
      label: labels[i % labels.length],
      value: timeVaryingValue(seed + i * 10, 10, 100),
      prev: timeVaryingValue(seed + i * 10 + 5, 10, 100),
      unit: "%",
      status: timeVaryingString(seed + i * 10 + 3, [
        "ok",
        "ok",
        "warn",
        "ok",
        "danger",
        "ok",
      ]) as string,
    }));

  switch (appId) {
    case "cybersecurity":
      return generate(6, "threat", [
        "Threats Blocked",
        "Vulns Scanned",
        "IP Checks",
        "Compliance %",
        "Active Alerts",
        "Patch Coverage",
      ]);
    case "health":
      return generate(6, "vital", [
        "Patients Triage",
        "Diag Accuracy",
        "Bed Occupancy",
        "Drug Check",
        "Telehealth",
        "ER Wait",
      ]);
    case "finance":
      return generate(6, "metric", [
        "Risk Score",
        "Market Sentiment",
        "Fraud Detected",
        "Payment Volume",
        "Approval Rate",
        "Portfolio VaR",
      ]);
    case "retail":
      return generate(6, "kpi", [
        "Sales Velocity",
        "Stock Health",
        "Order Fulfill",
        "Return Rate",
        "Customer Sat",
        "Inventory Turn",
      ]);
    case "transport":
      return generate(6, "zone", [
        "Traffic Flow",
        "Fleet Util",
        "On-Time Rate",
        "Incident Clear",
        "Route Efficiency",
        "Fuel Savings",
      ]);
    case "manufacturing":
      return generate(6, "machine", [
        "OEE Score",
        "Defect Rate",
        "Machine Health",
        "Throughput",
        "Energy Eff",
        "MTBF Hours",
      ]);
    case "tourism":
      return generate(6, "property", [
        "Occupancy",
        "RevPAR",
        "Booking Pace",
        "Guest Sat",
        "No-Show Rate",
        "Upsell Conv",
      ]);
    case "cultural_heritage":
      return generate(6, "venue", [
        "Visitor Flow",
        "Engagement",
        "Ticket Sales",
        "Tour Bookings",
        "Exhibit Pop",
        "Member Retent",
      ]);
    case "professional":
      return generate(6, "service", [
        "Doc Throughput",
        "Contract Cycle",
        "Invoice Accuracy",
        "Compliance",
        "Client Sat",
        "Billable Hours",
      ]);
    case "utilities":
      return generate(6, "grid", [
        "Grid Load",
        "Water Supply",
        "Waste Proc",
        "Renewable %",
        "Service Uptime",
        "Citizen Sat",
      ]);
    case "sme":
      return generate(6, "process", [
        "Workflow Auto",
        "Doc Proc",
        "Ticket Res",
        "Supply Chain",
        "Cost Savings",
        "Employee Prod",
      ]);
    default:
      return generate(4, "general", ["Performance", "Reliability", "Throughput", "Efficiency"]);
  }
}
