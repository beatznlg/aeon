"use client";

import { KPICard, Widget, Badge, SimpleLineChart, DataTable, DashboardData } from "./shared";

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
        <KPICard
          title="High-Risk Clauses"
          value={highRisk}
          sub="Need review"
          color={highRisk > 0 ? "var(--danger)" : "var(--success)"}
        />
        <KPICard
          title="Invoice Anomalies"
          value={anomalies}
          sub="Flagged"
          color={anomalies > 0 ? "var(--danger)" : "var(--success)"}
        />
      </div>
      <div className="module-widgets-grid">
        <Widget title="Legal Document Queue">
          <DataTable
            data={legal}
            columns={[
              { key: "doc", label: "Document" },
              { key: "type", label: "Type" },
              {
                key: "risk_score",
                label: "Risk",
                render: (r) => (
                  <Badge
                    variant={
                      r.risk_score === "high" ? "danger" : r.risk_score === "medium" ? "warn" : "ok"
                    }
                  >
                    {r.risk_score}
                  </Badge>
                ),
              },
              { key: "obligations", label: "Obligations", render: (r) => r.obligations.join(", ") },
            ]}
          />
        </Widget>
        <Widget title="Accounting Audit">
          <DataTable
            data={accounting}
            columns={[
              { key: "invoice_id", label: "Invoice" },
              { key: "vendor", label: "Vendor" },
              { key: "amount", label: "Amount", render: (r) => `$${r.amount.toLocaleString()}` },
              {
                key: "auto_approved",
                label: "Auto-Approved",
                render: (r) => (r.auto_approved ? "Yes" : "No"),
              },
              {
                key: "anomalies_detected",
                label: "Anomaly",
                render: (r) => (
                  <Badge variant={r.anomalies_detected ? "danger" : "ok"}>
                    {r.anomalies_detected ? "Yes" : "No"}
                  </Badge>
                ),
              },
            ]}
          />
        </Widget>
        <Widget title="Data Compliance">
          <DataTable
            data={dataMgmt}
            columns={[
              { key: "dataset", label: "Dataset" },
              { key: "pii_records_found", label: "PII Records" },
              {
                key: "compliance",
                label: "Compliance",
                render: (r) => (
                  <Badge variant={r.compliance === "GDPR-ready" ? "ok" : "warn"}>
                    {r.compliance}
                  </Badge>
                ),
              },
            ]}
          />
        </Widget>
      </div>
    </section>
  );
}
