"use client";

import { useEffect, useState } from "react";

// ════════════════════════════════════════════════════════════════
// Shared Types
// ════════════════════════════════════════════════════════════════

export type KPIData = { title: string; value: string | number; sub?: string; color?: string };

export type DashboardData = {
  ok: boolean;
  threats?: Array<{
    id: string;
    indicator: string;
    type: string;
    severity: string;
    status: string;
  }>;
  vulnerabilities?: Array<{
    cve: string;
    severity: string;
    cvss: number;
    affected: string;
    patch_available: boolean;
  }>;
  ip_reputation?: {
    score: number;
    known_malicious: boolean;
    source_countries: string[];
    last_seen_days: number;
  };
  compliance?: { framework: string; score: number; maturity: string; gaps: string[] };
  security_news?: Array<{ title: string; url: string }>;
  forecast?: Array<{
    sku: string;
    current_stock: number;
    projected_demand: number;
    recommended_order_qty: number;
    confidence: number;
  }>;
  inventory?: {
    alerts: Array<{ sku: string; status: string; days_remaining: number }>;
    reorder_recommendations: Array<{ sku: string; qty: number; supplier: string }>;
    healthy: Array<{ sku: string; status: string; days_supply: number }>;
    summary: { total_skus: number; stockout_risks: number; overstocks: number };
  };
  supplier_risks?: Array<{
    supplier: string;
    risk_score: number;
    classification: string;
    on_time_delivery_pct: number;
  }>;
  price_elasticity?: {
    sku: string;
    price_change_pct: number;
    elasticity: number;
    projected_demand_change_pct: number;
  };
  personalizer?: {
    segment: string;
    recommended_products: string[];
    estimated_conversion_lift_pct: number;
  };
  maintenance?: Array<{
    machine_id: string;
    status: string;
    temp_c: number;
    vibration_hz: number;
    failure_risk_pct: number;
    days_to_failure: number;
  }>;
  qc?: Array<{
    batch_id: string;
    items_scanned: number;
    defects_found: number;
    defect_rate: number;
    status: string;
  }>;
  logistics?: Array<{
    route_id: string;
    status: string;
    eta_days: number;
    reroute_cost_usd: number;
  }>;
  legal?: Array<{ doc: string; type: string; risk_score: string; obligations: string[] }>;
  accounting?: Array<{
    invoice_id: string;
    vendor: string;
    amount: number;
    anomalies_detected: boolean;
    auto_approved: boolean;
  }>;
  data_management?: Array<{ dataset: string; pii_records_found: number; compliance: string }>;
  bookings?: Array<{
    property: string;
    occupancy_pct: number;
    predictive_no_shows: number;
    net_expected_occupancy: number;
  }>;
  pricing?: Array<{ room: string; base_price: number; recommended_price: number; reason: string }>;
  concierge?: Array<{
    guest_id: string;
    sentiment: string;
    intent: string;
    automated_response: string;
    upsell?: string | null;
  }>;
  diagnostics?: Array<{
    analyzed_symptoms: string;
    possible_conditions: { name: string; probability: number; severity: string; action: string }[];
    urgency: string;
    recommendation: string;
  }>;
  patient_vitals?: Array<{
    patient_id: string;
    metric: string;
    baseline: number;
    current: number;
    trend: string;
    alert: boolean;
  }>;
  drug_interactions?: Array<{
    medications: string[];
    interactions_found: number;
    interactions: { drugs: string[]; severity: string; warning: string }[];
  }>;
  telehealth?: Array<{ symptoms: string; age: number; urgency: string; recommendation: string }>;
  traffic?: Array<{
    zone: string;
    current_congestion: number;
    predicted_improvement: string;
    incident_nearby: boolean;
  }>;
  fleet?: Array<{
    vehicles_available: number;
    shifts: number;
    utilization_pct: number;
    recommendation: string;
  }>;
  route_plan?: Array<{
    stops: string[];
    estimated_distance_km: number;
    estimated_time_min: number;
    fuel_cost_est: number;
  }>;
  risk_data?: {
    asset: string;
    portfolio_value: number;
    var_95_1d: number;
    var_95_pct: number;
    sharpe_estimate: number;
    beta: number;
    risk_rating: string;
    diversification_score: number;
    recommendation: string;
  };
  payment_analysis?: Array<{
    account_id: string;
    total_transactions: number;
    total_volume: number;
    anomaly_count: number;
    spending_trend: string;
  }>;
  market_data?: {
    market: string;
    predicted_direction: string;
    confidence: number;
    price_target_pct: number;
    volatility_forecast: string;
  };
  fraud_cases?: Array<{
    transaction_id: string;
    amount: number;
    fraud_score: number;
    risk_level: string;
    action: string;
  }>;
  credit_applications?: Array<{
    applicant_id: string;
    credit_score: number;
    rating: string;
    approval_probability: number;
  }>;
  visitor_data?: Array<{
    venue: string;
    daily_visitors: number;
    engagement_score: number;
    recommended_strategies: string[];
  }>;
  heritage_sites?: Array<{
    site: string;
    era: string;
    significance: string;
    annual_visitors: number;
    conservation_status: string;
  }>;
  exhibitions?: Array<{
    theme: string;
    recommended_duration_days: number;
    estimated_visitors: number;
    ticket_price: number;
    projected_revenue: number;
  }>;
  virtual_tours?: Array<{
    site: string;
    interest: string;
    narration: string;
    audio_duration_seconds: number;
  }>;
  resource_data?: Array<{
    resource: string;
    demand: number;
    supply: number;
    deficit: number;
    status: string;
  }>;
  public_services?: Array<{
    service: string;
    kpi_score: number;
    status: string;
    citizen_satisfaction: number;
    trend: string;
  }>;
  waste_data?: Array<{
    district: string;
    total_waste_tons: number;
    recycled_pct: number;
    landfill_pct: number;
    collection_efficiency: number;
  }>;
  energy_grid?: Array<{
    region: string;
    current_load_mw: number;
    capacity_mw: number;
    utilization_pct: number;
    renewable_share_pct: number;
    status: string;
  }>;
  workflow_data?: Array<{
    process: string;
    employees_involved: number;
    hours_saved_per_month: number;
    cost_savings_annual: number;
  }>;
  document_queue?: Array<{
    document_type: string;
    confidence: number;
    pages_processed: number;
    fields_extracted: string[];
  }>;
  support_tickets?: Array<{
    query: string;
    detected_intent: string;
    sentiment: string;
    response: string;
    escalated: boolean;
  }>;
  supply_chain?: Array<{
    chain_id: string;
    health_score: number;
    lead_time_days: number;
    risk_level: string;
    bottlenecks: string[];
  }>;
};

