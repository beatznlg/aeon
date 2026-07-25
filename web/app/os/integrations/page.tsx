"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

type Integration = {
  id: string;
  name: string;
  type: string;
  base_url: string;
  enabled: boolean;
  secrets: Record<string, string>;
  options: Record<string, any>;
  webhook_secret?: string;
  created_at: number;
  updated_at: number;
};

type Delivery = {
  id: string;
  integration_id: string;
  timestamp: number;
  payload: Record<string, any>;
  response_status: number;
  error_message?: string;
};

type CatalogItem = {
  id: string;
  name: string;
  icon: string;
  description: string;
  required_secrets: string[];
  optional_secrets: string[];
  adapter_type: string;
};

const TYPES = ["rest", "supabase", "github", "huggingface", "slack"];

const ICONS: Record<string, string> = {
  rest: "🌐",
  supabase: "⚡",
  github: "🐙",
  huggingface: "🤗",
  slack: "💬",
};

const generateId = () => Math.random().toString(36).slice(2, 9);

export default function IntegrationsPage() {
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [deliveries, setDeliveries] = useState<Delivery[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [activeTab, setActiveTab] = useState<"connectors" | "marketplace" | "webhooks">("connectors");
  const [catalog, setCatalog] = useState<CatalogItem[]>([]);
  const [healthResults, setHealthResults] = useState<Record<string, any>>({});
  const [healthChecking, setHealthChecking] = useState(false);

  const [form, setForm] = useState<Integration>({
    id: "",
    name: "",
    type: "rest",
    base_url: "",
    enabled: true,
    secrets: {},
    options: {},
    webhook_secret: "",
    created_at: 0,
    updated_at: 0,
  });

  const [secretKey, setSecretKey] = useState("");
  const [secretValue, setSecretValue] = useState("");
  const [optionKey, setOptionKey] = useState("");
  const [optionValue, setOptionValue] = useState("");
  const [runResponse, setRunResponse] = useState<any>(null);
  const [runLoading, setRunLoading] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [intRes, delRes, catRes] = await Promise.all([
        fetch("/api/os/integrations", { cache: "no-store" }).then((r) => r.json()),
        fetch("/api/os/webhooks/deliveries", { cache: "no-store" }).then((r) => r.json()),
        fetch("/api/os/integrations/catalog", { cache: "no-store" }).then((r) => r.json()),
      ]);
      if (intRes.ok) setIntegrations(intRes.integrations || []);
      else setError(intRes.error || "failed to load integrations");
      if (delRes.ok) setDeliveries(delRes.deliveries || []);
      if (catRes.ok) setCatalog(catRes.catalog || []);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  const runHealthCheck = async () => {
    setHealthChecking(true);
    const results: Record<string, any> = {};
    for (const item of integrations) {
      try {
        const res = await fetch(`/api/os/integrations/${item.id}/run`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ endpoint: "", method: "GET" }),
        });
        const data = await res.json();
        results[item.id] = data;
      } catch {
        results[item.id] = { ok: false, error: "request failed" };
      }
    }
    setHealthResults(results);
    setHealthChecking(false);
  };

  const createFromCatalog = async (item: CatalogItem) => {
    setForm({
      id: "",
      name: item.name,
      type: item.adapter_type,
      base_url: item.id === "rest" ? "https://" : "",
      enabled: true,
      secrets: {},
      options: {},
      webhook_secret: "",
      created_at: 0,
      updated_at: 0,
    });
    setActiveTab("connectors");
  };

  const save = async () => {
    setError(null);
    const body = { ...form };
    if (!body.id) body.id = generateId();
    const res = await fetch("/api/os/integrations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (data.ok) {
      setIntegrations((prev) => {
        const existing = prev.find((i) => i.id === data.integration.id);
        if (existing) {
          return prev.map((i) => (i.id === data.integration.id ? data.integration : i));
        }
        return [...prev, data.integration];
      });
      resetForm();
    } else {
      setError(data.error || "failed to save integration");
    }
  };

  const remove = async (id: string) => {
    const res = await fetch(`/api/os/integrations/${id}`, { method: "DELETE" });
    const data = await res.json();
    if (data.ok) {
      setIntegrations((prev) => prev.filter((i) => i.id !== id));
    }
  };

  const run = async (id: string) => {
    setRunLoading(true);
    setRunResponse(null);
    try {
      const res = await fetch(`/api/os/integrations/${id}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ endpoint: "", method: "GET" }),
      });
      const data = await res.json();
      setRunResponse(data);
    } catch (e) {
      setRunResponse({ ok: false, error: String(e) });
    }
    setRunLoading(false);
  };

  const addSecret = () => {
    if (!secretKey) return;
    setForm((prev) => ({ ...prev, secrets: { ...prev.secrets, [secretKey]: secretValue } }));
    setSecretKey("");
    setSecretValue("");
  };

  const removeSecret = (key: string) => {
    setForm((prev) => {
      const next = { ...prev.secrets };
      delete next[key];
      return { ...prev, secrets: next };
    });
  };

  const addOption = () => {
    if (!optionKey) return;
    setForm((prev) => ({ ...prev, options: { ...prev.options, [optionKey]: optionValue } }));
    setOptionKey("");
    setOptionValue("");
  };

  const removeOption = (key: string) => {
    setForm((prev) => {
      const next = { ...prev.options };
      delete next[key];
      return { ...prev, options: next };
    });
  };

  const resetForm = () => {
    setForm({
      id: "",
      name: "",
      type: "rest",
      base_url: "",
      enabled: true,
      secrets: {},
      options: {},
      webhook_secret: "",
      created_at: 0,
      updated_at: 0,
    });
  };

  const selectForEdit = (item: Integration) => {
    setForm({ ...item });
  };

  if (loading) {
    return (
      <div className="os-page">
        <div style={{ padding: 40, textAlign: "center", color: "var(--fg-mute)" }}>Loading integrations…</div>
      </div>
    );
  }

  return (
    <div className="os-page">
      <header className="os-header">
        <div>
          <Link href="/os" className="os-back">← OS Launcher</Link>
          <h1>🔗 API Gateway & Integrations</h1>
          <p className="dashboard-subtitle">Connect AEON to external REST APIs, webhooks, and third-party services</p>
        </div>
      </header>

      {error && <div className="module-alert danger">{error}</div>}

      {/* ── Tabs ── */}
      <div className="login-tabs" style={{ marginBottom: 20 }}>
        <button className={`login-tab ${activeTab === "connectors" ? "active" : ""}`} onClick={() => setActiveTab("connectors")}>
          🔌 Connectors ({integrations.length})
        </button>
        <button className={`login-tab ${activeTab === "marketplace" ? "active" : ""}`} onClick={() => setActiveTab("marketplace")}>
          🏪 Marketplace
        </button>
        <button className={`login-tab ${activeTab === "webhooks" ? "active" : ""}`} onClick={() => setActiveTab("webhooks")}>
          📡 Webhooks
        </button>
      </div>

      {/* ════════════════════════════ Connectors Tab ════════════════════════════ */}
      {activeTab === "connectors" && (
        <>
          <section className="module-widgets-grid" style={{ marginBottom: 24 }}>
            <div className="module-widget">
              <h3>{form.id ? "✏️ Edit Connector" : "➕ New Connector"}</h3>
              <input
                className="os-input"
                placeholder="Name"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
              <select
                className="os-input"
                value={form.type}
                onChange={(e) => setForm({ ...form, type: e.target.value })}
                style={{ marginTop: 8 }}
              >
                {TYPES.map((t) => (
                  <option key={t} value={t}>{ICONS[t] || "🔌"} {t}</option>
                ))}
              </select>
              <input
                className="os-input"
                placeholder="Base URL / Endpoint"
                value={form.base_url}
                onChange={(e) => setForm({ ...form, base_url: e.target.value })}
                style={{ marginTop: 8 }}
              />
              <label style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 8, color: "var(--fg-soft)" }}>
                <input
                  type="checkbox"
                  checked={form.enabled}
                  onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
                />
                Enabled
              </label>

              <h4 style={{ marginTop: 16 }}>🔐 Secrets</h4>
              <div style={{ display: "flex", gap: 8 }}>
                <input className="os-input" placeholder="key" value={secretKey} onChange={(e) => setSecretKey(e.target.value)} />
                <input className="os-input" placeholder="value" value={secretValue} onChange={(e) => setSecretValue(e.target.value)} type="password" />
                <button className="btn btn-sm" onClick={addSecret}>Add</button>
              </div>
              {Object.entries(form.secrets).map(([k, v]) => (
                <div key={k} className="module-alert" style={{ marginTop: 8, display: "flex", justifyContent: "space-between" }}>
                  <code>{k}</code>
                  <button className="btn btn-sm" onClick={() => removeSecret(k)}>×</button>
                </div>
              ))}

              <h4 style={{ marginTop: 16 }}>⚙️ Options</h4>
              <div style={{ display: "flex", gap: 8 }}>
                <input className="os-input" placeholder="key" value={optionKey} onChange={(e) => setOptionKey(e.target.value)} />
                <input className="os-input" placeholder="value" value={optionValue} onChange={(e) => setOptionValue(e.target.value)} />
                <button className="btn btn-sm" onClick={addOption}>Add</button>
              </div>
              {Object.entries(form.options).map(([k, v]) => (
                <div key={k} className="module-alert" style={{ marginTop: 8, display: "flex", justifyContent: "space-between" }}>
                  <code>{k}: {String(v)}</code>
                  <button className="btn btn-sm" onClick={() => removeOption(k)}>×</button>
                </div>
              ))}

              <input
                className="os-input"
                placeholder="Webhook secret (optional)"
                value={form.webhook_secret}
                onChange={(e) => setForm({ ...form, webhook_secret: e.target.value })}
                type="password"
                style={{ marginTop: 8 }}
              />

              <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
                <button className="btn btn-primary" onClick={save}>💾 Save</button>
                {form.id && <button className="btn btn-sm" onClick={resetForm}>New</button>}
              </div>
            </div>

            <div className="module-widget">
              <h3>🔌 Configured Connectors ({integrations.length})</h3>
              {integrations.length === 0 ? (
                <p className="module-empty">No integrations yet. Browse the Marketplace tab to add one.</p>
              ) : (
                <>
                  <button className="btn btn-sm" onClick={runHealthCheck} disabled={healthChecking} style={{ marginBottom: 12 }}>
                    {healthChecking ? "Checking..." : "🩺 Run Health Check"}
                  </button>
                  <ul className="os-goal-list">
                    {integrations.map((item) => {
                      const health = healthResults[item.id];
                      return (
                        <li key={item.id} style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", padding: "8px 0", borderBottom: "1px solid var(--border, #1e293b)" }}>
                          <span className="integration-status-dot" style={{
                            width: 10, height: 10, borderRadius: "50%", flexShrink: 0,
                            background: health ? (health.ok ? "#22c55e" : "#ef4444") : item.enabled ? "#6366f1" : "#71717a",
                            boxShadow: health?.ok ? "0 0 6px rgba(34,197,94,0.5)" : "none",
                          }} />
                          <span style={{ flex: 1 }}>
                            <strong>{item.name}</strong>
                            <span className="os-status-pill active" style={{ marginLeft: 6 }}>{item.type}</span>
                            <br />
                            <small style={{ color: item.enabled ? "var(--fg-soft)" : "var(--fg-mute)" }}>
                              {item.enabled ? "active" : "disabled"}
                              {health?.latency_s !== undefined && ` · ${(health.latency_s * 1000).toFixed(0)}ms`}
                            </small>
                          </span>
                          <button className="btn btn-sm" onClick={() => selectForEdit(item)}>Edit</button>
                          <button className="btn btn-sm" onClick={() => run(item.id)} disabled={runLoading}>Run</button>
                          <button className="btn btn-sm btn-danger" onClick={() => remove(item.id)}>×</button>
                        </li>
                      );
                    })}
                  </ul>
                </>
              )}
            </div>
          </section>

          {runResponse && (
            <section className="module-widget" style={{ marginBottom: 24 }}>
              <h3>Last Run Result</h3>
              <pre className="os-pre">{JSON.stringify(runResponse, null, 2)}</pre>
            </section>
          )}
        </>
      )}

      {/* ════════════════════════════ Marketplace Tab ════════════════════════════ */}
      {activeTab === "marketplace" && (
        <section>
          <p style={{ marginBottom: 16, color: "var(--fg-soft)" }}>
            Browse available integration types. Click "Add" to create a new connector pre-configured for that type.
          </p>
          <div className="integration-marketplace">
            {catalog.map((item) => (
              <div key={item.id} className="integration-marketplace-card">
                <div className="integration-marketplace-icon">{item.icon}</div>
                <div className="integration-marketplace-info">
                  <h4>{item.name}</h4>
                  <p>{item.description}</p>
                  <div className="integration-marketplace-meta">
                    {item.required_secrets.length > 0 && (
                      <span className="marketplace-secrets">
                        Requires: {item.required_secrets.join(", ")}
                      </span>
                    )}
                    <span className="marketplace-type">{item.adapter_type}</span>
                  </div>
                </div>
                <button className="btn btn-primary btn-sm" onClick={() => createFromCatalog(item)}>
                  + Add
                </button>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ════════════════════════════ Webhooks Tab ════════════════════════════ */}
      {activeTab === "webhooks" && (
        <section>
          <div className="module-widgets-grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
            <div className="module-widget">
              <h3>📡 Webhook Endpoints</h3>
              {integrations.filter((i) => i.webhook_secret).length === 0 ? (
                <p className="module-empty">
                  No webhook endpoints configured. Edit a connector and add a <strong>webhook_secret</strong> to enable webhook verification.
                </p>
              ) : (
                <ul className="os-goal-list">
                  {integrations.filter((i) => i.webhook_secret).map((item) => (
                    <li key={item.id} style={{ padding: "12px 0", borderBottom: "1px solid var(--border, #1e293b)" }}>
                      <strong>{item.name}</strong>
                      <span className="os-status-pill active" style={{ marginLeft: 8 }}>{item.type}</span>
                      <div style={{ marginTop: 8, fontSize: "0.8rem", color: "var(--fg-soft)" }}>
                        <div>Receive URL: <code style={{ fontSize: "0.75rem", background: "var(--bg)", padding: "2px 6px", borderRadius: 4 }}>
                          POST /webhooks/receive/{item.id}
                        </code></div>
                        <div style={{ marginTop: 4 }}>Signing secret: <code style={{ fontSize: "0.75rem" }}>********</code></div>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="module-widget">
              <h3>📋 Recent Deliveries</h3>
              {deliveries.length === 0 ? (
                <p className="module-empty">No webhook deliveries yet.</p>
              ) : (
                <div style={{ display: "grid", gap: 6, maxHeight: 400, overflowY: "auto" }}>
                  {deliveries.slice(0, 30).map((d) => (
                    <details key={d.id} className="module-alert" style={{ marginBottom: 2 }}>
                      <summary style={{ cursor: "pointer", fontSize: "0.8rem" }}>
                        <span style={{ color: d.response_status < 400 ? "#22c55e" : "#ef4444", fontWeight: 600 }}>
                          [{d.response_status}]
                        </span>{' '}
                        {d.integration_id}{' '}
                        <span style={{ color: "var(--fg-mute)" }}>
                          {new Date(d.timestamp * 1000).toLocaleString()}
                        </span>
                      </summary>
                      <pre className="os-pre" style={{ fontSize: "0.72rem", maxHeight: 150, overflow: "auto" }}>
                        {JSON.stringify(d.payload, null, 2)}
                      </pre>
                      {d.error_message && <div className="module-alert danger" style={{ fontSize: "0.8rem", padding: 6 }}>{d.error_message}</div>}
                    </details>
                  ))}
                </div>
              )}
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
