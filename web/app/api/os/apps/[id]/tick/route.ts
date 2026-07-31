import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/auth";
import { logAudit } from "@/lib/audit";
import { kernelTick, pythonUrl } from "@/lib/kernel";

export const dynamic = "force-dynamic";

/**
 * Mock responses for AEON OS app tick.
 * Returns deterministic, contextual JSON for each app/query pair
 * without needing Python (works on Vercel).
 */
function mockTick(appId: string, query: string): object {
  const lower = query.toLowerCase();
  const q = query.slice(0, 80);

  // Generic fallback
  const fallback = {
    ok: true,
    app_id: appId,
    query,
    response: `AEON processed '${q}' for the ${appId} module. Running in Vercel-compatible mock mode.`,
    mock: true,
  };

  // ── Cybersecurity ─────────────────────────────────────────────────
  if (appId === "cybersecurity") {
    if (lower.includes("scan") || lower.includes("vuln")) {
      return {
        ok: true,
        app_id: "cybersecurity",
        query,
        scan_results: [
          {
            port: 22,
            service: "SSH",
            status: "open",
            risk: "low",
            recommendation: "key-based auth only",
          },
          {
            port: 443,
            service: "HTTPS",
            status: "open",
            risk: "low",
            recommendation: "TLS 1.3 enabled",
          },
          {
            port: 3306,
            service: "MySQL",
            status: "open (internal)",
            risk: "medium",
            recommendation: "restrict to VPN",
          },
          {
            port: 8080,
            service: "HTTP-Alt",
            status: "open",
            risk: "high",
            recommendation: "close or require auth",
          },
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
        query,
        ip_reputation: {
          score: 0.18,
          known_malicious: false,
          source_countries: ["US", "DE", "JP"],
          last_seen_days: 2,
        },
        threat_intel: {
          active_campaigns: ["PhishKit-2026-03", "RansomHub-v2"],
          iocs_blocked_today: 142,
        },
      };
    }
    return fallback;
  }

  // ── Retail ────────────────────────────────────────────────────────
  if (appId === "retail") {
    if (lower.includes("forecast") || lower.includes("demand")) {
      return {
        ok: true,
        app_id: "retail",
        query,
        forecast: { sku: "SKU-001", predicted_units: 1240, confidence: 0.92, trend: "rising" },
      };
    }
    if (lower.includes("inventory") || lower.includes("stock")) {
      return {
        ok: true,
        app_id: "retail",
        query,
        inventory_health: { total_stock: 5250, low_stock_count: 1, overstock_count: 1 },
      };
    }
    return fallback;
  }

  // ── Manufacturing ─────────────────────────────────────────────────
  if (appId === "manufacturing") {
    if (lower.includes("maintenance")) {
      return {
        ok: true,
        app_id: "manufacturing",
        query,
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
        ok: true,
        app_id: "professional",
        query,
        document_analysis: {
          clauses_found: 14,
          risk_flags: ["indemnification cap"],
          summary: "Standard NDA reviewed",
        },
      };
    }
    return fallback;
  }

  // ── Tourism ───────────────────────────────────────────────────────
  if (appId === "tourism") {
    if (lower.includes("pricing") || lower.includes("revenue")) {
      return {
        ok: true,
        app_id: "tourism",
        query,
        pricing_analysis: {
          room: "King Suite",
          current: 299,
          optimal: 320,
          recommendation: "increase by 7%",
        },
      };
    }
    return fallback;
  }

  // ── Health & Medicine ─────────────────────────────────────────────
  if (appId === "health") {
    if (lower.includes("vitals") || lower.includes("monitor")) {
      return {
        ok: true,
        app_id: "health",
        query,
        vitals_summary: { patients_monitored: 42, alerts: 3, stable: 39 },
      };
    }
    if (lower.includes("drug") || lower.includes("interaction")) {
      return {
        ok: true,
        app_id: "health",
        query,
        interaction_check: {
          medications: ["aspirin", "warfarin"],
          risk: "moderate",
          warning: "increased bleeding risk",
        },
      };
    }
    return fallback;
  }

  // ── Transport & Logistics ─────────────────────────────────────────
  if (appId === "transport") {
    if (lower.includes("route") || lower.includes("optimize")) {
      return {
        ok: true,
        app_id: "transport",
        query,
        route_optimization: {
          stops: ["A", "B", "C"],
          estimated_distance_km: 42,
          estimated_time_min: 55,
          fuel_cost: 18.5,
        },
      };
    }
    if (lower.includes("traffic") || lower.includes("congestion")) {
      return {
        ok: true,
        app_id: "transport",
        query,
        traffic_summary: { zones_monitored: 4, congested_zones: 2, avg_speed_kmh: 25 },
      };
    }
    return fallback;
  }

  // ── Finance & Fintech ─────────────────────────────────────────────
  if (appId === "finance") {
    if (lower.includes("risk") || lower.includes("var")) {
      return {
        ok: true,
        app_id: "finance",
        query,
        risk_assessment: {
          portfolio_value: 500000,
          var_95_1d: 12500,
          sharpe: 1.45,
          recommendation: "diversify fixed income",
        },
      };
    }
    if (lower.includes("fraud")) {
      return {
        ok: true,
        app_id: "finance",
        query,
        fraud_summary: { flagged_transactions: 3, total_blocked: 1, review_queue: 2 },
      };
    }
    return fallback;
  }

  // ── Cultural Heritage ─────────────────────────────────────────────
  if (appId === "cultural_heritage") {
    if (lower.includes("visitor") || lower.includes("engagement")) {
      return {
        ok: true,
        app_id: "cultural_heritage",
        query,
        visitor_engagement: {
          venues: 3,
          avg_engagement: 88,
          top_strategy: "extend hours weekends",
        },
      };
    }
    if (lower.includes("exhibition") || lower.includes("plan")) {
      return {
        ok: true,
        app_id: "cultural_heritage",
        query,
        exhibition_plan: { theme: "Modern Art", projected_visitors: 80000, roi: 2.4 },
      };
    }
    return fallback;
  }

  // ── Utilities & Consumer Services ─────────────────────────────────
  if (appId === "utilities") {
    if (lower.includes("grid") || lower.includes("energy")) {
      return {
        ok: true,
        app_id: "utilities",
        query,
        grid_status: { regions: 3, stable: 2, critical: 1, avg_utilization: 89 },
      };
    }
    if (lower.includes("waste")) {
      return {
        ok: true,
        app_id: "utilities",
        query,
        waste_summary: { districts: 3, avg_recycling_pct: 32.7, collection_efficiency: 0.88 },
      };
    }
    return fallback;
  }

  // ── SME Business Suite ────────────────────────────────────────────
  if (appId === "sme") {
    if (lower.includes("workflow") || lower.includes("automation")) {
      return {
        ok: true,
        app_id: "sme",
        query,
        workflow_summary: {
          processes_automated: 3,
          hours_saved_monthly: 260,
          annual_savings: 52000,
        },
      };
    }
    if (lower.includes("support") || lower.includes("ticket")) {
      return {
        ok: true,
        app_id: "sme",
        query,
        support_summary: { tickets_resolved: 142, escalated: 3, avg_satisfaction: 4.3 },
      };
    }
    return fallback;
  }

  return fallback;
}

export async function POST(req: NextRequest, { params }: { params: { id: string } }) {
  const id = params.id;
  const body = await req.json().catch(() => ({}));
  const query = String(body.query || "").trim();

  if (!query) {
    return NextResponse.json({ ok: false, error: "missing query" }, { status: 400 });
  }

  const session = await auth();
  logAudit({
    userId: (session?.user as any)?.id,
    email: session?.user?.email ?? undefined,
    action: "TICK",
    module: id,
    metadata: { query },
  });

  // --- Route to the Python AEON kernel if configured ---
  if (pythonUrl()) {
    try {
      const kernelRes = await kernelTick(id, query);
      if (kernelRes) {
        return NextResponse.json(kernelRes);
      }
    } catch (error: any) {
      console.error(`[module-tick ${id}] kernel proxy error:`, error);
      return NextResponse.json(
        { ok: false, error: "kernel_proxy_error", details: error?.message },
        { status: 502 }
      );
    }
  }

  const result = mockTick(id, query);
  return NextResponse.json(result);
}