// ════════════════════════════════════════════════════════════════
// Shared Widgets
// ════════════════════════════════════════════════════════════════

export function KPICard({
  title,
  value,
  sub,
  color = "var(--success)",
}: KPIData & { color?: string }) {
  return (
    <div className="module-kpi-card">
      <div className="module-kpi-dot" style={{ background: color }} />
      <div>
        <div className="module-kpi-title">{title}</div>
        <div className="module-kpi-value">{value}</div>
        {sub && <div className="module-kpi-sub">{sub}</div>}
      </div>
    </div>
  );
}

export function Widget({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="module-widget">
      <h3>{title}</h3>
      {children}
    </div>
  );
}

export function Badge({
  children,
  variant = "ok",
}: {
  children: React.ReactNode;
  variant?: "ok" | "warn" | "danger";
}) {
  return <span className={`module-badge ${variant}`}>{children}</span>;
}

export function SimpleLineChart({
  data,
  xKey,
  yKeys,
}: {
  data: any[];
  xKey: string;
  yKeys: { key: string; color: string; label: string }[];
}) {
  const width = 500;
  const height = 200;
  const pad = { top: 20, right: 20, bottom: 40, left: 50 };
  const chartW = width - pad.left - pad.right;
  const chartH = height - pad.top - pad.bottom;
  const values = data.flatMap((d) => yKeys.map((yk) => Number(d[yk.key]) || 0));
  const maxVal = Math.max(...values, 1);

  const xFor = (i: number) => pad.left + (i * chartW) / (data.length - 1 || 1);
  const yFor = (v: number) => pad.top + chartH - (v / maxVal) * chartH;

  return (
    <div>
      <svg viewBox={`0 0 ${width} ${height}`} className="module-chart">
        <line
          x1={pad.left}
          y1={height - pad.bottom}
          x2={width - pad.right}
          y2={height - pad.bottom}
          stroke="var(--border-strong)"
        />
        <line
          x1={pad.left}
          y1={pad.top}
          x2={pad.left}
          y2={height - pad.bottom}
          stroke="var(--border-strong)"
        />
        {yKeys.map((yk) => {
          const points = data.map((d, i) => [xFor(i), yFor(Number(d[yk.key]) || 0)]);
          const path = points.map((p, i) => `${i === 0 ? "M" : "L"} ${p[0]} ${p[1]}`).join(" ");
          return (
            <g key={yk.key}>
              <path d={path} fill="none" stroke={yk.color} strokeWidth={2.5} />
              {points.map((p, i) => (
                <circle key={i} cx={p[0]} cy={p[1]} r={3} fill={yk.color} />
              ))}
            </g>
          );
        })}
        {data.map((d, i) => (
          <text
            key={i}
            x={xFor(i)}
            y={height - 10}
            textAnchor="middle"
            fill="var(--fg-mute)"
            fontSize={10}
            transform={`rotate(-25, ${xFor(i)}, ${height - 10})`}
          >
            {d[xKey]}
          </text>
        ))}
      </svg>
      <div className="module-legend">
        {yKeys.map((yk) => (
          <span key={yk.key}>
            <i style={{ background: yk.color }} /> {yk.label}
          </span>
        ))}
      </div>
    </div>
  );
}

export function DataTable({
  data,
  columns,
}: {
  data: any[];
  columns: { key: string; label: string; render?: (row: any) => React.ReactNode }[];
}) {
  return (
    <table className="module-table">
      <thead>
        <tr>
          {columns.map((c) => (
            <th key={c.key}>{c.label}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {data.map((row, i) => (
          <tr key={i}>
            {columns.map((c) => (
              <td key={c.key}>{c.render ? c.render(row) : row[c.key]}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// ════════════════════════════════════════════════════════════════
// useDashboard Hook
// ════════════════════════════════════════════════════════════════

export function useDashboard(appId: string) {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!appId || ["cybersecurity"].includes(appId)) {
      setData(null);
      return;
    }
    setLoading(true);
    fetch(`/api/os/apps/${appId}/dashboard`, { cache: "no-store" })
      .then((r) => r.json())
      .then((d: DashboardData) => {
        if (d.ok) setData(d);
      })
      .finally(() => setLoading(false));
  }, [appId]);

  return { data, loading };
}
