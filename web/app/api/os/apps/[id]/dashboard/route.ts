import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

/**
 * Deterministic mock dashboard data for each AEON OS vertical.
 * Returns rich, realistic data so the frontend dashboards render
 * without needing Python subprocesses (works on Vercel).
 */
const dashboards: Record<string, object> = {
  // ── Retail & Wholesale ─────────────────────────────────────────────
  retail: {
    ok: true,
    forecast: [
      { sku: "SKU-001", horizon_days: 30, forecast_units: 1240, confidence: 0.92, trend: "rising" },
      { sku: "SKU-042", horizon_days: 30, forecast_units: 680, confidence: 0.88, trend: "stable" },
      { sku: "SKU-099", horizon_days: 30, forecast_units: 2100, confidence: 0.95, trend: "rising" },
      { sku: "SKU-107", horizon_days: 30, forecast_units: 340, confidence: 0.76, trend: "declining" },
      { sku: "SKU-215", horizon_days: 30, forecast_units: 890, confidence: 0.84, trend: "stable" },
    ],
    inventory: {
      total_skus: 5,
      total_stock: 5250,
      low_stock_alerts: ["SKU-107"],
      overstock_alerts: ["SKU-099"],
      reorder_recommendations: [
        { sku: "SKU-107", suggested_order_qty: 200, priority: "high" },
      ],
    },
    supplier_risks: [
      { supplier: "Alpha Corp", risk_score: 0.15, status: "low", lead_time_days: 5 },
      { supplier: "Beta Logistics", risk_score: 0.42, status: "medium", lead_time_days: 12 },
      { supplier: "Gamma Wholesale", risk_score: 0.08, status: "low", lead_time_days: 3 },
      { supplier: "Delta Distributors", risk_score: 0.71, status: "high", lead_time_days: 21 },
    ],
    price_elasticity: {
      sku: "SKU-001",
      price_change_pct: 10,
      estimated_demand_change_pct: -4.2,
      elasticity: -0.42,
      recommendation: "inelastic — consider price increase",
    },
    personalizer: {
      segment: "premium_shopper",
      recommended_products: ["SKU-099", "SKU-001", "SKU-215"],
      personalized_discount: 0.1,
      engagement_score: 87,
    },
  },

  // ── Manufacturing & Engineering ─────────────────────────────────────
  manufacturing: {
    ok: true,
    maintenance: [
      { machine_id: "CNC-01", health_score: 92, days_until_maintenance: 45, status: "good" },
      { machine_id: "CNC-02", health_score: 67, days_until_maintenance: 12, status: "warning", alerts: ["bearing vibration"] },
      { machine_id: "CNC-03", health_score: 88, days_until_maintenance: 30, status: "good" },
      { machine_id: "CNC-04", health_score: 41, days_until_maintenance: 3, status: "critical", alerts: ["spindle overheat", "coolant leak"] },
    ],
    qc: [
      { batch_id: "B-998", defect_rate: 0.02, passed: true, inspected_units: 500 },
      { batch_id: "B-999", defect_rate: 0.07, passed: false, inspected_units: 500, failures: ["surface crack"] },
      { batch_id: "B-1000", defect_rate: 0.01, passed: true, inspected_units: 500 },
    ],
    logistics: [
      { route_id: "R-10", on_time_rate: 0.95, avg_delay_min: 4, incidents: 0 },
      { route_id: "R-11", on_time_rate: 0.78, avg_delay_min: 18, incidents: 2 },
      { route_id: "R-12", on_time_rate: 0.91, avg_delay_min: 7, incidents: 1 },
    ],
  },

  // ── Professional & Technical Services ───────────────────────────────
  professional: {
    ok: true,
    legal: [
      { document: "Vendor_NDA.pdf", clauses: 14, risk_flags: ["indemnification cap"], summary: "Standard NDA with 5-year term" },
      { document: "Client_MSA.pdf", clauses: 28, risk_flags: ["auto-renewal", "liability cap"], summary: "Master services agreement with SOW model" },
      { document: "Employment_Contract.pdf", clauses: 22, risk_flags: ["non-compete scope"], summary: "At-will employment with standard IP assignment" },
    ],
    accounting: [
      { invoice_id: "INV-102", status: "paid", amount: 12500, due_date: "2026-06-15", days_overdue: 0 },
      { invoice_id: "INV-103", status: "overdue", amount: 8400, due_date: "2026-05-30", days_overdue: 22 },
      { invoice_id: "INV-104", status: "pending", amount: 22000, due_date: "2026-07-01", days_overdue: 0 },
    ],
    data_management: [
      { dataset: "user_dump.csv", records: 15000, quality_score: 0.94, duplicates: 23, null_fields: 47 },
      { dataset: "transactions.csv", records: 85000, quality_score: 0.97, duplicates: 5, null_fields: 12 },
    ],
  },

  // ── Tourism & Hospitality ───────────────────────────────────────────
  tourism: {
    ok: true,
    bookings: [
      { property_id: "Hotel-Central", occupancy_rate: 0.82, revenue_per_room: 245, bookings_next_30d: 180 },
      { property_id: "Hotel-West", occupancy_rate: 0.68, revenue_per_room: 190, bookings_next_30d: 120 },
      { property_id: "Hotel-Airport", occupancy_rate: 0.91, revenue_per_room: 210, bookings_next_30d: 240 },
    ],
    pricing: [
      { room_type: "King Suite", optimal_price: 320, current_price: 299, demand_level: "high", recommendation: "increase" },
      { room_type: "Double Queen", optimal_price: 245, current_price: 259, demand_level: "medium", recommendation: "decrease" },
      { room_type: "Standard", optimal_price: 175, current_price: 169, demand_level: "low", recommendation: "hold" },
    ],
    concierge: [
      { guest_id: "G-445", request: "dining reservation", status: "fulfilled", response_time_min: 3 },
      { guest_id: "G-446", request: "housekeeping request", status: "fulfilled", response_time_min: 8 },
      { guest_id: "G-447", request: "transport to airport", status: "pending", response_time_min: 2 },
    ],
  },

  // ── Health & Medicine ───────────────────────────────────────────────
  health: {
    ok: true,
    diagnostics: [
      { symptoms: "fever, cough, fatigue", probability: "viral infection 0.78", severity: "moderate", recommendation: "rest and monitor" },
      { symptoms: "chest pain, shortness of breath", probability: "cardiac concern 0.65", severity: "high", recommendation: "immediate evaluation" },
      { symptoms: "headache, nausea", probability: "migraine 0.72", severity: "moderate", recommendation: "hydration and rest" },
    ],
    patient_vitals: [
      { patient_id: "P-1001", metric: "heart_rate", value: "72 bpm", status: "normal", trend: "stable" },
      { patient_id: "P-1001", metric: "blood_pressure_sys", value: "118 mmHg", status: "normal", trend: "stable" },
      { patient_id: "P-1001", metric: "oxygen_sat", value: "98%", status: "normal", trend: "stable" },
      { patient_id: "P-1002", metric: "heart_rate", value: "95 bpm", status: "elevated", trend: "rising" },
      { patient_id: "P-1002", metric: "blood_pressure_sys", value: "142 mmHg", status: "elevated", trend: "rising" },
      { patient_id: "P-1002", metric: "oxygen_sat", value: "94%", status: "acceptable", trend: "stable" },
      { patient_id: "P-1003", metric: "heart_rate", value: "88 bpm", status: "normal", trend: "stable" },
      { patient_id: "P-1003", metric: "blood_pressure_sys", value: "132 mmHg", status: "elevated", trend: "stable" },
      { patient_id: "P-1003", metric: "oxygen_sat", value: "96%", status: "normal", trend: "stable" },
    ],
    drug_interactions: [
      { drugs: "aspirin, warfarin", interaction_risk: "moderate", severity: "increased bleeding risk", recommendation: "monitor INR" },
      { drugs: "lisinopril, potassium", interaction_risk: "high", severity: "hyperkalemia risk", recommendation: "reduce potassium intake" },
      { drugs: "metformin", interaction_risk: "low", severity: "none significant", recommendation: "standard monitoring" },
    ],
    telehealth: [
      { symptoms: "chest pain", age: 65, triage: "emergency", priority: 1, recommended_action: "call 911" },
      { symptoms: "fever", age: 30, triage: "non-urgent", priority: 3, recommended_action: "schedule virtual visit" },
      { symptoms: "skin rash", age: 42, triage: "routine", priority: 4, recommended_action: "upload photos for dermatology review" },
    ],
  },

  // ── Transport & Logistics ───────────────────────────────────────────
  transport: {
    ok: true,
    traffic: [
      { zone: "downtown", congestion_index: 0.82, avg_speed_kmh: 18, recommendation: "divert to ring road" },
      { zone: "midtown", congestion_index: 0.65, avg_speed_kmh: 28, recommendation: "monitor" },
      { zone: "airport_corridor", congestion_index: 0.91, avg_speed_kmh: 12, recommendation: "activate bus lane" },
      { zone: "suburb_east", congestion_index: 0.38, avg_speed_kmh: 45, recommendation: "normal flow" },
    ],
    fleet: [
      { vehicles: 10, shifts: 3, utilization_rate: 0.87, idle_vehicles: 2, recommendation: "reduce 1 vehicle" },
      { vehicles: 8, shifts: 2, utilization_rate: 0.72, idle_vehicles: 3, recommendation: "reduce 2 vehicles" },
      { vehicles: 15, shifts: 3, utilization_rate: 0.93, idle_vehicles: 1, recommendation: "optimal" },
    ],
    route_plan: [
      { stops: "A,B,C,D,E", optimal_route: "A→C→E→D→B", total_distance_km: 42, estimated_time_min: 55, fuel_cost: 18.50 },
      { stops: "F,G,H,I,J", optimal_route: "F→H→J→I→G", total_distance_km: 38, estimated_time_min: 48, fuel_cost: 16.20 },
      { stops: "K,L,M,N,O", optimal_route: "K→M→O→N→L", total_distance_km: 56, estimated_time_min: 72, fuel_cost: 24.80 },
    ],
  },

  // ── Finance & Fintech ───────────────────────────────────────────────
  finance: {
    ok: true,
    risk_data: {
      asset: "S&P 500",
      portfolio_value: 500000,
      var_95_pct: 12500,
      sharpe_ratio: 1.45,
      volatility: 0.18,
      recommendation: "diversify fixed income",
    },
    payment_analysis: [
      { account_id: "ACC-1234", transactions_30d: 142, total_volume: 48500, avg_ticket: 341, success_rate: 0.98, chargeback_rate: 0.003 },
      { account_id: "ACC-5678", transactions_30d: 89, total_volume: 22300, avg_ticket: 251, success_rate: 0.95, chargeback_rate: 0.008 },
      { account_id: "ACC-9012", transactions_30d: 312, total_volume: 128000, avg_ticket: 410, success_rate: 0.99, chargeback_rate: 0.001 },
    ],
    market_data: {
      market: "NASDAQ",
      horizon_days: 90,
      forecast_trend: "bullish",
      confidence: 0.72,
      key_risk: "interest rate decision",
      recommended_allocation: { equities: 0.6, bonds: 0.25, cash: 0.15 },
    },
    fraud_cases: [
      { transaction_id: "TXN-5001", amount: 5000, location: "foreign", risk_score: 0.85, verdict: "blocked", reason: "geo anomaly" },
      { transaction_id: "TXN-5002", amount: 35, location: "local", risk_score: 0.05, verdict: "approved", reason: "" },
      { transaction_id: "TXN-5003", amount: 25000, location: "unknown", risk_score: 0.72, verdict: "flagged", reason: "amount exceeds threshold" },
    ],
    credit_applications: [
      { applicant_id: "APP-200", income: 75000, debt: 15000, history_years: 5, score: 720, verdict: "approved", suggested_limit: 25000 },
      { applicant_id: "APP-201", income: 45000, debt: 25000, history_years: 2, score: 580, verdict: "denied", reason: "high DTI ratio" },
      { applicant_id: "APP-202", income: 120000, debt: 10000, history_years: 8, score: 810, verdict: "approved", suggested_limit: 50000 },
    ],
  },

  // ── Cultural Heritage ───────────────────────────────────────────────
  cultural_heritage: {
    ok: true,
    visitor_data: [
      { venue: "National Museum", daily_visitors: 1200, satisfaction: 0.92, avg_dwell_min: 95, recommendation: "extend hours weekends" },
      { venue: "Modern Art Gallery", daily_visitors: 680, satisfaction: 0.88, avg_dwell_min: 72, recommendation: "new exhibition promo" },
      { venue: "History Center", daily_visitors: 450, satisfaction: 0.85, avg_dwell_min: 110, recommendation: "school program expansion" },
    ],
    heritage_sites: [
      { site: "Colosseum", preservation_status: "good", daily_capacity: 3000, visitor_satisfaction: 0.91, alert: "ongoing restoration sector C" },
      { site: "Machu Picchu", preservation_status: "at risk", daily_capacity: 2500, visitor_satisfaction: 0.94, alert: "erosion on main trail" },
      { site: "Angkor Wat", preservation_status: "fair", daily_capacity: 5000, visitor_satisfaction: 0.88, alert: "groundwater monitoring active" },
    ],
    exhibitions: [
      { theme: "Modern Art", projected_attendance: 80000, budget: 150000, roi_estimated: 2.4, recommendation: "proceed" },
      { theme: "Ancient Egypt", projected_attendance: 60000, budget: 120000, roi_estimated: 1.8, recommendation: "proceed" },
      { theme: "Space Exploration", projected_attendance: 45000, budget: 200000, roi_estimated: 0.9, recommendation: "reconsider budget" },
    ],
    virtual_tours: [
      { site: "Louvre Museum", interest: "art", tour_duration_min: 35, engagement_score: 0.94, languages_available: 8 },
      { site: "British Museum", interest: "history", tour_duration_min: 40, engagement_score: 0.91, languages_available: 6 },
      { site: "Uffizi Gallery", interest: "architecture", tour_duration_min: 28, engagement_score: 0.87, languages_available: 5 },
    ],
  },

  // ── Utilities & Public Sector ────────────────────────────────────────
  utilities: {
    ok: true,
    resource_data: [
      { resource: "water", demand: 1000, supply: 850, deficit: 150, status: "critical", recommendation: "reduce non-essential use" },
      { resource: "electricity", demand: 500, supply: 480, deficit: 20, status: "warning", recommendation: "peak hour load shedding" },
      { resource: "natural_gas", demand: 300, supply: 320, deficit: 0, status: "good", recommendation: "normal operations" },
    ],
    public_services: [
      { service: "waste_collection", kpi: "on-time rate", value: 0.89, status: "acceptable", target: 0.95 },
      { service: "street_lighting", kpi: "uptime", value: 0.97, status: "good", target: 0.95 },
      { service: "public_transport", kpi: "punctuality", value: 0.82, status: "needs improvement", target: 0.90 },
    ],
    waste_data: [
      { district: "Zone A", collection_rate: 0.92, recycling_rate: 0.35, diverted_landfill_tons: 120, recommendation: "expand recycling" },
      { district: "Zone B", collection_rate: 0.78, recycling_rate: 0.22, diverted_landfill_tons: 65, recommendation: "add collection routes" },
      { district: "Zone C", collection_rate: 0.95, recycling_rate: 0.41, diverted_landfill_tons: 180, recommendation: "model district" },
    ],
    energy_grid: [
      { region: "North Grid", load_mw: 245, capacity_mw: 280, renewable_pct: 0.38, stability: "stable" },
      { region: "South Grid", load_mw: 312, capacity_mw: 300, renewable_pct: 0.22, stability: "overloaded", alert: "peak load 104%" },
      { region: "East Grid", load_mw: 198, capacity_mw: 260, renewable_pct: 0.45, stability: "stable" },
    ],
  },

  // ── SME Business Suite ───────────────────────────────────────────────
  sme: {
    ok: true,
    workflow_data: [
      { process: "invoice_approval", employees: 5, cycle_time_hours: 8, automation_rate: 0.6, bottleneck: "manager approval" },
      { process: "employee_onboarding", employees: 3, cycle_time_hours: 24, automation_rate: 0.4, bottleneck: "IT setup" },
      { process: "report_generation", employees: 2, cycle_time_hours: 3, automation_rate: 0.8, bottleneck: "" },
    ],
    document_queue: [
      { type: "invoice", pending: 23, processed_today: 15, accuracy_rate: 0.97, avg_extraction_time_s: 2.1 },
      { type: "contract", pending: 8, processed_today: 5, accuracy_rate: 0.94, avg_extraction_time_s: 4.5 },
      { type: "receipt", pending: 45, processed_today: 30, accuracy_rate: 0.96, avg_extraction_time_s: 1.2 },
    ],
    support_tickets: [
      { query: "Where is my order?", tier: "standard", sentiment: "frustrated", resolution: "tracking link sent", satisfaction: 4 },
      { query: "I want a refund", tier: "premium", sentiment: "angry", resolution: "refund initiated", satisfaction: 5 },
      { query: "My account is locked", tier: "standard", sentiment: "neutral", resolution: "unlocked with MFA reset", satisfaction: 4 },
    ],
    supply_chain: [
      { chain_id: "SC-001", depth: 3, risk_score: 0.22, status: "low", lead_time_days: 5, nodes: ["supplier", "warehouse", "retailer"] },
      { chain_id: "SC-002", depth: 3, risk_score: 0.58, status: "medium", lead_time_days: 14, nodes: ["supplier", "distributor", "warehouse", "retailer"] },
      { chain_id: "SC-003", depth: 3, risk_score: 0.34, status: "low", lead_time_days: 7, nodes: ["supplier", "fulfillment", "retailer"] },
    ],
  },
};

export async function GET(
  _req: Request,
  { params }: { params: { id: string } },
) {
  const id = params.id;
  const data = dashboards[id];
  if (!data) {
    return NextResponse.json(
      { ok: false, error: "no dashboard for this app" },
      { status: 404 },
    );
  }
  return NextResponse.json(data);
}
