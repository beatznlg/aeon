"use client";

import { useEffect, useState } from "react";

// =================== Shared Types ===================
export type KPIData = { title: string; value: string | number; sub?: string; color?: string };

export type DashboardData = {
  ok: boolean;
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
