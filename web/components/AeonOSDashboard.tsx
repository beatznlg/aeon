"use client";

import { useEffect, useState } from "react";

// =================== Shared Types ===================
export type KPIData = { title: string; value: string | number; sub?: string; color?: string };

export type DashboardData = {
  ok: boolean;
  // cybersecurity
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
  compliance?: {
    framework: string;
    score: number;
    maturity: string;
    gaps: string[];
  };
  security_news?: Array<{ title: string; url: string }>;
  // retail
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
  // manufacturing
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
  // professional
  legal?: Array<{
    doc: string;
    type: string;
    risk_score: string;
    obligations: string[];
  }>;
  accounting?: Array<{
    invoice_id: string;
    vendor: string;
    amount: number;
    anomalies_detected: boolean;
    auto_approved: boolean;
  }>;
  data_management?: Array<{
    dataset: string;
    pii_records_found: number;
    compliance: string;
  }>;
  // tourism
  bookings?: Array<{
    property: string;
    occupancy_pct: number;
    predictive_no_shows: number;
    net_expected_occupancy: number;
  }>;
  pricing?: Array<{
    room: string;
    base_price: number;
    recommended_price: number;
    reason: string;
  }>;
  concierge?: Array<{
    guest_id: string;
    sentiment: string;
    intent: string;
    automated_response: string;
    upsell?: string | null;
  }>;
  // health
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
  telehealth?: Array<{
    symptoms: string;
    age: number;
    urgency: string;
    recommendation: string;
  }>;
  // transport
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
  // finance
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
  // cultural heritage
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
  // utilities
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
  // sme
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

// =================== Shared Widgets ===================
export function KPICard({ title, value, sub, color = "var(--success)" }: KPIData & { color?: string }) {
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

export function Badge({ children, variant = "ok" }: { children: React.ReactNode; variant?: "ok" | "warn" | "danger" }) {
  return <span className={`module-badge ${variant}`}>{children}</span>;
}

export function SimpleLineChart({ data, xKey, yKeys }: { data: any[]; xKey: string; yKeys: { key: string; color: string; label: string }[] }) {
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
        <line x1={pad.left} y1={height - pad.bottom} x2={width - pad.right} y2={height - pad.bottom} stroke="var(--border-strong)" />
        <line x1={pad.left} y1={pad.top} x2={pad.left} y2={height - pad.bottom} stroke="var(--border-strong)" />
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
          <text key={i} x={xFor(i)} y={height - 10} textAnchor="middle" fill="var(--fg-mute)" fontSize={10} transform={`rotate(-25, ${xFor(i)}, ${height - 10})`}>
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

export function DataTable({ data, columns }: { data: any[]; columns: { key: string; label: string; render?: (row: any) => React.ReactNode }[] }) {
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

// =================== Module Dashboards ===================
export function CyberSecurityDashboard({ data }: { data: DashboardData }) {
  const threats = data.threats || [];
  const vulns = data.vulnerabilities || [];
  const ip = data.ip_reputation;
  const compliance = data.compliance;
  const news = data.security_news || [];
  const criticalVulns = vulns.filter((v) => v.severity.toLowerCase() === "critical").length;
  const activeThreats = threats.filter((t) => t.status === "blocked" || t.status === "quarantined").length;

  return (
    <section className="module-dashboard">
      <div className="module-dashboard-header">
        <h2>🛡️ Security Command Center</h2>
        <p>Threat intelligence, vulnerability tracking, IP reputation, and compliance posture.</p>
      </div>
      <div className="module-kpi-row">
        <KPICard title="Active Threats" value={activeThreats} sub="Blocked / quarantined" color={activeThreats > 0 ? "var(--danger)" : "var(--success)"} />
        <KPICard title="Critical Vulns" value={criticalVulns} sub="Need immediate patch" color={criticalVulns > 0 ? "var(--danger)" : "var(--success)"} />
        {ip && <KPICard title="IP Rep Score" value={ip.score.toFixed(2)} sub="0-1 reputation" color={ip.score > 0.5 ? "var(--danger)" : "var(--success)"} />}
        {compliance && <KPICard title="Compliance" value={`${compliance.score}%`} sub={compliance.framework} />}
      </div>
      <div className="module-widgets-grid">
        <Widget title="Threat Intelligence">
          <DataTable data={threats} columns={[
            { key: "indicator", label: "Indicator" },
            { key: "type", label: "Type" },
            { key: "severity", label: "Severity", render: (r) => <Badge variant={r.severity === "critical" ? "danger" : r.severity === "high" ? "warn" : "ok"}>{r.severity}</Badge> },
            { key: "status", label: "Status", render: (r) => <Badge variant={r.status === "blocked" || r.status === "quarantined" ? "ok" : "warn"}>{r.status}</Badge> },
          ]} />
        </Widget>
        <Widget title="Vulnerability Scan">
          <DataTable data={vulns} columns={[
            { key: "cve", label: "CVE" },
            { key: "affected", label: "Affected" },
            { key: "cvss", label: "CVSS" },
            { key: "severity", label: "Severity", render: (r) => <Badge variant={r.severity === "Critical" ? "danger" : r.severity === "High" ? "warn" : "ok"}>{r.severity}</Badge> },
            { key: "patch_available", label: "Patch", render: (r) => r.patch_available ? "✓" : "✗" },
          ]} />
        </Widget>
        {compliance && (
          <Widget title="Compliance Posture">
            <div className="module-elasticity">
              <div><span>Framework</span><strong>{compliance.framework}</strong></div>
              <div><span>Score</span><strong>{compliance.score}%</strong></div>
              <div><span>Maturity</span><strong>{compliance.maturity}</strong></div>
            </div>
            <div className="module-alert-section" style={{ marginTop: 12 }}>
              <h4>Gaps</h4>
              {compliance.gaps.map((g, i) => (
                <div key={i} className="module-alert danger">{g}</div>
              ))}
            </div>
          </Widget>
        )}
        {ip && (
          <Widget title="IP Reputation">
            <div className="module-elasticity">
              <div><span>Score</span><strong>{ip.score.toFixed(2)}</strong></div>
              <div><span>Known Malicious</span><strong>{ip.known_malicious ? "Yes" : "No"}</strong></div>
              <div><span>Sources</span><strong>{ip.source_countries.join(", ")}</strong></div>
              <div><span>Last Seen</span><strong>{ip.last_seen_days}d ago</strong></div>
            </div>
          </Widget>
        )}
        <Widget title="Security News">
          <ul className="module-product-list">
            {news.map((n, i) => (
              <li key={i}><a href={n.url} style={{ color: "var(--accent)" }}>{n.title}</a></li>
            ))}
          </ul>
        </Widget>
      </div>
    </section>
  );
}

export function RetailDashboard({ data }: { data: DashboardData }) {
  const forecast = data.forecast || [];
  const inventory = data.inventory || { alerts: [], reorder_recommendations: [], healthy: [], summary: { total_skus: 0, stockout_risks: 0, overstocks: 0 } };
  const suppliers = data.supplier_risks || [];
  const elasticity = data.price_elasticity;
  const personalizer = data.personalizer;

  return (
    <section className="module-dashboard">
      <div className="module-dashboard-header">
        <h2>Commerce Command Center</h2>
        <p>Real-time forecasting, inventory, supplier risk, and storefront personalization.</p>
      </div>
      <div className="module-kpi-row">
        <KPICard title="Projected Demand" value={forecast.reduce((s, f) => s + f.projected_demand, 0).toLocaleString()} sub="Next 30 days" />
        <KPICard title="Stockout Risks" value={inventory.summary.stockout_risks} sub="SKUs need reorder" color="var(--danger)" />
        <KPICard title="Avg Supplier Risk" value={Math.round(suppliers.reduce((s, r) => s + r.risk_score, 0) / (suppliers.length || 1))} sub="0-100 scale" color="var(--accent-2)" />
        {personalizer && <KPICard title="Conversion Lift" value={`+${personalizer.estimated_conversion_lift_pct}%`} sub={personalizer.segment} />}
      </div>
      <div className="module-widgets-grid">
        <Widget title="30-Day Demand Forecast">
          <SimpleLineChart data={forecast} xKey="sku" yKeys={[
            { key: "current_stock", color: "var(--fg-soft)", label: "Current Stock" },
            { key: "projected_demand", color: "var(--success)", label: "Projected Demand" },
            { key: "recommended_order_qty", color: "var(--accent)", label: "Recommended Order" },
          ]} />
        </Widget>
        <Widget title="Inventory Status">
          <div className="module-kpi-row">
            <KPICard title="Total SKUs" value={inventory.summary.total_skus} />
            <KPICard title="Stockout Risks" value={inventory.summary.stockout_risks} color="var(--danger)" />
            <KPICard title="Overstocks" value={inventory.summary.overstocks} color="var(--accent-2)" />
          </div>
          {inventory.alerts.length > 0 && (
            <div className="module-alert-section">
              <h4>Alerts</h4>
              {inventory.alerts.map((a) => (
                <div key={a.sku} className="module-alert danger"><strong>{a.sku}</strong> — {a.days_remaining} days remaining</div>
              ))}
            </div>
          )}
        </Widget>
        <Widget title="Supplier Risk">
          <DataTable data={suppliers} columns={[
            { key: "supplier", label: "Supplier" },
            { key: "risk_score", label: "Risk Score" },
            { key: "classification", label: "Status", render: (r) => <Badge variant={r.risk_score > 70 ? "danger" : r.risk_score > 45 ? "warn" : "ok"}>{r.classification}</Badge> },
            { key: "on_time_delivery_pct", label: "On-Time %", render: (r) => `${r.on_time_delivery_pct}%` },
          ]} />
        </Widget>
        {elasticity && (
          <Widget title="Price Elasticity">
            <div className="module-elasticity">
              <div><span>SKU</span><strong>{elasticity.sku}</strong></div>
              <div><span>Elasticity</span><strong>{elasticity.elasticity.toFixed(2)}</strong></div>
              <div><span>Price Change</span><strong>{elasticity.price_change_pct}%</strong></div>
              <div><span>Demand Impact</span><strong>{elasticity.projected_demand_change_pct}%</strong></div>
            </div>
          </Widget>
        )}
        {personalizer && (
          <Widget title="Storefront Personalization">
            <p className="module-segment">Segment: <strong>{personalizer.segment}</strong></p>
            <ul className="module-product-list">{personalizer.recommended_products.map((p) => <li key={p}>{p}</li>)}</ul>
            <div className="module-conversion">Est. conversion lift: +{personalizer.estimated_conversion_lift_pct}%</div>
          </Widget>
        )}
      </div>
    </section>
  );
}

export function ManufacturingDashboard({ data }: { data: DashboardData }) {
  const maintenance = data.maintenance || [];
  const qc = data.qc || [];
  const logistics = data.logistics || [];
  const atRisk = maintenance.filter((m) => m.failure_risk_pct > 60).length;
  const delayedRoutes = logistics.filter((l) => l.status === "delayed").length;

  return (
    <section className="module-dashboard">
      <div className="module-dashboard-header">
        <h2>Factory Command Center</h2>
        <p>Predictive maintenance, quality control, and smart logistics monitoring.</p>
      </div>
      <div className="module-kpi-row">
        <KPICard title="Machines at Risk" value={atRisk} sub="Need attention" color={atRisk > 0 ? "var(--danger)" : "var(--success)"} />
        <KPICard title="Avg Defect Rate" value={`${(qc.reduce((s, q) => s + q.defect_rate, 0) / (qc.length || 1) * 100).toFixed(2)}%`} sub="Across batches" />
        <KPICard title="Logistics Delays" value={delayedRoutes} sub="Routes delayed" color={delayedRoutes > 0 ? "var(--danger)" : "var(--success)"} />
      </div>
      <div className="module-widgets-grid">
        <Widget title="Machine Health">
          <DataTable data={maintenance} columns={[
            { key: "machine_id", label: "Machine" },
            { key: "temp_c", label: "Temp °C" },
            { key: "vibration_hz", label: "Vibration Hz" },
            { key: "failure_risk_pct", label: "Risk %" },
            { key: "days_to_failure", label: "Days to Failure" },
            { key: "status", label: "Status", render: (r) => <Badge variant={r.status === "critical" ? "danger" : r.status === "warning" ? "warn" : "ok"}>{r.status}</Badge> },
          ]} />
        </Widget>
        <Widget title="Quality Control">
          <DataTable data={qc} columns={[
            { key: "batch_id", label: "Batch" },
            { key: "items_scanned", label: "Items Scanned" },
            { key: "defects_found", label: "Defects" },
            { key: "defect_rate", label: "Defect Rate", render: (r) => `${(r.defect_rate * 100).toFixed(2)}%` },
            { key: "status", label: "Status", render: (r) => <Badge variant={r.status === "fail" ? "danger" : "ok"}>{r.status}</Badge> },
          ]} />
        </Widget>
        <Widget title="Smart Logistics">
          <DataTable data={logistics} columns={[
            { key: "route_id", label: "Route" },
            { key: "status", label: "Status", render: (r) => <Badge variant={r.status === "delayed" ? "warn" : "ok"}>{r.status}</Badge> },
            { key: "eta_days", label: "ETA Days" },
            { key: "reroute_cost_usd", label: "Reroute Cost", render: (r) => `$${r.reroute_cost_usd}` },
          ]} />
        </Widget>
      </div>
    </section>
  );
}

export function ProfessionalDashboard({ data }: { data: DashboardData }) {
  const legal = data.legal || [];
  const accounting = data.accounting || [];
  const dataMgmt = data.data_management || [];
  const highRisk = legal.filter((l) => l.risk_score === "high").length;
  const anomalies = accounting.filter((a) => a.anomalies_detected).length;

  return (
    <section className="module-dashboard">
      <div className="module-dashboard-header">
        <h2>Professional Services Hub</h2>
        <p>Automated contract review, accounting audit, and data compliance.</p>
      </div>
      <div className="module-kpi-row">
        <KPICard title="Contracts Reviewed" value={legal.length} sub="In queue" />
        <KPICard title="High-Risk Clauses" value={highRisk} sub="Need review" color={highRisk > 0 ? "var(--danger)" : "var(--success)"} />
        <KPICard title="Invoice Anomalies" value={anomalies} sub="Flagged" color={anomalies > 0 ? "var(--danger)" : "var(--success)"} />
      </div>
      <div className="module-widgets-grid">
        <Widget title="Legal Document Queue">
          <DataTable data={legal} columns={[
            { key: "doc", label: "Document" },
            { key: "type", label: "Type" },
            { key: "risk_score", label: "Risk", render: (r) => <Badge variant={r.risk_score === "high" ? "danger" : r.risk_score === "medium" ? "warn" : "ok"}>{r.risk_score}</Badge> },
            { key: "obligations", label: "Obligations", render: (r) => r.obligations.join(", ") },
          ]} />
        </Widget>
        <Widget title="Accounting Audit">
          <DataTable data={accounting} columns={[
            { key: "invoice_id", label: "Invoice" },
            { key: "vendor", label: "Vendor" },
            { key: "amount", label: "Amount", render: (r) => `$${r.amount.toLocaleString()}` },
            { key: "auto_approved", label: "Auto-Approved", render: (r) => (r.auto_approved ? "Yes" : "No") },
            { key: "anomalies_detected", label: "Anomaly", render: (r) => <Badge variant={r.anomalies_detected ? "danger" : "ok"}>{r.anomalies_detected ? "Yes" : "No"}</Badge> },
          ]} />
        </Widget>
        <Widget title="Data Compliance">
          <DataTable data={dataMgmt} columns={[
            { key: "dataset", label: "Dataset" },
            { key: "pii_records_found", label: "PII Records" },
            { key: "compliance", label: "Compliance", render: (r) => <Badge variant={r.compliance === "GDPR-ready" ? "ok" : "warn"}>{r.compliance}</Badge> },
          ]} />
        </Widget>
      </div>
    </section>
  );
}

export function TourismDashboard({ data }: { data: DashboardData }) {
  const bookings = data.bookings || [];
  const pricing = data.pricing || [];
  const concierge = data.concierge || [];
  const avgOccupancy = Math.round(bookings.reduce((s, b) => s + b.occupancy_pct, 0) / (bookings.length || 1));
  const avgPrice = Math.round(pricing.reduce((s, p) => s + p.recommended_price, 0) / (pricing.length || 1));

  return (
    <section className="module-dashboard">
      <div className="module-dashboard-header">
        <h2>Hospitality Command Center</h2>
        <p>Booking optimization, dynamic pricing, and automated concierge.</p>
      </div>
      <div className="module-kpi-row">
        <KPICard title="Avg Occupancy" value={`${avgOccupancy}%`} sub="Across properties" />
        <KPICard title="Avg Recommended Price" value={`$${avgPrice}`} sub="Per night" />
        <KPICard title="Guest Requests" value={concierge.length} sub="Triaged" />
      </div>
      <div className="module-widgets-grid">
        <Widget title="Booking Optimization">
          <DataTable data={bookings} columns={[
            { key: "property", label: "Property" },
            { key: "occupancy_pct", label: "Occupancy %" },
            { key: "predictive_no_shows", label: "Predicted No-Shows" },
            { key: "net_expected_occupancy", label: "Net Expected Occupancy %" },
          ]} />
        </Widget>
        <Widget title="Dynamic Pricing">
          <DataTable data={pricing} columns={[
            { key: "room", label: "Room" },
            { key: "base_price", label: "Base Price", render: (r) => `$${r.base_price}` },
            { key: "recommended_price", label: "Recommended", render: (r) => `$${r.recommended_price}` },
            { key: "reason", label: "Reason" },
          ]} />
        </Widget>
        <Widget title="Concierge Triage">
          <DataTable data={concierge} columns={[
            { key: "guest_id", label: "Guest" },
            { key: "intent", label: "Intent" },
            { key: "sentiment", label: "Sentiment", render: (r) => <Badge variant={r.sentiment === "negative" ? "danger" : r.sentiment === "positive" ? "ok" : "warn"}>{r.sentiment}</Badge> },
            { key: "automated_response", label: "Auto Response" },
            { key: "upsell", label: "Upsell", render: (r) => r.upsell || "—" },
          ]} />
        </Widget>
      </div>
    </section>
  );
}

// =================== New Vertical Dashboards ===================

export function HealthDashboard({ data }: { data: DashboardData }) {
  const diagnostics = data.diagnostics || [];
  const vitals = data.patient_vitals || [];
  const interactions = data.drug_interactions || [];
  const telehealth = data.telehealth || [];
  const urgentCases = diagnostics.filter((d) => d.urgency === "high").length;
  const alerts = vitals.filter((v) => v.alert).length;

  return (
    <section className="module-dashboard">
      <div className="module-dashboard-header">
        <h2>🏥 Health Command Center</h2>
        <p>AI diagnostics, patient monitoring, drug interaction checks, and telehealth triage.</p>
      </div>
      <div className="module-kpi-row">
        <KPICard title="Cases Triaged" value={diagnostics.length} sub="This shift" />
        <KPICard title="Urgent Cases" value={urgentCases} sub="Needs immediate attention" color={urgentCases > 0 ? "var(--danger)" : "var(--success)"} />
        <KPICard title="Vital Alerts" value={alerts} sub="Flagged patients" color={alerts > 0 ? "var(--danger)" : "var(--success)"} />
        <KPICard title="Telehealth Eligible" value={telehealth.filter((t) => t.urgency !== "emergent").length} sub="Virtual visits" />
      </div>
      <div className="module-widgets-grid">
        <Widget title="Diagnostic Analysis">
          <DataTable data={diagnostics} columns={[
            { key: "analyzed_symptoms", label: "Symptoms" },
            { key: "urgency", label: "Urgency", render: (r) => <Badge variant={r.urgency === "high" ? "danger" : r.urgency === "moderate" ? "warn" : "ok"}>{r.urgency}</Badge> },
            { key: "recommendation", label: "Recommendation" },
          ]} />
        </Widget>
        <Widget title="Patient Vitals Monitor">
          <DataTable data={vitals} columns={[
            { key: "patient_id", label: "Patient" },
            { key: "metric", label: "Metric" },
            { key: "current", label: "Current", render: (r) => `${r.current} (baseline: ${r.baseline})` },
            { key: "trend", label: "Trend", render: (r) => <Badge variant={r.trend === "rising" ? "warn" : r.trend === "falling" ? "danger" : "ok"}>{r.trend}</Badge> },
            { key: "alert", label: "Alert", render: (r) => r.alert ? <Badge variant="danger">ALERT</Badge> : "—" },
          ]} />
        </Widget>
        <Widget title="Drug Interaction Check">
          {interactions.map((d, i) => (
            <div key={i} className="module-alert-section">
              <h4>Medications: {d.medications.join(", ")}</h4>
              {d.interactions.length > 0 ? d.interactions.map((ix, j) => (
                <div key={j} className="module-alert danger"><strong>{ix.severity}</strong> — {ix.warning}</div>
              )) : <p className="module-empty">No significant interactions predicted.</p>}
            </div>
          ))}
        </Widget>
        <Widget title="Telehealth Triage">
          <DataTable data={telehealth} columns={[
            { key: "symptoms", label: "Symptoms" },
            { key: "age", label: "Age" },
            { key: "urgency", label: "Urgency", render: (r) => <Badge variant={r.urgency === "emergent" ? "danger" : r.urgency === "urgent" ? "warn" : "ok"}>{r.urgency}</Badge> },
            { key: "recommendation", label: "Action" },
          ]} />
        </Widget>
      </div>
    </section>
  );
}

export function TransportDashboard({ data }: { data: DashboardData }) {
  const traffic = data.traffic || [];
  const fleet = data.fleet || [];
  const routes = data.route_plan || [];
  const activeIncidents = traffic.filter((t) => t.incident_nearby).length;
  const avgUtilization = Math.round(fleet.reduce((s, f) => s + f.utilization_pct, 0) / (fleet.length || 1));

  return (
    <section className="module-dashboard">
      <div className="module-dashboard-header">
        <h2>🚚 Transport Command Center</h2>
        <p>Traffic optimization, fleet scheduling, and route planning.</p>
      </div>
      <div className="module-kpi-row">
        <KPICard title="Zones Monitored" value={traffic.length} sub="Active zones" />
        <KPICard title="Active Incidents" value={activeIncidents} sub="Nearby" color={activeIncidents > 0 ? "var(--danger)" : "var(--success)"} />
        <KPICard title="Fleet Utilization" value={`${avgUtilization}%`} sub="Average" />
        <KPICard title="Routes Planned" value={routes.length} sub="Optimized" />
      </div>
      <div className="module-widgets-grid">
        <Widget title="Traffic Zones">
          <DataTable data={traffic} columns={[
            { key: "zone", label: "Zone" },
            { key: "current_congestion", label: "Congestion", render: (r) => <Badge variant={r.current_congestion > 6 ? "danger" : r.current_congestion > 3 ? "warn" : "ok"}>{r.current_congestion}/10</Badge> },
            { key: "predicted_improvement", label: "Predicted Improvement" },
            { key: "incident_nearby", label: "Incident", render: (r) => r.incident_nearby ? <Badge variant="danger">Yes</Badge> : "—" },
          ]} />
        </Widget>
        <Widget title="Fleet Scheduling">
          <DataTable data={fleet} columns={[
            { key: "vehicles_available", label: "Vehicles" },
            { key: "shifts", label: "Shifts" },
            { key: "utilization_pct", label: "Utilization %", render: (r) => `${r.utilization_pct}%` },
            { key: "recommendation", label: "Recommendation" },
          ]} />
        </Widget>
        <Widget title="Route Optimization">
          <DataTable data={routes} columns={[
            { key: "stops", label: "Stops", render: (r) => `${r.stops.length} stops` },
            { key: "estimated_distance_km", label: "Distance km" },
            { key: "estimated_time_min", label: "Time min" },
            { key: "fuel_cost_est", label: "Fuel Cost", render: (r) => `$${r.fuel_cost_est}` },
          ]} />
        </Widget>
      </div>
    </section>
  );
}

export function FinanceDashboard({ data }: { data: DashboardData }) {
  const risk = data.risk_data;
  const payments = data.payment_analysis || [];
  const market = data.market_data;
  const fraud = data.fraud_cases || [];
  const credit = data.credit_applications || [];
  const highFraud = fraud.filter((f) => f.risk_level === "high").length;

  return (
    <section className="module-dashboard">
      <div className="module-dashboard-header">
        <h2>💰 Finance Command Center</h2>
        <p>Risk assessment, market forecasting, fraud detection, and credit scoring.</p>
      </div>
      <div className="module-kpi-row">
        {risk && <KPICard title="VaR (95%)" value={`$${risk.var_95_1d.toLocaleString()}`} sub={`${risk.var_95_pct}% of portfolio`} />}
        {market && <KPICard title="Market Outlook" value={market.predicted_direction} sub={`${(market.confidence * 100).toFixed(0)}% confidence`} color={market.predicted_direction === "bullish" ? "var(--success)" : market.predicted_direction === "bearish" ? "var(--danger)" : "var(--accent-2)"} />}
        <KPICard title="Fraud Alerts" value={highFraud} sub="Need review" color={highFraud > 0 ? "var(--danger)" : "var(--success)"} />
        <KPICard title="Credit Applications" value={credit.length} sub="Processed" />
      </div>
      <div className="module-widgets-grid">
        {risk && (
          <Widget title="Portfolio Risk Metrics">
            <div className="module-elasticity">
              <div><span>Asset</span><strong>{risk.asset}</strong></div>
              <div><span>Sharpe Ratio</span><strong>{risk.sharpe_estimate}</strong></div>
              <div><span>Beta</span><strong>{risk.beta}</strong></div>
              <div><span>Risk Rating</span><strong><Badge variant={risk.risk_rating === "high" ? "danger" : risk.risk_rating === "medium" ? "warn" : "ok"}>{risk.risk_rating}</Badge></strong></div>
              <div><span>Diversification</span><strong>{risk.diversification_score}/10</strong></div>
              <div><span>Recommendation</span><strong>{risk.recommendation}</strong></div>
            </div>
          </Widget>
        )}
        {market && (
          <Widget title="Market Forecast">
            <div className="module-elasticity">
              <div><span>Market</span><strong>{market.market}</strong></div>
              <div><span>Direction</span><strong>{market.predicted_direction}</strong></div>
              <div><span>Price Target</span><strong>{market.price_target_pct > 0 ? `+${market.price_target_pct}%` : `${market.price_target_pct}%`}</strong></div>
              <div><span>Volatility</span><strong>{market.volatility_forecast}</strong></div>
            </div>
          </Widget>
        )}
        <Widget title="Fraud Detection">
          <DataTable data={fraud} columns={[
            { key: "transaction_id", label: "Transaction" },
            { key: "amount", label: "Amount", render: (r) => `$${r.amount.toLocaleString()}` },
            { key: "fraud_score", label: "Score", render: (r) => `${(r.fraud_score * 100).toFixed(0)}%` },
            { key: "risk_level", label: "Risk", render: (r) => <Badge variant={r.risk_level === "high" ? "danger" : r.risk_level === "medium" ? "warn" : "ok"}>{r.risk_level}</Badge> },
            { key: "action", label: "Action" },
          ]} />
        </Widget>
        <Widget title="Credit Scoring">
          <DataTable data={credit} columns={[
            { key: "applicant_id", label: "Applicant" },
            { key: "credit_score", label: "Score", render: (r) => <Badge variant={r.credit_score > 670 ? "ok" : r.credit_score > 580 ? "warn" : "danger"}>{r.credit_score}</Badge> },
            { key: "rating", label: "Rating" },
            { key: "approval_probability", label: "Approval %", render: (r) => `${(r.approval_probability * 100).toFixed(0)}%` },
          ]} />
        </Widget>
      </div>
    </section>
  );
}

export function CulturalHeritageDashboard({ data }: { data: DashboardData }) {
  const visitors = data.visitor_data || [];
  const sites = data.heritage_sites || [];
  const exhibitions = data.exhibitions || [];
  const tours = data.virtual_tours || [];
  const avgEngagement = Math.round(visitors.reduce((s, v) => s + v.engagement_score, 0) / (visitors.length || 1));

  return (
    <section className="module-dashboard">
      <div className="module-dashboard-header">
        <h2>🎭 Cultural Heritage Command Center</h2>
        <p>Visitor engagement, heritage site insights, exhibition planning, and virtual tours.</p>
      </div>
      <div className="module-kpi-row">
        <KPICard title="Venues" value={visitors.length} sub="Monitored" />
        <KPICard title="Engagement Score" value={`${avgEngagement}%`} sub="Average" />
        <KPICard title="Total Annual Visitors" value={sites.reduce((s, si) => s + si.annual_visitors, 0).toLocaleString()} sub="Across sites" />
        <KPICard title="Exhibitions Planned" value={exhibitions.length} sub="In pipeline" />
      </div>
      <div className="module-widgets-grid">
        <Widget title="Visitor Engagement">
          <DataTable data={visitors} columns={[
            { key: "venue", label: "Venue" },
            { key: "daily_visitors", label: "Daily Visitors" },
            { key: "engagement_score", label: "Engagement", render: (r) => <Badge variant={r.engagement_score > 75 ? "ok" : r.engagement_score > 50 ? "warn" : "danger"}>{r.engagement_score}%</Badge> },
            { key: "recommended_strategies", label: "Strategies", render: (r) => r.recommended_strategies.slice(0, 2).join(", ") },
          ]} />
        </Widget>
        <Widget title="Heritage Sites">
          <DataTable data={sites} columns={[
            { key: "site", label: "Site" },
            { key: "era", label: "Era" },
            { key: "annual_visitors", label: "Annual Visitors", render: (r) => r.annual_visitors.toLocaleString() },
            { key: "conservation_status", label: "Status", render: (r) => <Badge variant={r.conservation_status === "good" ? "ok" : r.conservation_status === "requires attention" ? "warn" : "danger"}>{r.conservation_status}</Badge> },
          ]} />
        </Widget>
        <Widget title="Exhibition Planning">
          <DataTable data={exhibitions} columns={[
            { key: "theme", label: "Theme" },
            { key: "recommended_duration_days", label: "Duration Days" },
            { key: "estimated_visitors", label: "Est. Visitors", render: (r) => r.estimated_visitors.toLocaleString() },
            { key: "ticket_price", label: "Ticket", render: (r) => `$${r.ticket_price}` },
            { key: "projected_revenue", label: "Revenue", render: (r) => `$${r.projected_revenue.toLocaleString()}` },
          ]} />
        </Widget>
        <Widget title="Virtual Tours">
          <DataTable data={tours} columns={[
            { key: "site", label: "Site" },
            { key: "interest", label: "Interest" },
            { key: "audio_duration_seconds", label: "Audio Duration", render: (r) => `${Math.floor(r.audio_duration_seconds / 60)}m ${r.audio_duration_seconds % 60}s` },
          ]} />
        </Widget>
      </div>
    </section>
  );
}

export function UtilitiesDashboard({ data }: { data: DashboardData }) {
  const resources = data.resource_data || [];
  const services = data.public_services || [];
  const waste = data.waste_data || [];
  const grid = data.energy_grid || [];
  const criticalResources = resources.filter((r) => r.status === "critical").length;
  const gridCritical = grid.filter((g) => g.status === "critical").length;

  return (
    <section className="module-dashboard">
      <div className="module-dashboard-header">
        <h2>⚡ Utilities Command Center</h2>
        <p>Resource optimization, public service monitoring, waste management, and energy grid oversight.</p>
      </div>
      <div className="module-kpi-row">
        <KPICard title="Resource Status" value={criticalResources} sub="Critical deficits" color={criticalResources > 0 ? "var(--danger)" : "var(--success)"} />
        <KPICard title="Service KPI Avg" value={`${Math.round(services.reduce((s, sv) => s + sv.kpi_score, 0) / (services.length || 1))}%`} sub="Satisfaction score" />
        <KPICard title="Recycling Rate" value={`${Math.round(waste.reduce((s, w) => s + w.recycled_pct, 0) / (waste.length || 1))}%`} sub="Average" />
        <KPICard title="Grid Status" value={gridCritical} sub="Critical zones" color={gridCritical > 0 ? "var(--danger)" : "var(--success)"} />
      </div>
      <div className="module-widgets-grid">
        <Widget title="Resource Optimization">
          <DataTable data={resources} columns={[
            { key: "resource", label: "Resource" },
            { key: "demand", label: "Demand" },
            { key: "supply", label: "Supply" },
            { key: "deficit", label: "Deficit", render: (r) => <span style={{color: r.deficit < 0 ? "var(--danger)" : "var(--success)"}}>{r.deficit}</span> },
            { key: "status", label: "Status", render: (r) => <Badge variant={r.status === "critical" ? "danger" : r.status === "warning" ? "warn" : "ok"}>{r.status}</Badge> },
          ]} />
        </Widget>
        <Widget title="Public Service KPIs">
          <DataTable data={services} columns={[
            { key: "service", label: "Service" },
            { key: "kpi_score", label: "KPI Score" },
            { key: "status", label: "Status", render: (r) => <Badge variant={r.status === "excellent" ? "ok" : r.status === "satisfactory" ? "warn" : "danger"}>{r.status}</Badge> },
            { key: "citizen_satisfaction", label: "Satisfaction", render: (r) => `${(r.citizen_satisfaction * 100).toFixed(0)}%` },
            { key: "trend", label: "Trend", render: (r) => <Badge variant={r.trend === "improving" ? "ok" : r.trend === "declining" ? "danger" : "warn"}>{r.trend}</Badge> },
          ]} />
        </Widget>
        <Widget title="Waste Management">
          <DataTable data={waste} columns={[
            { key: "district", label: "District" },
            { key: "total_waste_tons", label: "Total Waste (tons)" },
            { key: "recycled_pct", label: "Recycled %" },
            { key: "landfill_pct", label: "Landfill %" },
            { key: "collection_efficiency", label: "Efficiency" },
          ]} />
        </Widget>
        <Widget title="Energy Grid">
          <DataTable data={grid} columns={[
            { key: "region", label: "Region" },
            { key: "current_load_mw", label: "Load MW" },
            { key: "utilization_pct", label: "Utilization %", render: (r) => `${r.utilization_pct}%` },
            { key: "renewable_share_pct", label: "Renewable %" },
            { key: "status", label: "Status", render: (r) => <Badge variant={r.status === "critical" ? "danger" : r.status === "warning" ? "warn" : "ok"}>{r.status}</Badge> },
          ]} />
        </Widget>
      </div>
    </section>
  );
}

export function SMEDashboard({ data }: { data: DashboardData }) {
  const workflows = data.workflow_data || [];
  const docs = data.document_queue || [];
  const tickets = data.support_tickets || [];
  const chains = data.supply_chain || [];
  const totalSavings = workflows.reduce((s, w) => s + w.cost_savings_annual, 0);
  const escalatedTickets = tickets.filter((t) => t.escalated).length;
  const highRiskChains = chains.filter((c) => c.risk_level === "high").length;

  return (
    <section className="module-dashboard">
      <div className="module-dashboard-header">
        <h2>🏢 SME Business Suite</h2>
        <p>Workflow automation, document processing, AI support, and supply chain analytics.</p>
      </div>
      <div className="module-kpi-row">
        <KPICard title="Annual Savings" value={`$${totalSavings.toLocaleString()}`} sub="From automation" />
        <KPICard title="Docs Processed" value={docs.length} sub="In queue" />
        <KPICard title="Escalated Tickets" value={escalatedTickets} sub="Needs review" color={escalatedTickets > 0 ? "var(--danger)" : "var(--success)"} />
        <KPICard title="Supply Chain Risk" value={highRiskChains} sub="High risk" color={highRiskChains > 0 ? "var(--danger)" : "var(--success)"} />
      </div>
      <div className="module-widgets-grid">
        <Widget title="Workflow Automation">
          <DataTable data={workflows} columns={[
            { key: "process", label: "Process" },
            { key: "employees_involved", label: "Employees" },
            { key: "hours_saved_per_month", label: "Hours Saved/Mo" },
            { key: "cost_savings_annual", label: "Annual Savings", render: (r) => `$${r.cost_savings_annual.toLocaleString()}` },
          ]} />
        </Widget>
        <Widget title="Document Processing">
          <DataTable data={docs} columns={[
            { key: "document_type", label: "Type" },
            { key: "confidence", label: "AI Confidence", render: (r) => `${(r.confidence * 100).toFixed(0)}%` },
            { key: "pages_processed", label: "Pages" },
            { key: "fields_extracted", label: "Fields", render: (r) => r.fields_extracted.slice(0, 3).join(", ") },
          ]} />
        </Widget>
        <Widget title="Customer Support">
          <DataTable data={tickets} columns={[
            { key: "detected_intent", label: "Intent" },
            { key: "sentiment", label: "Sentiment", render: (r) => <Badge variant={r.sentiment === "positive" ? "ok" : r.sentiment === "negative" ? "danger" : "warn"}>{r.sentiment}</Badge> },
            { key: "response", label: "AI Response" },
            { key: "escalated", label: "Escalated", render: (r) => r.escalated ? <Badge variant="danger">Yes</Badge> : "No" },
          ]} />
        </Widget>
        <Widget title="Supply Chain Analytics">
          <DataTable data={chains} columns={[
            { key: "chain_id", label: "Chain" },
            { key: "health_score", label: "Health Score" },
            { key: "lead_time_days", label: "Lead Time Days" },
            { key: "risk_level", label: "Risk", render: (r) => <Badge variant={r.risk_level === "high" ? "danger" : r.risk_level === "medium" ? "warn" : "ok"}>{r.risk_level}</Badge> },
            { key: "bottlenecks", label: "Bottlenecks", render: (r) => r.bottlenecks.length > 0 ? r.bottlenecks.join(", ") : "None" },
          ]} />
        </Widget>
      </div>
    </section>
  );
}

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
