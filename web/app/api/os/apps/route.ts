import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

let apps: any[] = [];
let installed: string[] = [];

function loadApps() {
  if (apps.length > 0) return;
  // Mirror of the AppRegistry in aeon_os.py (simplified for the web layer)
  apps = [
    {
      id: "cybersecurity",
      name: "CyberSecurity",
      category: "Security & Compliance",
      description:
        "Autonomous threat intelligence, vulnerability tracking, IP reputation, and compliance monitoring for government and business.",
      icon: "🛡️",
      color: "#ef4444",
      status: "active",
      allowed_tools: [
        "threat_lookup",
        "vuln_scan",
        "ip_reputation",
        "compliance_check",
        "security_news",
        "fetch",
        "search",
      ],
      default_goals: [
        { title: "Monitor threat landscape and surface critical alerts", priority: 10 },
        { title: "Track high-severity CVEs affecting client assets", priority: 9 },
        { title: "Maintain IP reputation watchlist and flag malicious actors", priority: 8 },
        { title: "Generate compliance posture score for frameworks", priority: 7 },
      ],
    },
    {
      id: "retail",
      name: "Retail & Wholesale",
      category: "Commerce",
      description:
        "Intelligent stock forecasting, automated supply chains, and personalized digital storefronts.",
      icon: "🛒",
      color: "#10b981",
      status: "active",
      allowed_tools: [
        "demand_forecast",
        "inventory_optimizer",
        "supplier_risk",
        "price_elasticity",
        "storefront_personalizer",
        "fetch",
        "search",
        "math",
        "api_catalog_search",
      ],
      default_goals: [
        { title: "Monitor inventory for stockout risks and generate reorder recommendations", priority: 10 },
        { title: "Forecast high-velocity SKU demand across 30-90 day horizons", priority: 9 },
        { title: "Track supplier risk and flag delivery disruptions", priority: 8 },
        { title: "Optimize pricing and personalize storefront offers", priority: 7 },
      ],
    },
    {
      id: "manufacturing",
      name: "Manufacturing & Engineering",
      category: "Industry",
      description:
        "Predictive maintenance, automated QC vision systems, and smart logistics.",
      icon: "🏭",
      color: "#f59e0b",
      status: "active",
      allowed_tools: [
        "predictive_maintenance",
        "qc_vision",
        "smart_logistics",
        "fetch",
        "search",
        "math",
      ],
      default_goals: [
        { title: "Monitor machine telemetry for failure risks and dispatch maintenance", priority: 10 },
        { title: "Scan QC pipeline for defect spikes and production anomalies", priority: 9 },
        { title: "Optimize logistics routes and minimize delivery delays", priority: 8 },
      ],
    },
    {
      id: "professional",
      name: "Professional Services",
      category: "Services",
      description:
        "Automated legal document parsing, intelligent accounting workflows, and digital data management.",
      icon: "📄",
      color: "#3b82f6",
      status: "active",
      allowed_tools: [
        "legal_doc_parser",
        "smart_accounting",
        "data_manager",
        "fetch",
        "search",
        "math",
      ],
      default_goals: [
        { title: "Parse incoming contracts and flag high-risk clauses", priority: 10 },
        { title: "Process invoice queue and surface accounting anomalies", priority: 9 },
        { title: "Scan data assets for PII and compliance readiness", priority: 8 },
      ],
    },
    {
      id: "tourism",
      name: "Tourism & Hospitality",
      category: "Hospitality",
      description:
        "AI-driven booking optimization, dynamic pricing, and automated guest concierge.",
      icon: "🏨",
      color: "#ec4899",
      status: "active",
      allowed_tools: [
        "booking_optimizer",
        "dynamic_pricing",
        "automated_concierge",
        "fetch",
        "search",
        "math",
      ],
      default_goals: [
        { title: "Maximize occupancy through predictive overbooking", priority: 10 },
        { title: "Adjust room rates dynamically based on demand signals", priority: 9 },
        { title: "Triage guest requests and automate concierge responses", priority: 8 },
      ],
    },
  ];
}

export async function GET() {
  loadApps();
  return NextResponse.json({ ok: true, apps, installed });
}

export async function POST(req: NextRequest) {
  loadApps();
  const body = await req.json().catch(() => ({}));
  const appId = String(body.appId || "").trim();
  const exists = apps.some((a) => a.id === appId);
  if (!exists) {
    return NextResponse.json({ ok: false, error: "unknown app" }, { status: 400 });
  }
  if (!installed.includes(appId)) {
    installed.push(appId);
  }
  return NextResponse.json({ ok: true, appId, installed });
}
