"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSession } from "next-auth/react";

type AuditRow = {
  id: string;
  action: string;
  module: string;
  email?: string;
  user_id?: string;
  workspace_id?: string;
  metadata: Record<string, any>;
  timestamp: string;
  pii_redacted: boolean;
  review_status: string;
};

type ComplianceResult = {
  ok: boolean;
  check_type: string;
  status: "success" | "warning" | "failed";
  findings: any[];
  scanned?: number;
  note?: string;
};

function useFetch<T>(url: string) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    fetch(url, { cache: "no-store" })
      .then((r) => r.json())
      .then((d) => {
        if (!mounted) return;
        setData(d);
        setLoading(false);
      })
      .catch((e) => {
        if (!mounted) return;
        setError(String(e));
        setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [url]);

  return { data, loading, error };
}

function Card({ title, children, className = "" }: { title?: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={`os-card ${className}`} style={{ padding: 20 }}>
      {title && <h3 style={{ margin: "0 0 16px", fontSize: "0.95rem", textTransform: "uppercase", letterSpacing: 1, color: "var(--fg-mute)" }}>{title}</h3>}
      {children}
    </div>
  );
}

const checkTypes = [
  { id: "pii_scan", label: "PII Scan" },
  { id: "retention_run", label: "Retention Check" },
  { id: "consent_audit", label: "Consent Audit" },
  { id: "role_review", label: "Role Review" },
];

