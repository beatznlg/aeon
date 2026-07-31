import { NextRequest, NextResponse } from "next/server";
import { listSectorTools, generateSectorData } from "@/lib/sector-data-gen";

export const dynamic = "force-dynamic";
export const maxDuration = 60; // Can take time to search all 40+ tools

// ─── Sector display metadata ──────────────────────────────────────────────────

const SECTOR_INFO: Record<string, { name: string; icon: string }> = {
  cybersecurity: { name: "Cybersecurity", icon: "🛡️" },
  health: { name: "Healthcare", icon: "🏥" },
  finance: { name: "Finance", icon: "💰" },
  retail: { name: "Retail & E-commerce", icon: "📦" },
  transport: { name: "Transport & Logistics", icon: "🚚" },
  manufacturing: { name: "Manufacturing", icon: "🏭" },
  tourism: { name: "Tourism & Hospitality", icon: "🏨" },
  utilities: { name: "Utilities & Energy", icon: "⚡" },
  cultural_heritage: { name: "Cultural Heritage", icon: "🎭" },
  sme: { name: "SME Business Suite", icon: "🏢" },
  professional: { name: "Professional Services", icon: "📋" },
};

const TOOL_LABELS: Record<string, string> = {
  threats: "Threat Intelligence",
  vulnerabilities: "Vulnerability Scan",
  compliance: "Compliance Posture",
  "ip-reputation": "IP Reputation",
  news: "Security News",
  diagnostics: "Diagnostic Analysis",
  vitals: "Patient Vitals",
  "drug-interactions": "Drug Interactions",
  telehealth: "Telehealth Triage",
  risk: "Risk Assessment",
  market: "Market Forecast",
  fraud: "Fraud Detection",
  credit: "Credit Scoring",
  payments: "Payment Analysis",
  forecast: "Demand Forecast",
  inventory: "Inventory Status",
  suppliers: "Supplier Risk",
  pricing: "Price Elasticity",
  traffic: "Traffic Zones",
  fleet: "Fleet Scheduling",
  routes: "Route Planning",
  maintenance: "Machine Health",
  quality: "Quality Control",
  logistics: "Smart Logistics",
  bookings: "Booking Optimization",
  concierge: "Concierge Triage",
  visitors: "Visitor Analytics",
  sites: "Heritage Sites",
  exhibitions: "Exhibition Planning",
  tours: "Virtual Tours",
  resources: "Resource Optimization",
  services: "Public Services KPIs",
  waste: "Waste Management",
  grid: "Energy Grid",
  workflows: "Workflow Automation",
  documents: "Document Processing",
  support: "Customer Support",
  "supply-chain": "Supply Chain",
  legal: "Legal Document Review",
  accounting: "Accounting Audit",
  "data-management": "Data Compliance",
};

// ─── Search logic ────────────────────────────────────────────────────────────

interface SearchResultItem {
  sectorId: string;
  sectorName: string;
  sectorIcon: string;
  toolPath: string;
  toolLabel: string;
  matchField: string;
  matchValue: string;
  record: Record<string, unknown>;
}

/**
 * Recursively search an object/array for text matches.
 * Returns up to maxMatches matches with field/value context.
 */
function searchObject(
  obj: unknown,
  query: string,
  maxMatches: number
): { field: string; value: string }[] {
  const q = query.toLowerCase();
  const results: { field: string; value: string }[] = [];

  function walk(value: unknown, path: string) {
    if (results.length >= maxMatches) return;

    if (Array.isArray(value)) {
      for (let i = 0; i < value.length; i++) {
        walk(value[i], `${path}[${i}]`);
      }
    } else if (value !== null && typeof value === "object") {
      for (const [key, val] of Object.entries(value as Record<string, unknown>)) {
        if (results.length >= maxMatches) return;
        walk(val, path ? `${path}.${key}` : key);
      }
    } else if (typeof value === "string") {
      const str = value.toLowerCase();
      if (str.includes(q)) {
        results.push({
          field: path || "value",
          value: value.length > 120 ? value.substring(0, 117) + "…" : value,
        });
      }
    } else if (typeof value === "number" || typeof value === "boolean") {
      const str = String(value);
      if (str.includes(q)) {
        results.push({ field: path || "value", value: str });
      }
    }
  }

  walk(obj, "");
  return results;
}

// ─── GET handler ─────────────────────────────────────────────────────────────

export async function GET(req: NextRequest) {
  const q = req.nextUrl.searchParams.get("q")?.trim();
  const sector = req.nextUrl.searchParams.get("sector"); // optional filter
  const limit = Math.min(Number(req.nextUrl.searchParams.get("limit")) || 10, 50);

  if (!q || q.length < 1) {
    return NextResponse.json({ ok: true, results: [], query: q });
  }

  const allTools = listSectorTools();
  const results: SearchResultItem[] = [];

  // Filter by sector if specified
  const toolsToSearch = sector ? allTools.filter((t) => t.sector === sector) : allTools;

  // Generate data for each tool and search
  for (const { sector: s, tool: t } of toolsToSearch) {
    if (results.length >= limit) break;

    try {
      const data = generateSectorData({ sector: s, tool: t });
      if (!data || (typeof data === "object" && (data as Record<string, unknown>).error)) continue;

      const matches = searchObject(data, q, 3);
      if (matches.length > 0) {
        const info = SECTOR_INFO[s];
        const label = TOOL_LABELS[t] || t;
        for (const match of matches) {
          if (results.length >= limit) break;
          results.push({
            sectorId: s,
            sectorName: info?.name || s,
            sectorIcon: info?.icon || "📊",
            toolPath: t,
            toolLabel: label,
            matchField: match.field,
            matchValue: match.value,
            record: {},
          });
        }
      }
    } catch {
      // Silently skip tools that error
    }
  }

  return NextResponse.json({
    ok: true,
    query: q,
    totalResults: results.length,
    results,
  });
}
