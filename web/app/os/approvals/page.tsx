"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { getAuthHeaders } from "@/lib/flask-auth";
import ErrorState from "@/components/ui/ErrorState";

type ApprovalStatus = "pending" | "approved" | "rejected" | "cancelled";
type JsonRecord = Record<string, unknown>;

interface ApprovalRequest {
  id: string;
  rule_id?: string | null;
  event_type?: string | null;
  event_payload?: JsonRecord | string | null;
  action_type?: string | null;
  action_config?: JsonRecord | string | null;
  capability_review?: { capability_id?: string | null; sensitive_values_withheld?: boolean };
  status: ApprovalStatus;
  reason?: string | null;
  created_at?: string | null;
  resolved_at?: string | null;
  result?: JsonRecord | string | null;
}

const STATUS_OPTIONS = ["all", "pending", "approved", "rejected", "cancelled"] as const;

function parseRecord(value: JsonRecord | string | null | undefined): JsonRecord {
  if (!value) return {};
  if (typeof value === "object") return value;
  try {
    const parsed: unknown = JSON.parse(value);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? (parsed as JsonRecord)
      : {};
  } catch {
    return {};
  }
}

function stringValue(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function capabilityDetails(approval: ApprovalRequest) {
  const eventPayload = parseRecord(approval.event_payload);
  const actionConfig = parseRecord(approval.action_config);
  const payload = parseRecord(eventPayload.payload as JsonRecord | string | null | undefined);
  const capabilityId =
    stringValue(approval.capability_review?.capability_id) ||
    stringValue(actionConfig.capability_id) ||
    stringValue(payload.capability_id);
  if (approval.action_type !== "capability" && !capabilityId) return null;

  const rawArguments = actionConfig.arguments ?? payload.arguments;
  const args = parseRecord(rawArguments as JsonRecord | string | null | undefined);
  const policy = Array.isArray(payload.policy) ? payload.policy : [];
  return {
    capabilityId: capabilityId || "unknown capability",
    argumentKeys: Object.keys(args),
    policy,
    requesterRole: stringValue(payload.user_role),
  };
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

export default function ApprovalsPage() {
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<(typeof STATUS_OPTIONS)[number]>("pending");
  const [resolving, setResolving] = useState<Record<string, boolean>>({});
  const [reasons, setReasons] = useState<Record<string, string>>({});

  const loadApprovals = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/approvals?status=${statusFilter}`, {
        headers: getAuthHeaders(),
        cache: "no-store",
      });
      const data: unknown = await res.json();
      const body = data as { ok?: boolean; approvals?: ApprovalRequest[]; error?: string };
      if (!res.ok || !body.ok || !Array.isArray(body.approvals)) {
        throw new Error(body.error || "Failed to load approvals");
      }
      setApprovals(body.approvals);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load approvals");
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    void loadApprovals();
  }, [loadApprovals]);

  async function resolveApproval(id: string, decision: "approved" | "rejected") {
    setResolving((prev) => ({ ...prev, [id]: true }));
    setError(null);
    try {
      const res = await fetch(`/api/approvals/${encodeURIComponent(id)}/resolve`, {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify({
          decision,
          reason: reasons[id]?.trim() || `Resolved via AEON UI (${decision})`,
        }),
      });
      const data: unknown = await res.json();
      const body = data as { ok?: boolean; error?: string };
      if (!res.ok || !body.ok) throw new Error(body.error || "Failed to resolve approval");
      await loadApprovals();
    } catch (resolveError) {
      setError(resolveError instanceof Error ? resolveError.message : "Failed to resolve approval");
    } finally {
      setResolving((prev) => ({ ...prev, [id]: false }));
    }
  }

  return (
    <main className="module-page" style={{ maxWidth: 1180, margin: "0 auto", padding: "32px 24px" }}>
      <header
        className="module-page-header"
        style={{ display: "flex", justifyContent: "space-between", gap: 20, alignItems: "flex-start" }}
      >
        <div>
          <div className="eyebrow">GOVERNANCE CONTROL PLANE</div>
          <h1 className="module-title">Approval queue</h1>
          <p className="module-subtitle">
            Review automation checkpoints and policy-gated capability requests before they run.
          </p>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <Link href="/os/capabilities" className="btn btn-sm">Capabilities</Link>
          <Link href="/os" className="btn btn-sm">← OS</Link>
        </div>
      </header>

      {error && (
        <div style={{ marginTop: 20 }}>
          <ErrorState error={error} onRetry={loadApprovals} title="Could not load approvals" />
        </div>
      )}

      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", margin: "24px 0 16px" }}>
        <span className="text-muted" style={{ fontSize: 13 }}>View:</span>
        {STATUS_OPTIONS.map((status) => (
          <button
            key={status}
            className="btn btn-sm"
            onClick={() => setStatusFilter(status)}
            style={{
              background: statusFilter === status ? "var(--fg)" : "transparent",
              color: statusFilter === status ? "var(--bg)" : "var(--fg)",
              textTransform: "capitalize",
            }}
          >
            {status}
          </button>
        ))}
        <button className="btn btn-sm" onClick={() => void loadApprovals()} disabled={loading}>
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      <section className="module-widget" style={{ padding: 0, overflow: "hidden" }}>
        {loading ? (
          <div className="text-muted" style={{ padding: 48, textAlign: "center" }}>Loading approval queue…</div>
        ) : approvals.length === 0 ? (
          <div className="text-muted" style={{ padding: 64, textAlign: "center" }}>
            <div style={{ fontSize: 36, marginBottom: 12, opacity: 0.55 }}>✓</div>
            <h2 style={{ margin: 0, color: "var(--fg)" }}>Queue is clear</h2>
            <p style={{ marginBottom: 0 }}>No {statusFilter === "all" ? "" : statusFilter} approval requests are visible in this workspace.</p>
          </div>
        ) : (
          <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {approvals.map((approval) => {
              const capability = capabilityDetails(approval);
              const busy = Boolean(resolving[approval.id]);
              return (
                <li key={approval.id} style={{ padding: "20px 22px", borderBottom: "1px solid var(--border)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 18, alignItems: "flex-start", flexWrap: "wrap" }}>
                    <div style={{ minWidth: 0, flex: "1 1 520px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 9, flexWrap: "wrap" }}>
                        <span className="eyebrow" style={{ margin: 0 }}>{capability ? "CAPABILITY REQUEST" : approval.event_type || "approval"}</span>
                        <span className="badge" style={{ color: statusColor(approval.status), borderColor: `${statusColor(approval.status)}55` }}>{approval.status}</span>
                      </div>
                      {capability ? (
                        <>
                          <h2 style={{ margin: "10px 0 6px", fontFamily: "monospace", fontSize: 18 }}>{capability.capabilityId}</h2>
                          <p className="text-muted" style={{ margin: 0 }}>
                            A workspace policy requires an operator decision before this capability can execute.
                            {capability.requesterRole ? ` Requested by a ${capability.requesterRole} member.` : ""}
                          </p>
                          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 14 }}>
                            <span className="badge">{capability.argumentKeys.length} argument key{capability.argumentKeys.length === 1 ? "" : "s"}</span>
                            {capability.argumentKeys.slice(0, 6).map((key) => <span className="badge" key={key}>{key}</span>)}
                            {capability.argumentKeys.length > 6 && <span className="badge">+{capability.argumentKeys.length - 6} more</span>}
                          </div>
                          <p className="text-muted" style={{ fontSize: 12, margin: "10px 0 0" }}>
                            Argument values are withheld from this review surface.
                          </p>
                          {capability.policy.length > 0 && (
                            <details style={{ marginTop: 12 }}>
                              <summary style={{ cursor: "pointer", fontSize: 13 }}>Policy signals ({capability.policy.length})</summary>
                              <pre className="code-block" style={{ marginTop: 8, whiteSpace: "pre-wrap", wordBreak: "break-word", fontSize: 12 }}>
                                {JSON.stringify(capability.policy, null, 2)}
                              </pre>
                            </details>
                          )}
                        </>
                      ) : (
                        <>
                          <h2 style={{ margin: "10px 0 6px", fontSize: 18 }}>{approval.action_type || "automation action"}</h2>
                          <p className="text-muted" style={{ margin: 0 }}>
                            Created {approval.created_at ? new Date(approval.created_at).toLocaleString() : "at an unknown time"}.
                          </p>
                          <details style={{ marginTop: 12 }}>
                            <summary style={{ cursor: "pointer", fontSize: 13 }}>Event payload</summary>
                            <pre className="code-block" style={{ marginTop: 8, whiteSpace: "pre-wrap", wordBreak: "break-word", fontSize: 12 }}>
                              {JSON.stringify(parseRecord(approval.event_payload), null, 2)}
                            </pre>
                          </details>
                        </>
                      )}
                      {approval.status !== "pending" && approval.reason && (
                        <p className="text-muted" style={{ fontSize: 12, margin: "12px 0 0" }}>Resolution note: {approval.reason}</p>
                      )}
                    </div>
                    {approval.status === "pending" && (
                      <div style={{ display: "flex", flexDirection: "column", gap: 8, width: "min(280px, 100%)" }}>
                        <textarea
                          className="input"
                          rows={2}
                          value={reasons[approval.id] || ""}
                          onChange={(event) => setReasons((prev) => ({ ...prev, [approval.id]: event.target.value }))}
                          placeholder="Optional decision note"
                          aria-label={`Decision note for ${approval.id}`}
                        />
                        <div style={{ display: "flex", gap: 8 }}>
                          <button className="btn btn-sm btn-success" onClick={() => void resolveApproval(approval.id, "approved")} disabled={busy}>
                            {busy ? "Working…" : "Approve & run"}
                          </button>
                          <button className="btn btn-sm btn-danger" onClick={() => void resolveApproval(approval.id, "rejected")} disabled={busy}>
                            {busy ? "Working…" : "Reject"}
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </main>
  );
}