export default function GovernancePage() {
  const { data: session } = useSession();
  const workspaceId = ((session?.user as any)?.workspaceId as string) || "default";

  const [offset, setOffset] = useState(0);
  const [actionFilter, setActionFilter] = useState("");
  const [moduleFilter, setModuleFilter] = useState("");
  const [selectedCheck, setSelectedCheck] = useState("pii_scan");
  const [complianceResult, setComplianceResult] = useState<ComplianceResult | null>(null);
  const [checkLoading, setCheckLoading] = useState(false);
  const [retentionDays, setRetentionDays] = useState(365);
  const [retentionAction, setRetentionAction] = useState<"archive" | "delete">("archive");
  const [retentionMsg, setRetentionMsg] = useState("");

  const auditUrl = useMemo(() => {
    const params = new URLSearchParams({ workspace_id: workspaceId, limit: "50", offset: String(offset) });
    if (actionFilter) params.set("action", actionFilter);
    if (moduleFilter) params.set("module", moduleFilter);
    return `/api/governance/audit?${params.toString()}`;
  }, [workspaceId, offset, actionFilter, moduleFilter]);

  const { data: audit, loading: auditLoading, error: auditError } = useFetch<{ ok: boolean; rows: AuditRow[]; count: number }>(auditUrl);

  const { data: retention } = useFetch<{ ok: boolean; policy: { retention_days: number; action: "archive" | "delete" } }>(
    `/api/governance/retention?workspace_id=${encodeURIComponent(workspaceId)}`
  );

  useEffect(() => {
    if (retention?.policy) {
      setRetentionDays(retention.policy.retention_days ?? 365);
      setRetentionAction(retention.policy.action ?? "archive");
    }
  }, [retention]);

  const runCompliance = async () => {
    setCheckLoading(true);
    setComplianceResult(null);
    try {
      const res = await fetch("/api/governance/compliance", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ check_type: selectedCheck, workspace_id: workspaceId }),
      });
      const data = await res.json();
      setComplianceResult(data);
    } catch (e: any) {
      setComplianceResult({ ok: false, check_type: selectedCheck, status: "failed", findings: [e?.message || String(e)] });
    } finally {
      setCheckLoading(false);
    }
  };

  const saveRetention = async () => {
    setRetentionMsg("");
    try {
      const res = await fetch("/api/governance/retention", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ workspace_id: workspaceId, retention_days: retentionDays, action: retentionAction }),
      });
      const data = await res.json();
      setRetentionMsg(data.ok ? "Retention policy saved." : data.error || "Failed to save.");
    } catch (e: any) {
      setRetentionMsg(e?.message || String(e));
    }
  };

  return (
    <div className="os-page">
      <header className="os-header">
        <div>
          <h1 style={{ background: "var(--grad)", WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent" }}>
            🛡️ Governance & Compliance
          </h1>
          <p className="dashboard-subtitle">Audit logs, PII scanning, retention policy, and compliance posture</p>
        </div>
        <Link href="/os" className="btn btn-sm">← OS Launcher</Link>
      </header>

      <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 24 }}>
        <Card title="Compliance Check">
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <select value={selectedCheck} onChange={(e) => setSelectedCheck(e.target.value)} className="input">
              {checkTypes.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.label}
                </option>
              ))}
            </select>
            <button onClick={runCompliance} disabled={checkLoading} className="btn btn-primary">
              {checkLoading ? "Running…" : "Run Check"}
            </button>
            {complianceResult && (
              <div
                style={{
                  padding: 12,
                  borderRadius: 8,
                  background: complianceResult.status === "success" ? "#064e3b" : complianceResult.status === "warning" ? "#713f12" : "#7f1d1d",
                  fontSize: "0.9rem",
                }}
              >
                <strong>{complianceResult.check_type}</strong> — {complianceResult.status}
                {complianceResult.scanned !== undefined && <div>Scanned: {complianceResult.scanned}</div>}
                {complianceResult.findings && complianceResult.findings.length > 0 && (
                  <ul style={{ margin: 0, paddingLeft: 16, marginTop: 8 }}>
                    {complianceResult.findings.map((f, i) => (
                      <li key={i}>{typeof f === "string" ? f : JSON.stringify(f)}</li>
                    ))}
                  </ul>
                )}
                {complianceResult.note && <div style={{ marginTop: 8 }}>{complianceResult.note}</div>}
              </div>
            )}
          </div>
        </Card>

        <Card title="Retention Policy">
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <label style={{ fontSize: "0.85rem", color: "var(--fg-mute)" }}>Keep audit logs for (days)</label>
            <input
              type="number"
              min={1}
              value={retentionDays}
              onChange={(e) => setRetentionDays(Number(e.target.value))}
              className="input"
            />
            <label style={{ fontSize: "0.85rem", color: "var(--fg-mute)" }}>After retention period</label>
            <select value={retentionAction} onChange={(e) => setRetentionAction(e.target.value as any)} className="input">
              <option value="archive">Archive</option>
              <option value="delete">Delete</option>
            </select>
            <button onClick={saveRetention} className="btn btn-primary">
              Save Policy
            </button>
            {retentionMsg && <div style={{ fontSize: "0.85rem", color: "var(--fg-mute)" }}>{retentionMsg}</div>}
          </div>
        </Card>
      </section>

      <section style={{ marginTop: 24 }}>
        <Card title="Audit Logs">
          <div style={{ display: "flex", gap: 12, marginBottom: 16, flexWrap: "wrap" }}>
            <input
              type="text"
              placeholder="Filter by action"
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
              className="input"
              style={{ flex: 1, minWidth: 160 }}
            />
            <input
              type="text"
              placeholder="Filter by module"
              value={moduleFilter}
              onChange={(e) => setModuleFilter(e.target.value)}
              className="input"
              style={{ flex: 1, minWidth: 160 }}
            />
          </div>

          {auditLoading && <div style={{ color: "var(--fg-mute)" }}>Loading audit logs…</div>}
          {auditError && <div className="module-alert danger">{auditError}</div>}

          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem" }}>
              <thead>
                <tr style={{ textAlign: "left", borderBottom: "1px solid var(--border)" }}>
                  <th style={{ padding: "8px 12px" }}>Action</th>
                  <th style={{ padding: "8px 12px" }}>Module</th>
                  <th style={{ padding: "8px 12px" }}>Email</th>
                  <th style={{ padding: "8px 12px" }}>Time</th>
                  <th style={{ padding: "8px 12px" }}>Status</th>
                  <th style={{ padding: "8px 12px" }}>Metadata</th>
                </tr>
              </thead>
              <tbody>
                {audit?.rows?.map((row) => (
                  <tr key={row.id} style={{ borderBottom: "1px solid var(--border)" }}>
                    <td style={{ padding: "8px 12px" }}>{row.action}</td>
                    <td style={{ padding: "8px 12px" }}>{row.module}</td>
                    <td style={{ padding: "8px 12px" }}>{row.email || "—"}</td>
                    <td style={{ padding: "8px 12px" }}>{new Date(row.timestamp).toLocaleString()}</td>
                    <td style={{ padding: "8px 12px" }}>
                      {row.pii_redacted && <span style={{ color: "#f59e0b" }}>PII redacted</span>}
                      <span style={{ color: "var(--fg-mute)", marginLeft: 4 }}>{row.review_status}</span>
                    </td>
                    <td style={{ padding: "8px 12px", maxWidth: 260, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {JSON.stringify(row.metadata)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 16 }}>
            <button onClick={() => setOffset((o) => Math.max(0, o - 50))} disabled={offset === 0} className="btn btn-sm">
              Previous
            </button>
            <button onClick={() => setOffset((o) => o + 50)} className="btn btn-sm">
              Next
            </button>
          </div>
        </Card>
      </section>
    </div>
  );
}
