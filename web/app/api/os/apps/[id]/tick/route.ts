import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

/**
 * Mock responses for AEON OS app ticks.
 * Returns deterministic, contextual JSON for each app/query pair
 * without needing Python (works on Vercel).
 */
function mockTick(appId: string, query: string): object {
  const lower = query.toLowerCase();

  // Generic fallback
  const fallback = {
    ok: true,
    app_id: appId,
    query: query.slice(0, 80),
    response: `AEON processed '${query.slice(0, 60)}' for ${appId} module. Running in Vercel-compatible mock mode.`,
    mock: true,
  };

  // ── Cybersecurity ─────────────────────────────────────────────────
  if (appId === "cybersecurity") {
    if (lower.includes("scan") || lower.includes("vuln")) {
      return {
        ok: true,
        app_id: "cybersecurity",
        query: query.slice(0, 80),
        scan_results: [
          { port: 22, service: "SSH", status: "open", risk: "low", recommendation: "key-based auth only" },
          { port: 443, service: "HTTPS", status: "open", risk: "low", recommendation: "TLS 1.3 enabled" },
          { port: 3306, service: "MySQL", status: "open (internal)", risk: "medium", recommendation: "restrict to VPN" },
          { port: 8080, service: "HTTP-Alt", status: "open", risk: "high", recommendation: "close or require auth" },
        ],
        critical_vulns: 1,
        total_vulns: 4,
        overall_risk: "medium",
      };
    }
    if (lower.includes("ip") || lower.includes("reputation")) {
      return {
        ok: true,
        app_id: "cybersecurity",
        query: query.slice(0, 80),
        ip_reputation: { score: 0.18, known_malicious: false, source_countries: ["US", "DE", "JP"], last_seen_days: 2 },
        threat_intel: { active_campaigns: ["PhishKit-2026-03", "RansomHub-v2"], iocs_blocked_today: 142 },
      };
    }
    return fallback;
  }

  // ── Retail ────────────────────────────────────────────────────────
  if (appId === "retail") {
    if (lower.includes("forecast") || lower.includes("demand")) {
      return {
        ok: true, app_id: "retail",
        query: query.slice(0, 80),
        forecast: { sku: "SKU-001", predicted_units: 1240, confidence: 0.92, trend: "rising" },
      };
    }
    if (lower.includes("inventory") || lower.includes("stock")) {
      return {
        ok: true, app_id: "retail",
        query: query.slice(0, 80),
        inventory_health: { total_stock: 5250, low_stock_count: 1, overstock_count: 1 },
      };
    }
    return fallback;
  }

  // ── Manufacturing ─────────────────────────────────────────────────
  if (appId === "manufacturing") {
    if (lower.includes("maintenance")) {
      return {
        ok: true, app_id: "manufacturing",
        query: query.slice(0, 80),
        maintenance_schedule: [
          { machine: "CNC-01", days_until: 45, status: "good" },
          { machine: "CNC-04", days_until: 3, status: "critical", alerts: ["spindle overheat"] },
        ],
      };
    }
    return fallback;
  }

  // ── Professional Services ─────────────────────────────────────────
  if (appId === "professional") {
    if (lower.includes("document") || lower.includes("legal")) {
      return {
        ok: true, app_id: "professional",
        query: query.slice(0, 80),
        document_analysis: { clauses_found: 14, risk_flags: ["indemnification cap"], summary: "Standard NDA reviewed" },
      };
    }
    return fallback;
  }

  // ── Tourism ───────────────────────────────────────────────────────
  if (appId === "tourism") {
    if (lower.includes("pricing") || lower.includes("revenue")) {
      return {
        ok: true, app_id: "tourism",
        query: query.slice(0, 80),
        pricing_analysis: { room: "King Suite", current: 299, optimal: 320, recommendation: "increase by 7%" },
      };
    }
    return fallback;
  }

  return fallback;
}

export async function POST(
  req: NextRequest,
  { params }: { params: { id: string } },
) {
  const id = params.id;
  const body = await req.json().catch(() => ({}));
  const query = String(body.query || "").trim();

  if (!query) {
    return NextResponse.json(
      { ok: false, error: "missing query" },
      { status: 400 },
    );
  }

  const result = mockTick(id, query);
  return NextResponse.json(result);
}
