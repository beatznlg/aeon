"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { getAuthHeaders } from "@/lib/flask-auth";

type Capability = {
  id: string;
  name: string;
  description: string;
  source: "builtin" | "marketplace" | "mcp";
  available: boolean;
  input_schema: Record<string, unknown>;
  permissions: string[];
  plugin_id?: string;
  entry?: string;
  server_name?: string;
  tool?: string;
  verified?: boolean;
};

type RegistryResponse = {
  ok: boolean;
  capabilities?: Capability[];
  count?: number;
  source_counts?: Record<string, number>;
  error?: string;
};

type AuditLog = {
  id?: string;
  action?: string;
  module?: string;
  workspace_id?: string;
  user_id?: string;
  email?: string;
  timestamp?: string;
  pii_redacted?: boolean;
  metadata?: {
    capability_id?: string;
    decision?: "allowed" | "denied";
    reason?: string;
    user_role?: string;
    policy_violation_count?: number;
  };
};

type AuditResponse = {
  ok: boolean;
  logs?: AuditLog[];
  count?: number;
  has_more?: boolean;
  error?: string;
};

const SOURCE_META: Record<Capability["source"], { label: string; icon: string; tone: string }> = {
  builtin: { label: "Core", icon: "◈", tone: "var(--aeon-primary)" },
  marketplace: { label: "Marketplace", icon: "🏪", tone: "#7dd3fc" },
  mcp: { label: "MCP", icon: "🔌", tone: "#c4b5fd" },
};

