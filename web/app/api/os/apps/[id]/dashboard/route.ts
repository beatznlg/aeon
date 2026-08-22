import { NextResponse } from "next/server";
import { auth } from "@/auth";
import { logAudit } from "@/lib/audit";
import { logUsage } from "@/lib/usage";

export const dynamic = "force-dynamic";

const AEON_PYTHON_URL = process.env.AEON_PYTHON_URL || "http://127.0.0.1:5000";

/**
 * Maps a frontend sector id to the Python backend sector name.
 * Only needed when the names differ (e.g. cultural_heritage vs heritage).
 */
const SECTOR_ALIASES: Record<string, string> = {
  cultural_heritage: "heritage",
};

/**
 * Maps Python tool data_key values to the keys the existing dashboard
 * components expect. This lets the Python backend stay the source of
 * truth while the frontend keeps its current shape.
 */
const SECTOR_KEY_MAP: Record<string, Record<string, string>> = {
  cybersecurity: { news: "security_news" },
  health: {
    vitals: "patient_vitals",
    interactions: "drug_interactions",
    triage: "telehealth",
  },
  finance: {
    risk: "risk_data",
    market: "market_data",
    applications: "credit_applications",
    accounts: "payment_analysis",
  },
  retail: {
    suppliers: "supplier_risks",
    elasticity: "price_elasticity",
  },
  transport: {
    zones: "traffic",
    routes: "route_plan",
  },
  manufacturing: {
    machines: "maintenance",
    batches: "qc",
    shipments: "logistics",
  },
  tourism: {
    requests: "concierge",
    venues: "visitors",
  },
  utilities: {
    resources: "resource_data",
    services: "public_services",
    districts: "waste_data",
    regions: "energy_grid",
  },
  cultural_heritage: {
    venues: "visitor_data",
    sites: "heritage_sites",
    exhibitions: "exhibitions",
    tours: "virtual_tours",
  },
  sme: {
    workflows: "workflow_data",
    documents: "document_queue",
    tickets: "support_tickets",
    chains: "supply_chain",
  },
};

/**
 * Deterministic mock dashboard data for each AEON OS vertical.
 * Used as a fallback when the Python backend is unavailable and to
 * provide static-only sections (e.g. personalizer) that the backend
 * does not yet expose.
 */
