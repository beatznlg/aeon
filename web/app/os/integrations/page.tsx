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

const TYPES = ["rest", "supabase", "github", "huggingface"];

const generateId = () => Math.random().toString(36).slice(2, 9);

export default function IntegrationsPage() {
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [deliveries, setDeliveries] = useState<Delivery[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
      const [intRes, delRes] = await Promise.all([
        fetch("/api/os/integrations", { cache: "no-store" }).then((r) => r.json()),
        fetch("/api/os/webhooks/deliveries", { cache: "no-store" }).then((r) => r.json()),
      ]);
      if (intRes.ok) setIntegrations(intRes.integrations || []);
      else setError(intRes.error || "failed to load integrations");
      if (delRes.ok) setDeliveries(delRes.deliveries || []);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
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

      <section className="module-widgets-grid" style={{ marginBottom: 24 }}>
        <div className="module-widget">
          <h3>{form.id ? "Edit Connector" : "New Connector"}</h3>
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
              <option key={t} value={t}>{t}</option>
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

          <h4 style={{ marginTop: 16 }}>Secrets</h4>
          <div style={{ display: "flex", gap: 8 }}>
            <input className="os-input" placeholder="key" value={secretKey} onChange={(e) => setSecretKey(e.target.value)} />
            <input className="os-input" placeholder="value" value={secretValue} onChange={(e) => setSecretValue(e.target.value)} type="password" />
            <button className="btn btn-sm" onClick={addSecret}>Add</button>
          </div>
          {Object.entries(form.secrets).map(([k, v]) => (
            <div key={k} className="module-alert" style={{ marginTop: 8, display: "flex", justifyContent: "space-between" }}>
              <code>{k}</code>
              <button className="btn btn-sm" onClick={() => removeSecret(k)}>Remove</button>
            </div>
          ))}

          <h4 style={{ marginTop: 16 }}>Options</h4>
          <div style={{ display: "flex", gap: 8 }}>
            <input className="os-input" placeholder="key" value={optionKey} onChange={(e) => setOptionKey(e.target.value)} />
            <input className="os-input" placeholder="value" value={optionValue} onChange={(e) => setOptionValue(e.target.value)} />
            <button className="btn btn-sm" onClick={addOption}>Add</button>
          </div>
          {Object.entries(form.options).map(([k, v]) => (
            <div key={k} className="module-alert" style={{ marginTop: 8, display: "flex", justifyContent: "space-between" }}>
              <code>{k}: {String(v)}</code>
              <button className="btn btn-sm" onClick={() => removeOption(k)}>Remove</button>
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
          <h3>Configured Connectors ({integrations.length})</h3>
          {integrations.length === 0 ? (
            <p className="module-empty">No integrations yet.</p>
          ) : (
            <ul className="os-goal-list">
              {integrations.map((item) => (
                <li key={item.id} style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                  <span style={{ flex: 1 }}>
                    <strong>{item.name}</strong> <span className="os-status-pill active">{item.type}</span>
                    <br />
                    <small>{item.enabled ? "enabled" : "disabled"}</small>
                  </span>
                  <button className="btn btn-sm" onClick={() => selectForEdit(item)}>Edit</button>
                  <button className="btn btn-sm" onClick={() => run(item.id)} disabled={runLoading}>Run</button>
                  <button className="btn btn-sm btn-danger" onClick={() => remove(item.id)}>×</button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      {runResponse && (
        <section className="module-widget" style={{ marginBottom: 24 }}>
          <h3>Last Run Result</h3>
          <pre className="os-pre">{JSON.stringify(runResponse, null, 2)}</pre>
        </section>
      )}

      <section className="module-widget">
        <h3>Recent Webhook Deliveries</h3>
        {deliveries.length === 0 ? (
          <p className="module-empty">No webhook deliveries yet.</p>
        ) : (
          <div style={{ display: "grid", gap: 8 }}>
            {deliveries.slice(0, 20).map((d) => (
              <details key={d.id} className="module-alert" style={{ marginBottom: 4 }}>
                <summary style={{ cursor: "pointer" }}>
                  {new Date(d.timestamp * 1000).toLocaleString()} — {d.integration_id} — status {d.response_status}
                </summary>
                <pre className="os-pre">{JSON.stringify(d.payload, null, 2)}</pre>
                {d.error_message && <div className="module-alert danger">{d.error_message}</div>}
              </details>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