export default function CapabilitiesPage() {
  const [data, setData] = useState<RegistryResponse>({ ok: false });
  const [source, setSource] = useState<"all" | Capability["source"]>("all");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<Capability | null>(null);
  const [argumentsText, setArgumentsText] = useState("{}");
  const [result, setResult] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [invoking, setInvoking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [audit, setAudit] = useState<AuditResponse>({ ok: false });
  const [auditLoading, setAuditLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/os/capabilities", {
        headers: getAuthHeaders(),
        cache: "no-store",
      });
      const body = (await response.json()) as RegistryResponse;
      if (!response.ok || !body.ok) throw new Error(body.error || "Unable to load capabilities");
      setData(body);
    } catch (loadError) {
      setError(String(loadError));
    } finally {
      setLoading(false);
    }
  }, []);

  const loadAudit = useCallback(async () => {
    setAuditLoading(true);
    try {
      const response = await fetch("/api/os/capabilities?audit=1&limit=12", {
        headers: getAuthHeaders(),
        cache: "no-store",
      });
      const body = (await response.json()) as AuditResponse;
      if (!response.ok || !body.ok) throw new Error(body.error || "Unable to load capability audit");
      setAudit(body);
    } catch (auditError) {
      setError(String(auditError));
    } finally {
      setAuditLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    loadAudit();
  }, [load, loadAudit]);

  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return (data.capabilities || []).filter((capability) => {
      const matchesSource = source === "all" || capability.source === source;
      const haystack =
        `${capability.name} ${capability.description} ${capability.id}`.toLowerCase();
      return matchesSource && (!normalized || haystack.includes(normalized));
    });
  }, [data.capabilities, query, source]);

  const invoke = async () => {
    if (!selected) return;
    let args: unknown;
    try {
      args = JSON.parse(argumentsText || "{}");
    } catch {
      setError("Arguments must be valid JSON");
      return;
    }
    setInvoking(true);
    setError(null);
    setResult(null);
    try {
      const response = await fetch("/api/os/capabilities", {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify({ capability_id: selected.id, arguments: args }),
      });
      const body = await response.json();
      if (!response.ok || !body.ok) throw new Error(body.error || "Capability invocation failed");
      setResult(body.result);
      loadAudit();
    } catch (invokeError) {
      setError(String(invokeError));
    } finally {
      setInvoking(false);
    }
  };

  const openCapability = (capability: Capability) => {
    setSelected(capability);
    setArgumentsText("{}");
    setResult(null);
    setError(null);
  };

  return (
    <main
      className="module-page"
      style={{ maxWidth: 1240, margin: "0 auto", padding: "32px 24px" }}
    >
      <div
        className="module-page-header"
        style={{
          display: "flex",
          justifyContent: "space-between",
          gap: 20,
          alignItems: "flex-start",
        }}
      >
        <div>
          <div className="eyebrow">AEON OPERATIVE FABRIC</div>
          <h1 className="module-title">Capability Center</h1>
          <p className="module-subtitle">
            One composable surface for core tools, installed plugins, and connected MCP servers.
          </p>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <Link className="btn btn-sm" href="/os/marketplace">
            Marketplace
          </Link>
          <Link className="btn btn-sm" href="/os/integrations/mcp">
            MCP servers
          </Link>
        </div>
      </div>

      <div className="module-widgets-grid" style={{ marginTop: 24, marginBottom: 24 }}>
        {(["all", "builtin", "marketplace", "mcp"] as const).map((key) => {
          const count = key === "all" ? data.count || 0 : data.source_counts?.[key] || 0;
          const meta = key === "all" ? { label: "All capabilities", icon: "✦" } : SOURCE_META[key];
          return (
            <button
              key={key}
              className="module-widget"
              onClick={() => setSource(key)}
              style={{
                textAlign: "left",
                border:
                  source === key
                    ? `1px solid ${key === "all" ? "var(--aeon-primary)" : SOURCE_META[key].tone}`
                    : undefined,
                cursor: "pointer",
              }}
            >
              <div
                style={{
                  color: key === "all" ? "var(--aeon-primary)" : SOURCE_META[key].tone,
                  fontSize: 20,
                }}
              >
                {meta.icon}
              </div>
              <div className="stat-value" style={{ marginTop: 8 }}>
                {count}
              </div>
              <div className="stat-label">{meta.label}</div>
            </button>
          );
        })}
      </div>

      <section className="module-widget" style={{ marginBottom: 20 }}>
        <div
          style={{
            display: "flex",
            gap: 12,
            flexWrap: "wrap",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div>
            <h2 style={{ margin: 0 }}>Discoverable now</h2>
            <p className="text-muted" style={{ margin: "6px 0 0" }}>
              {filtered.length} capabilities available to this workspace.
            </p>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <input
              className="input"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search capabilities…"
            />
            <button className="btn btn-sm" onClick={load} disabled={loading}>
              {loading ? "Refreshing…" : "Refresh"}
            </button>
          </div>
        </div>
      </section>

      {error && (
        <div className="notice notice-error" style={{ marginBottom: 18 }}>
          {error}
        </div>
      )}
      <section className="module-widget" style={{ marginTop: 22, marginBottom: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
          <div>
            <div className="eyebrow">GOVERNANCE STREAM</div>
            <h2 style={{ margin: "8px 0 4px" }}>Capability decisions</h2>
            <p className="text-muted" style={{ margin: 0 }}>
              Recent allowed and denied invocations for this workspace. Arguments are never exposed.
            </p>
          </div>
          <button className="btn btn-sm" onClick={loadAudit} disabled={auditLoading}>
            {auditLoading ? "Loading…" : "Refresh audit"}
          </button>
        </div>
        <div style={{ marginTop: 16, display: "grid", gap: 8 }}>
          {(audit.logs || []).map((log) => {
            const metadata = log.metadata || {};
            const allowed = metadata.decision === "allowed";
            return (
              <div
                key={log.id || `${log.timestamp}-${metadata.capability_id}`}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  gap: 14,
                  alignItems: "center",
                  flexWrap: "wrap",
                  padding: "11px 12px",
                  border: "1px solid var(--aeon-border)",
                  borderRadius: 10,
                  background: "rgba(255,255,255,.02)",
                }}
              >
                <div>
                  <strong style={{ fontFamily: "monospace" }}>{metadata.capability_id || "unknown capability"}</strong>
                  <div className="text-muted" style={{ fontSize: 12, marginTop: 4 }}>
                    {metadata.reason || "unknown decision"} · {metadata.user_role || "unknown role"}
                    {metadata.policy_violation_count ? ` · ${metadata.policy_violation_count} policy violation(s)` : ""}
                  </div>
                </div>
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <span className="badge" style={{ color: allowed ? "#86efac" : "#fca5a5" }}>
                    {allowed ? "allowed" : "denied"}
                  </span>
                  <span className="text-muted" style={{ fontSize: 12 }}>
                    {log.timestamp ? new Date(log.timestamp).toLocaleString() : "—"}
                  </span>
                </div>
              </div>
            );
          })}
          {!auditLoading && (audit.logs || []).length === 0 && (
            <div className="text-muted" style={{ padding: "12px 0" }}>No capability decisions recorded yet.</div>
          )}
        </div>
      </section>

      {loading ? (
        <div className="module-widget">Loading capability registry…</div>
      ) : filtered.length === 0 ? (
        <div className="module-widget">
          No capabilities match this filter. Install a plugin or sync an MCP server to extend AEON.
        </div>
      ) : (
        <section className="module-widgets-grid">
          {filtered.map((capability) => {
            const meta = SOURCE_META[capability.source];
            return (
              <button
                key={capability.id}
                className="module-widget"
                onClick={() => openCapability(capability)}
                style={{
                  textAlign: "left",
                  cursor: "pointer",
                  transition: "transform .18s ease, border-color .18s ease",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    gap: 10,
                    alignItems: "center",
                  }}
                >
                  <span style={{ color: meta.tone, fontSize: 20 }}>{meta.icon}</span>
                  <span className="badge" style={{ color: meta.tone }}>
                    {meta.label}
                  </span>
                </div>
                <h3 style={{ margin: "16px 0 8px" }}>{capability.name}</h3>
                <p className="text-muted" style={{ minHeight: 42, margin: 0 }}>
                  {capability.description || "No description provided."}
                </p>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 16 }}>
                  {capability.permissions.map((permission) => (
                    <span className="badge" key={permission}>
                      {permission}
                    </span>
                  ))}
                  {capability.verified && (
                    <span className="badge" style={{ color: "#86efac" }}>
                      verified
                    </span>
                  )}
                </div>
              </button>
            );
          })}
        </section>
      )}

      {selected && (
        <div className="modal-backdrop" onClick={() => setSelected(null)}>
          <div
            className="module-widget"
            onClick={(event) => event.stopPropagation()}
            style={{ width: "min(720px, calc(100vw - 32px))", maxHeight: "85vh", overflow: "auto" }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                gap: 16,
                alignItems: "flex-start",
              }}
            >
              <div>
                <div className="eyebrow">{SOURCE_META[selected.source].label} CAPABILITY</div>
                <h2 style={{ margin: "8px 0" }}>{selected.name}</h2>
                <p className="text-muted">{selected.description}</p>
              </div>
              <button className="btn btn-sm" onClick={() => setSelected(null)}>
                Close
              </button>
            </div>
            <div style={{ marginTop: 18 }}>
              <label className="input-label" htmlFor="capability-args">
                Arguments (JSON)
              </label>
              <textarea
                id="capability-args"
                className="input"
                rows={8}
                value={argumentsText}
                onChange={(event) => setArgumentsText(event.target.value)}
                style={{ width: "100%", fontFamily: "monospace" }}
              />
              <p className="text-muted" style={{ fontSize: 12 }}>
                Schema: {JSON.stringify(selected.input_schema)}
              </p>
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 16 }}>
              <button className="btn btn-primary" onClick={invoke} disabled={invoking}>
                {invoking ? "Invoking…" : "Invoke capability"}
              </button>
            </div>
            {result !== null && (
              <pre className="code-block" style={{ marginTop: 18, whiteSpace: "pre-wrap" }}>
                {JSON.stringify(result, null, 2)}
              </pre>
            )}
          </div>
        </div>
      )}
    </main>
  );
}