const dashboards: Record<string, object> = {
  // ── Cybersecurity ───────────────────────────────────────────────────
  cybersecurity: {
    ok: true,
    threats: [
      { id: "TH-001", indicator: "192.0.2.45", type: "IP", severity: "high", status: "blocked" },
      {
        id: "TH-002",
        indicator: "malware.exe",
        type: "Hash",
        severity: "critical",
        status: "quarantined",
      },
      {
        id: "TH-003",
        indicator: "phish.example.com",
        type: "Domain",
        severity: "medium",
        status: "monitored",
      },
    ],
    vulnerabilities: [
      {
        cve: "CVE-2024-0001",
        severity: "Critical",
        cvss: 9.8,
        affected: "example-lib",
        patch_available: true,
      },
      {
        cve: "CVE-2024-0002",
        severity: "High",
        cvss: 7.5,
        affected: "auth-service",
        patch_available: false,
      },
      {
        cve: "CVE-2024-0003",
        severity: "Medium",
        cvss: 5.3,
        affected: "api-gateway",
        patch_available: true,
      },
    ],
    ip_reputation: {
      score: 0.18,
      known_malicious: false,
      source_countries: ["US", "DE", "JP"],
      last_seen_days: 2,
    },
    compliance: {
      framework: "NIST-CSF",
      score: 84,
      maturity: "Managed",
      gaps: ["IAM review", "Log retention", "Incident response automation"],
    },
    security_news: [
      { title: "Critical OpenSSH vulnerability disclosed", url: "#" },
      { title: "New ransomware group targets healthcare sector", url: "#" },
    ],
  },

  // ── Retail & Wholesale ─────────────────────────────────────────────
  retail: {
    ok: true,
    forecast: [
      {
        sku: "SKU-001",
        current_stock: 850,
        projected_demand: 1240,
        recommended_order_qty: 390,
        confidence: 0.92,
      },
      {
        sku: "SKU-042",
        current_stock: 420,
        projected_demand: 680,
        recommended_order_qty: 260,
        confidence: 0.88,
      },
      {
        sku: "SKU-099",
        current_stock: 2100,
        projected_demand: 1890,
        recommended_order_qty: 0,
        confidence: 0.95,
      },
      {
        sku: "SKU-107",
        current_stock: 120,
        projected_demand: 340,
        recommended_order_qty: 220,
        confidence: 0.76,
      },
      {
        sku: "SKU-215",
        current_stock: 560,
        projected_demand: 890,
        recommended_order_qty: 330,
        confidence: 0.84,
      },
    ],
    inventory: {
      alerts: [{ sku: "SKU-107", status: "stockout_risk", days_remaining: 2 }],
      reorder_recommendations: [
        { sku: "SKU-107", qty: 220, supplier: "Alpha Corp" },
        { sku: "SKU-042", qty: 260, supplier: "Gamma Wholesale" },
      ],
      healthy: [
        { sku: "SKU-001", status: "healthy", days_supply: 21 },
        { sku: "SKU-099", status: "overstock", days_supply: 75 },
        { sku: "SKU-215", status: "healthy", days_supply: 18 },
      ],
      summary: { total_skus: 5, stockout_risks: 1, overstocks: 1 },
    },
    supplier_risks: [
      {
        supplier: "Alpha Corp",
        risk_score: 15,
        classification: "Low Risk",
        on_time_delivery_pct: 96,
      },
      {
        supplier: "Beta Logistics",
        risk_score: 42,
        classification: "Medium Risk",
        on_time_delivery_pct: 82,
      },
      {
        supplier: "Gamma Wholesale",
        risk_score: 8,
        classification: "Low Risk",
        on_time_delivery_pct: 99,
      },
      {
        supplier: "Delta Distributors",
        risk_score: 71,
        classification: "High Risk",
        on_time_delivery_pct: 61,
      },
    ],
    price_elasticity: {
      sku: "SKU-001",
      price_change_pct: 10,
      elasticity: -0.42,
      projected_demand_change_pct: -4.2,
    },
    personalizer: {
      segment: "premium_shopper",
      recommended_products: ["SKU-099", "SKU-001", "SKU-215"],
      estimated_conversion_lift_pct: 10,
    },
  },

  // ── Manufacturing & Engineering ─────────────────────────────────────
  manufacturing: {
    ok: true,
    maintenance: [
      {
        machine_id: "CNC-01",
        status: "good",
        temp_c: 42,
        vibration_hz: 12.5,
        failure_risk_pct: 12,
        days_to_failure: 45,
      },
      {
        machine_id: "CNC-02",
        status: "warning",
        temp_c: 58,
        vibration_hz: 18.2,
        failure_risk_pct: 34,
        days_to_failure: 12,
      },
      {
        machine_id: "CNC-03",
        status: "good",
        temp_c: 44,
        vibration_hz: 11.8,
        failure_risk_pct: 15,
        days_to_failure: 30,
      },
      {
        machine_id: "CNC-04",
        status: "critical",
        temp_c: 78,
        vibration_hz: 31.4,
        failure_risk_pct: 89,
        days_to_failure: 3,
      },
    ],
    qc: [
      {
        batch_id: "B-998",
        items_scanned: 500,
        defects_found: 10,
        defect_rate: 0.02,
        status: "pass",
      },
      {
        batch_id: "B-999",
        items_scanned: 500,
        defects_found: 35,
        defect_rate: 0.07,
        status: "fail",
      },
      {
        batch_id: "B-1000",
        items_scanned: 500,
        defects_found: 5,
        defect_rate: 0.01,
        status: "pass",
      },
    ],
    logistics: [
      { route_id: "R-10", status: "on_time", eta_days: 1, reroute_cost_usd: 0 },
      { route_id: "R-11", status: "delayed", eta_days: 3, reroute_cost_usd: 1800 },
      { route_id: "R-12", status: "on_time", eta_days: 2, reroute_cost_usd: 0 },
    ],
  },

  // ── Professional & Technical Services ───────────────────────────────
  professional: {
    ok: true,
    legal: [
      {
        doc: "Vendor_NDA.pdf",
        type: "NDA",
        risk_score: "low",
        obligations: ["5-year term", "standard confidentiality"],
      },
      {
        doc: "Client_MSA.pdf",
        type: "MSA",
        risk_score: "medium",
        obligations: ["auto-renewal", "liability cap review"],
      },
      {
        doc: "Employment_Contract.pdf",
        type: "Employment",
        risk_score: "low",
        obligations: ["IP assignment", "non-compete scope"],
      },
    ],
    accounting: [
      {
        invoice_id: "INV-102",
        vendor: "Alpha Services",
        amount: 12500,
        anomalies_detected: false,
        auto_approved: true,
      },
      {
        invoice_id: "INV-103",
        vendor: "Beta Consulting",
        amount: 8400,
        anomalies_detected: true,
        auto_approved: false,
      },
      {
        invoice_id: "INV-104",
        vendor: "Gamma Cloud",
        amount: 22000,
        anomalies_detected: false,
        auto_approved: true,
      },
    ],
    data_management: [
      { dataset: "user_dump.csv", pii_records_found: 23, compliance: "GDPR-ready" },
      { dataset: "transactions.csv", pii_records_found: 12, compliance: "GDPR-ready" },
    ],
  },

  // ── Tourism & Hospitality ───────────────────────────────────────────
  tourism: {
    ok: true,
    bookings: [
      {
        property: "Hotel-Central",
        occupancy_pct: 82,
        predictive_no_shows: 14,
        net_expected_occupancy: 78,
      },
      {
        property: "Hotel-West",
        occupancy_pct: 68,
        predictive_no_shows: 18,
        net_expected_occupancy: 64,
      },
      {
        property: "Hotel-Airport",
        occupancy_pct: 91,
        predictive_no_shows: 22,
        net_expected_occupancy: 89,
      },
    ],
    pricing: [
      { room: "King Suite", base_price: 299, recommended_price: 320, reason: "High demand" },
      { room: "Double Queen", base_price: 259, recommended_price: 245, reason: "Medium demand" },
      { room: "Standard", base_price: 169, recommended_price: 175, reason: "Low demand, hold" },
    ],
    concierge: [
      {
        guest_id: "G-445",
        sentiment: "positive",
        intent: "dining reservation",
        automated_response: "Reservation confirmed at 8 PM",
        upsell: "Wine pairing package",
      },
      {
        guest_id: "G-446",
        sentiment: "neutral",
        intent: "housekeeping request",
        automated_response: "Housekeeping dispatched",
        upsell: null,
      },
      {
        guest_id: "G-447",
        sentiment: "negative",
        intent: "transport to airport",
        automated_response: "Taxi booked for 6 AM",
        upsell: null,
      },
    ],
  },

  // ── Health & Medicine ───────────────────────────────────────────────
  health: {
    ok: true,
    diagnostics: [
      {
        analyzed_symptoms: "fever, cough, fatigue",
        possible_conditions: [
          {
            name: "viral infection",
            probability: 0.78,
            severity: "moderate",
            action: "rest and monitor",
          },
        ],
        urgency: "moderate",
        recommendation: "rest and monitor",
      },
      {
        analyzed_symptoms: "chest pain, shortness of breath",
        possible_conditions: [
          {
            name: "cardiac concern",
            probability: 0.65,
            severity: "high",
            action: "immediate evaluation",
          },
        ],
        urgency: "high",
        recommendation: "immediate evaluation",
      },
      {
        analyzed_symptoms: "headache, nausea",
        possible_conditions: [
          {
            name: "migraine",
            probability: 0.72,
            severity: "moderate",
            action: "hydration and rest",
          },
        ],
        urgency: "moderate",
        recommendation: "hydration and rest",
      },
    ],
    patient_vitals: [
      {
        patient_id: "P-1001",
        metric: "heart_rate",
        baseline: 72,
        current: 72,
        trend: "stable",
        alert: false,
      },
      {
        patient_id: "P-1001",
        metric: "blood_pressure_sys",
        baseline: 120,
        current: 118,
        trend: "stable",
        alert: false,
      },
      {
        patient_id: "P-1002",
        metric: "heart_rate",
        baseline: 72,
        current: 95,
        trend: "rising",
        alert: true,
      },
      {
        patient_id: "P-1002",
        metric: "blood_pressure_sys",
        baseline: 120,
        current: 142,
        trend: "rising",
        alert: true,
      },
    ],
    drug_interactions: [
      {
        medications: ["aspirin", "warfarin"],
        interactions_found: 1,
        interactions: [
          {
            drugs: ["aspirin", "warfarin"],
            severity: "moderate",
            warning: "increased bleeding risk",
          },
        ],
      },
      {
        medications: ["lisinopril", "potassium"],
        interactions_found: 1,
        interactions: [
          { drugs: ["lisinopril", "potassium"], severity: "high", warning: "hyperkalemia risk" },
        ],
      },
    ],
    telehealth: [
      { symptoms: "chest pain", age: 65, urgency: "emergent", recommendation: "call 911" },
      {
        symptoms: "fever",
        age: 30,
        urgency: "non-urgent",
        recommendation: "schedule virtual visit",
      },
      {
        symptoms: "skin rash",
        age: 42,
        urgency: "routine",
        recommendation: "upload photos for dermatology review",
      },
    ],
  },

  // ── Transport & Logistics ───────────────────────────────────────────
  transport: {
    ok: true,
    traffic: [
      {
        zone: "downtown",
        current_congestion: 8.2,
        predicted_improvement: "divert to ring road",
        incident_nearby: true,
      },
      {
        zone: "midtown",
        current_congestion: 6.5,
        predicted_improvement: "monitor",
        incident_nearby: false,
      },
      {
        zone: "airport_corridor",
        current_congestion: 9.1,
        predicted_improvement: "activate bus lane",
        incident_nearby: true,
      },
      {
        zone: "suburb_east",
        current_congestion: 3.8,
        predicted_improvement: "normal flow",
        incident_nearby: false,
      },
    ],
    fleet: [
      {
        vehicles_available: 10,
        shifts: 3,
        utilization_pct: 87,
        recommendation: "reduce 1 vehicle",
      },
      {
        vehicles_available: 8,
        shifts: 2,
        utilization_pct: 72,
        recommendation: "reduce 2 vehicles",
      },
      { vehicles_available: 15, shifts: 3, utilization_pct: 93, recommendation: "optimal" },
    ],
    route_plan: [
      {
        stops: ["A", "B", "C", "D", "E"],
        estimated_distance_km: 42,
        estimated_time_min: 55,
        fuel_cost_est: 18.5,
      },
      {
        stops: ["F", "G", "H", "I", "J"],
        estimated_distance_km: 38,
        estimated_time_min: 48,
        fuel_cost_est: 16.2,
      },
      {
        stops: ["K", "L", "M", "N", "O"],
        estimated_distance_km: 56,
        estimated_time_min: 72,
        fuel_cost_est: 24.8,
      },
    ],
  },

  // ── Finance & Fintech ───────────────────────────────────────────────
  finance: {
    ok: true,
    risk_data: {
      asset: "S&P 500",
      portfolio_value: 500000,
      var_95_1d: 12500,
      var_95_pct: 2.5,
      sharpe_estimate: 1.45,
      beta: 0.98,
      risk_rating: "medium",
      diversification_score: 7,
      recommendation: "diversify fixed income",
    },
    payment_analysis: [
      {
        account_id: "ACC-1234",
        total_transactions: 142,
        total_volume: 48500,
        anomaly_count: 1,
        spending_trend: "stable",
      },
      {
        account_id: "ACC-5678",
        total_transactions: 89,
        total_volume: 22300,
        anomaly_count: 3,
        spending_trend: "increasing",
      },
      {
        account_id: "ACC-9012",
        total_transactions: 312,
        total_volume: 128000,
        anomaly_count: 0,
        spending_trend: "stable",
      },
    ],
    market_data: {
      market: "NASDAQ",
      predicted_direction: "bullish",
      confidence: 0.72,
      price_target_pct: 4.2,
      volatility_forecast: "moderate",
    },
    fraud_cases: [
      {
        transaction_id: "TXN-5001",
        amount: 5000,
        fraud_score: 0.85,
        risk_level: "high",
        action: "blocked",
      },
      {
        transaction_id: "TXN-5002",
        amount: 35,
        fraud_score: 0.05,
        risk_level: "low",
        action: "approved",
      },
      {
        transaction_id: "TXN-5003",
        amount: 25000,
        fraud_score: 0.72,
        risk_level: "high",
        action: "flagged",
      },
    ],
    credit_applications: [
      { applicant_id: "APP-200", credit_score: 720, rating: "Good", approval_probability: 0.92 },
      { applicant_id: "APP-201", credit_score: 580, rating: "Poor", approval_probability: 0.18 },
      {
        applicant_id: "APP-202",
        credit_score: 810,
        rating: "Excellent",
        approval_probability: 0.99,
      },
    ],
  },

  // ── Cultural Heritage ───────────────────────────────────────────────
  cultural_heritage: {
    ok: true,
    visitor_data: [
      {
        venue: "National Museum",
        daily_visitors: 1200,
        engagement_score: 92,
        recommended_strategies: ["extend hours weekends", "new family tour"],
      },
      {
        venue: "Modern Art Gallery",
        daily_visitors: 680,
        engagement_score: 88,
        recommended_strategies: ["new exhibition promo"],
      },
      {
        venue: "History Center",
        daily_visitors: 450,
        engagement_score: 85,
        recommended_strategies: ["school program expansion"],
      },
    ],
    heritage_sites: [
      {
        site: "Colosseum",
        era: "Ancient Rome",
        significance: "Iconic amphitheatre",
        annual_visitors: 7400000,
        conservation_status: "good",
      },
      {
        site: "Machu Picchu",
        era: "Inca Empire",
        significance: "Citadel in the Andes",
        annual_visitors: 2500000,
        conservation_status: "requires attention",
      },
      {
        site: "Angkor Wat",
        era: "Khmer Empire",
        significance: "Largest religious monument",
        annual_visitors: 2600000,
        conservation_status: "fair",
      },
    ],
    exhibitions: [
      {
        theme: "Modern Art",
        recommended_duration_days: 90,
        estimated_visitors: 80000,
        ticket_price: 25,
        projected_revenue: 2000000,
      },
      {
        theme: "Ancient Egypt",
        recommended_duration_days: 60,
        estimated_visitors: 60000,
        ticket_price: 22,
        projected_revenue: 1320000,
      },
      {
        theme: "Space Exploration",
        recommended_duration_days: 45,
        estimated_visitors: 45000,
        ticket_price: 28,
        projected_revenue: 1260000,
      },
    ],
    virtual_tours: [
      {
        site: "Louvre Museum",
        interest: "art",
        narration: "Explore the Mona Lisa and French masters",
        audio_duration_seconds: 2100,
      },
      {
        site: "British Museum",
        interest: "history",
        narration: "Journey through 2 million years of history",
        audio_duration_seconds: 2400,
      },
      {
        site: "Uffizi Gallery",
        interest: "architecture",
        narration: "Renaissance art and architecture",
        audio_duration_seconds: 1680,
      },
    ],
  },

  // ── Utilities & Public Sector ────────────────────────────────────────
  utilities: {
    ok: true,
    resource_data: [
      { resource: "water", demand: 1000, supply: 850, deficit: 150, status: "critical" },
      { resource: "electricity", demand: 500, supply: 480, deficit: 20, status: "warning" },
      { resource: "natural_gas", demand: 300, supply: 320, deficit: 0, status: "good" },
    ],
    public_services: [
      {
        service: "waste_collection",
        kpi_score: 0.89,
        status: "satisfactory",
        citizen_satisfaction: 0.78,
        trend: "stable",
      },
      {
        service: "street_lighting",
        kpi_score: 0.97,
        status: "excellent",
        citizen_satisfaction: 0.92,
        trend: "improving",
      },
      {
        service: "public_transport",
        kpi_score: 0.82,
        status: "needs improvement",
        citizen_satisfaction: 0.65,
        trend: "declining",
      },
    ],
    waste_data: [
      {
        district: "Zone A",
        total_waste_tons: 1200,
        recycled_pct: 35,
        landfill_pct: 65,
        collection_efficiency: 0.92,
      },
      {
        district: "Zone B",
        total_waste_tons: 850,
        recycled_pct: 22,
        landfill_pct: 78,
        collection_efficiency: 0.78,
      },
      {
        district: "Zone C",
        total_waste_tons: 1600,
        recycled_pct: 41,
        landfill_pct: 59,
        collection_efficiency: 0.95,
      },
    ],
    energy_grid: [
      {
        region: "North Grid",
        current_load_mw: 245,
        capacity_mw: 280,
        utilization_pct: 87.5,
        renewable_share_pct: 38,
        status: "stable",
      },
      {
        region: "South Grid",
        current_load_mw: 312,
        capacity_mw: 300,
        utilization_pct: 104,
        renewable_share_pct: 22,
        status: "critical",
      },
      {
        region: "East Grid",
        current_load_mw: 198,
        capacity_mw: 260,
        utilization_pct: 76.2,
        renewable_share_pct: 45,
        status: "stable",
      },
    ],
  },

  // ── SME Business Suite ───────────────────────────────────────────────
  sme: {
    ok: true,
    workflow_data: [
      {
        process: "invoice_approval",
        employees_involved: 5,
        hours_saved_per_month: 120,
        cost_savings_annual: 24000,
      },
      {
        process: "employee_onboarding",
        employees_involved: 3,
        hours_saved_per_month: 80,
        cost_savings_annual: 16000,
      },
      {
        process: "report_generation",
        employees_involved: 2,
        hours_saved_per_month: 60,
        cost_savings_annual: 12000,
      },
    ],
    document_queue: [
      {
        document_type: "invoice",
        confidence: 0.97,
        pages_processed: 142,
        fields_extracted: ["vendor", "amount", "due_date"],
      },
      {
        document_type: "contract",
        confidence: 0.94,
        pages_processed: 38,
        fields_extracted: ["parties", "term", "liability"],
      },
      {
        document_type: "receipt",
        confidence: 0.96,
        pages_processed: 210,
        fields_extracted: ["merchant", "total", "date"],
      },
    ],
    support_tickets: [
      {
        query: "Where is my order?",
        detected_intent: "order_status",
        sentiment: "frustrated",
        response: "Tracking link sent",
        escalated: false,
      },
      {
        query: "I want a refund",
        detected_intent: "refund",
        sentiment: "angry",
        response: "Refund initiated",
        escalated: true,
      },
      {
        query: "My account is locked",
        detected_intent: "account_access",
        sentiment: "neutral",
        response: "Unlocked with MFA reset",
        escalated: false,
      },
    ],
    supply_chain: [
      {
        chain_id: "SC-001",
        health_score: 92,
        lead_time_days: 5,
        risk_level: "low",
        bottlenecks: [],
      },
      {
        chain_id: "SC-002",
        health_score: 68,
        lead_time_days: 14,
        risk_level: "medium",
        bottlenecks: ["distributor delay"],
      },
      {
        chain_id: "SC-003",
        health_score: 85,
        lead_time_days: 7,
        risk_level: "low",
        bottlenecks: [],
      },
    ],
  },
};

