"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

interface Execution {
  id: string;
  rule_id: string;
  rule_name?: string;
  event_type: string;
  event_payload: Record<string, any>;
  status: "triggered" | "failed";
  result: Record<string, any>;
  created_at: string;
}

interface AutomationRule {
  id: string;
  name: string;
}

const PAGE_SIZE = 25;

export default function ExecutionsPage() {
  const [executions, setExecutions] = useState<Execution[]>([]);
  const [rules, setRules] = useState<AutomationRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [eventTypeFilter, setEventTypeFilter] = useState<string>("");
  const [ruleFilter, setRuleFilter] = useState<string>("");
  const [selected, setSelected] = useState<Execution | null>(null);

  useEffect(() => {
    loadRules();
  }, []);

  useEffect(() => {
    loadExecutions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [offset, statusFilter, eventTypeFilter, ruleFilter]);

  async function loadRules() {
    try {
      const res = await fetch("/api/automations");
      const data = await res.json();
      if (data.ok && Array.isArray(data.rules)) {
        setRules(data.rules.map((r: any) => ({ id: r.id, name: r.name })));
      }
    } catch {}
  }

  async function loadExecutions() {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.set("limit", String(PAGE_SIZE));
      params.set("offset", String(offset));
      if (statusFilter) params.set("status", statusFilter);
      if (eventTypeFilter) params.set("event_type", eventTypeFilter);
      if (ruleFilter) params.set("rule_id", ruleFilter);

      const res = await fetch(`/api/automations/executions?${params.toString()}`);
      const data = await res.json();
      if (data.ok && Array.isArray(data.executions)) {
        setExecutions(data.executions);
      } else {
        setError(data.error || "Failed to load executions");
      }
    } catch (e: any) {
      setError(e.message || "Failed to load executions");
    } finally {
      setLoading(false);
    }
  }

  async function retryRule(ruleId: string) {
    try {
      const res = await fetch(`/api/automations/${ruleId}/run`, { method: "POST" });
      const data = await res.json();
      if (data.ok) {
        alert("Rule re-triggered. Refresh to see the new execution.");
      } else {
        alert(data.error || "Failed to re-trigger rule");
      }
    } catch (e: any) {
      alert(e.message || "Failed to re-trigger rule");
    }
  }

  function formatDate(iso: string) {
    return new Date(iso).toLocaleString();
  }

  function truncate(str: string, len = 60) {
    if (!str) return "—";
    return str.length > len ? str.slice(0, len) + "…" : str;
  }

  const eventTypes = Array.from(new Set(executions.map((e) => e.event_type)));

  return (
    <div className="os-page" style={{ padding: 24 }}>
      <header
        style={{
          marginBottom: 20,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 12,
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
            📊 Automation Executions
          </h1>
          <p className="dashboard-subtitle">
            History of every automation run across your workspace.
          </p>
        </div>
        <div style={{ display: "flex", gap: 12 }}>
          <Link href="/os/automations" className="btn btn-sm">
            ← Automations
          </Link>
          <Link href="/os" className="btn btn-sm">
            ← OS
          </Link>
        </div>
      </header>

      {error && (
        <div className="module-alert danger" style={{ marginBottom: 16 }}>
          {error}
        </div>
      )}

      <section
        style={{
          border: "1px solid var(--border)",
          borderRadius: 12,
          padding: 16,
          background: "var(--bg)",
          marginBottom: 24,
        }}
      >
        <div style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "end" }}>
          <div>
            <label
              style={{ display: "block", marginBottom: 6, fontSize: "0.8rem", fontWeight: 600 }}
            >
              Status
            </label>
            <select
              className="input"
              value={statusFilter}
              onChange={(e) => {
                setOffset(0);
                setStatusFilter(e.target.value);
              }}
            >
              <option value="">All</option>
              <option value="triggered">Triggered</option>
              <option value="failed">Failed</option>
            </select>
          </div>
          <div>
            <label
              style={{ display: "block", marginBottom: 6, fontSize: "0.8rem", fontWeight: 600 }}
            >
              Event Type
            </label>
            <select
              className="input"
              value={eventTypeFilter}
              onChange={(e) => {
                setOffset(0);
                setEventTypeFilter(e.target.value);
              }}
            >
              <option value="">All</option>
              {eventTypes.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label
              style={{ display: "block", marginBottom: 6, fontSize: "0.8rem", fontWeight: 600 }}
            >
              Rule
            </label>
            <select
              className="input"
              value={ruleFilter}
              onChange={(e) => {
                setOffset(0);
                setRuleFilter(e.target.value);
              }}
            >
              <option value="">All</option>
              {rules.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name}
                </option>
              ))}
            </select>
          </div>
          <button
            className="btn btn-sm"
            onClick={() => {
              setOffset(0);
              loadExecutions();
            }}
          >
            Refresh
          </button>
        </div>
      </section>

      <section
        style={{
          border: "1px solid var(--border)",
          borderRadius: 12,
          overflow: "hidden",
          background: "var(--bg)",
        }}
      >
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ background: "var(--bg-2)", textAlign: "left" }}>
              <th style={{ padding: 12, fontSize: "0.8rem" }}>Rule</th>
              <th style={{ padding: 12, fontSize: "0.8rem" }}>Event Type</th>
              <th style={{ padding: 12, fontSize: "0.8rem" }}>Status</th>
              <th style={{ padding: 12, fontSize: "0.8rem" }}>Created At</th>
              <th style={{ padding: 12, fontSize: "0.8rem" }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading && executions.length === 0 ? (
              <tr>
                <td colSpan={5} style={{ padding: 24, textAlign: "center" }}>
                  Loading…
                </td>
              </tr>
            ) : executions.length === 0 ? (
              <tr>
                <td colSpan={5} style={{ padding: 24, textAlign: "center" }}>
                  No executions found.
                </td>
              </tr>
            ) : (
              executions.map((e) => (
                <tr key={e.id} style={{ borderTop: "1px solid var(--border)" }}>
                  <td style={{ padding: 12 }}>{e.rule_name || truncate(e.rule_id, 8)}</td>
                  <td style={{ padding: 12, fontSize: "0.85rem" }}>{e.event_type}</td>
                  <td style={{ padding: 12 }}>
                    <span
                      style={{
                        display: "inline-block",
                        padding: "2px 8px",
                        borderRadius: 999,
                        fontSize: "0.75rem",
                        fontWeight: 600,
                        background:
                          e.status === "failed" ? "rgba(239,68,68,0.15)" : "rgba(34,197,94,0.15)",
                        color: e.status === "failed" ? "#ef4444" : "#22c55e",
                      }}
                    >
                      {e.status}
                    </span>
                  </td>
                  <td style={{ padding: 12, fontSize: "0.85rem" }}>{formatDate(e.created_at)}</td>
                  <td style={{ padding: 12, display: "flex", gap: 8 }}>
                    <button className="btn btn-sm" onClick={() => setSelected(e)}>
                      View
                    </button>
                    <button className="btn btn-sm" onClick={() => retryRule(e.rule_id)}>
                      Retry
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </section>

      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginTop: 16,
        }}
      >
        <button
          className="btn btn-sm"
          disabled={offset === 0}
          onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
        >
          ← Previous
        </button>
        <span style={{ fontSize: "0.85rem" }}>Offset: {offset}</span>
        <button
          className="btn btn-sm"
          disabled={executions.length < PAGE_SIZE}
          onClick={() => setOffset((o) => o + PAGE_SIZE)}
        >
          Next →
        </button>
      </div>

      {selected && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.5)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 100,
            padding: 24,
          }}
          onClick={(ev) => {
            if (ev.target === ev.currentTarget) setSelected(null);
          }}
        >
          <div
            style={{
              background: "var(--bg)",
              border: "1px solid var(--border)",
              borderRadius: 12,
              width: "100%",
              maxWidth: 700,
              maxHeight: "80vh",
              overflow: "auto",
              padding: 24,
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: 16,
              }}
            >
              <h3 style={{ margin: 0 }}>Execution Details</h3>
              <button className="btn btn-sm" onClick={() => setSelected(null)}>
                Close
              </button>
            </div>
            <p>
              <strong>ID:</strong> {selected.id}
            </p>
            <p>
              <strong>Rule:</strong> {selected.rule_name || selected.rule_id}
            </p>
            <p>
              <strong>Event Type:</strong> {selected.event_type}
            </p>
            <p>
              <strong>Status:</strong> {selected.status}
            </p>
            <p>
              <strong>Created At:</strong> {formatDate(selected.created_at)}
            </p>

            <div style={{ marginTop: 16 }}>
              <h4 style={{ marginBottom: 8 }}>Event Payload</h4>
              <pre
                style={{
                  background: "var(--bg-2)",
                  padding: 12,
                  borderRadius: 8,
                  overflow: "auto",
                  fontSize: "0.8rem",
                }}
              >
                {JSON.stringify(selected.event_payload, null, 2)}
              </pre>
            </div>

            <div style={{ marginTop: 16 }}>
              <h4 style={{ marginBottom: 8 }}>Result</h4>
              <pre
                style={{
                  background: "var(--bg-2)",
                  padding: 12,
                  borderRadius: 8,
                  overflow: "auto",
                  fontSize: "0.8rem",
                }}
              >
                {JSON.stringify(selected.result, null, 2)}
              </pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
