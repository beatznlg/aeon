"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

interface ApprovalRequest {
  id: string;
  rule_id: string;
  event_type: string;
  event_payload: Record<string, any>;
  action_type: string;
  action_config: Record<string, any>;
  status: "pending" | "approved" | "rejected" | "cancelled";
  reason: string;
  created_at: string;
  resolved_at?: string;
  result?: Record<string, any>;
}

const STATUS_OPTIONS = ["all", "pending", "approved", "rejected", "cancelled"];

export default function ApprovalsPage() {
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("pending");
  const [resolving, setResolving] = useState<Record<string, boolean>>({});

  useEffect(() => {
    loadApprovals();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter]);

  async function loadApprovals() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/approvals?status=${statusFilter}`);
      const data = await res.json();
      if (data.ok && Array.isArray(data.approvals)) {
        setApprovals(data.approvals);
      } else {
        setError(data.error || "Failed to load approvals");
      }
    } catch (e: any) {
      setError(e.message || "Failed to load approvals");
    } finally {
      setLoading(false);
    }
  }

  async function resolveApproval(id: string, decision: "approved" | "rejected") {
    setResolving((prev) => ({ ...prev, [id]: true }));
    try {
      const res = await fetch(`/api/approvals/${id}/resolve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision, reason: "Resolved via UI" }),
      });
      const data = await res.json();
      if (data.ok) {
        await loadApprovals();
      } else {
        setError(data.error || "Failed to resolve approval");
      }
    } catch (e: any) {
      setError(e.message || "Failed to resolve approval");
    } finally {
      setResolving((prev) => ({ ...prev, [id]: false }));
    }
  }

  function statusColor(status: string) {
    switch (status) {
      case "pending":
        return "#f59e0b";
      case "approved":
        return "#22c55e";
      case "rejected":
        return "#ef4444";
      default:
        return "#94a3b8";
    }
  }

  return (
    <div className="os-page" style={{ padding: 24 }}>
      <header
        className="os-header"
        style={{
          marginBottom: 20,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div>
          <h1
            style={{
              background: "var(--grad)",
              WebkitBackgroundClip: "text",
              backgroundClip: "text",
              color: "transparent",
            }}
          >
            ✋ Approvals
          </h1>
          <p className="dashboard-subtitle">Human-in-the-loop checkpoint for automations.</p>
        </div>
        <Link href="/os" className="btn btn-sm">
          ← Back to OS
        </Link>
      </header>

      {error && (
        <div className="module-alert danger" style={{ marginBottom: 16 }}>
          {error}
        </div>
      )}

      <div style={{ marginBottom: 16, display: "flex", gap: 8, alignItems: "center" }}>
        <span style={{ fontSize: "0.85rem", color: "var(--fg-mute)" }}>Filter:</span>
        {STATUS_OPTIONS.map((s) => (
          <button
            key={s}
            className="btn btn-sm"
            onClick={() => setStatusFilter(s)}
            style={{
              background: statusFilter === s ? "var(--fg)" : "transparent",
              color: statusFilter === s ? "var(--bg)" : "var(--fg)",
              textTransform: "capitalize",
            }}
          >
            {s}
          </button>
        ))}
      </div>

      <section
        style={{
          border: "1px solid var(--border)",
          borderRadius: 12,
          background: "var(--bg)",
          minHeight: 400,
        }}
      >
        {loading ? (
          <div style={{ padding: 40, textAlign: "center", color: "var(--fg-mute)" }}>Loading…</div>
        ) : approvals.length === 0 ? (
          <div style={{ padding: 60, textAlign: "center", color: "var(--fg-mute)" }}>
            <div style={{ fontSize: "2rem", marginBottom: 12, opacity: 0.5 }}>✋</div>
            <p>No approval requests found.</p>
            <p style={{ fontSize: "0.78rem" }}>
              Pending automations requiring human approval will appear here.
            </p>
          </div>
        ) : (
          <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {approvals.map((approval) => (
              <li
                key={approval.id}
                style={{
                  padding: "16px 18px",
                  borderBottom: "1px solid var(--border)",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "flex-start",
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 600, display: "flex", alignItems: "center", gap: 8 }}>
                      {approval.event_type}
                      <span
                        style={{
                          fontSize: "0.72rem",
                          padding: "2px 8px",
                          borderRadius: 999,
                          background: `${statusColor(approval.status)}20`,
                          color: statusColor(approval.status),
                          textTransform: "capitalize",
                        }}
                      >
                        {approval.status}
                      </span>
                    </div>
                    <div style={{ fontSize: "0.78rem", color: "var(--fg-mute)", marginTop: 4 }}>
                      Action: {approval.action_type} · Created{" "}
                      {new Date(approval.created_at).toLocaleString()}
                    </div>
                    <details style={{ marginTop: 8, fontSize: "0.78rem", color: "var(--fg-mute)" }}>
                      <summary style={{ cursor: "pointer" }}>Payload</summary>
                      <pre
                        style={{ marginTop: 8, whiteSpace: "pre-wrap", wordBreak: "break-word" }}
                      >
                        {JSON.stringify(approval.event_payload, null, 2)}
                      </pre>
                    </details>
                    {approval.status !== "pending" && approval.result && (
                      <details
                        style={{ marginTop: 8, fontSize: "0.78rem", color: "var(--fg-mute)" }}
                      >
                        <summary style={{ cursor: "pointer" }}>Result</summary>
                        <pre
                          style={{ marginTop: 8, whiteSpace: "pre-wrap", wordBreak: "break-word" }}
                        >
                          {JSON.stringify(approval.result, null, 2)}
                        </pre>
                      </details>
                    )}
                  </div>
                  {approval.status === "pending" && (
                    <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
                      <button
                        className="btn btn-sm btn-success"
                        onClick={() => resolveApproval(approval.id, "approved")}
                        disabled={resolving[approval.id]}
                      >
                        {resolving[approval.id] ? "…" : "Approve"}
                      </button>
                      <button
                        className="btn btn-sm btn-danger"
                        onClick={() => resolveApproval(approval.id, "rejected")}
                        disabled={resolving[approval.id]}
                      >
                        {resolving[approval.id] ? "…" : "Reject"}
                      </button>
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