async function fetchLiveDashboard(
  id: string,
  req: Request
): Promise<Record<string, unknown> | null> {
  try {
    const pythonSector = SECTOR_ALIASES[id] ?? id;
    const url = `${AEON_PYTHON_URL}/sectors/data/${encodeURIComponent(pythonSector)}/dashboard`;

    const headers: Record<string, string> = {};
    const authHeader = req.headers.get("authorization");
    const cookie = req.headers.get("cookie");
    if (authHeader) headers.Authorization = authHeader;
    if (cookie) headers.Cookie = cookie;

    const res = await fetch(url, { headers, cache: "no-store" });
    if (!res.ok) return null;
    const json = (await res.json()) as Record<string, unknown>;
    return json.ok === true ? json : null;
  } catch {
    return null;
  }
}

function transformLiveData(id: string, live: Record<string, unknown>): Record<string, unknown> {
  const keyMap = SECTOR_KEY_MAP[id] ?? {};
  const transformed: Record<string, unknown> = {};
  for (const [pythonKey, value] of Object.entries(live)) {
    if (pythonKey === "ok" || pythonKey === "source") continue;
    const frontendKey = keyMap[pythonKey] ?? pythonKey;
    transformed[frontendKey] = value;
  }
  return transformed;
}

export async function GET(req: Request, context: { params: Promise<{ id: string }> }) {
  const params = await context.params;
  const id = params.id;
  const session = await auth();
  const userId = (session?.user as any)?.id;
  const workspaceId = (session?.user as any)?.workspaceId;

  const staticData = dashboards[id];
  if (!staticData) {
    return NextResponse.json({ ok: false, error: "no dashboard for this app" }, { status: 404 });
  }

  let responseData: Record<string, unknown> = { ...staticData };
  let source = "static";

  const live = await fetchLiveDashboard(id, req);
  if (live) {
    const transformed = transformLiveData(id, live);
    responseData = { ...staticData, ...transformed, ok: true };
    source = (live.source as string) ?? "live";
  }

  logAudit({
    userId,
    email: session?.user?.email ?? undefined,
    action: "DASHBOARD",
    module: id,
    metadata: { endpoint: req.url, source },
  });

  logUsage({
    userId,
    workspaceId,
    action: "dashboard_view",
    module: id,
    quantity: 1,
  });

  return NextResponse.json({ ...responseData, _source: source });
}
