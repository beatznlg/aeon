"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

interface AutomationRule {
  id: string;
  name: string;
  event_type: string;
  condition: Record<string, any>;
  action_type: string;
  action_config: Record<string, any>;
  enabled: boolean;
  approval_required?: boolean;
  schedule_type?: "event" | "cron";
  cron_expression?: string;
  last_run_at?: string;
  next_run_at?: string;
  created_at: string;
}

interface Execution {
  id: string;
  event_type: string;
  status: string;
  created_at: string;
  result?: Record<string, any>;
}

interface InboundWebhook {
  id: string;
  name: string;
  token: string;
  created_at: string;
}

const EVENT_TYPES = [
  "swarm_status",
  "workflow_status",
  "notification",
  "api_key_created",
  "api_key_revoked",
  "workspace_activity",
  "system",
  "inbound_webhook",
];

const ACTION_TYPES = ["webhook", "outbound_webhook", "swarm", "workflow"];

function TestConditionButton({ condition }: { condition: Record<string, any> }) {
  const [payload, setPayload] = useState<string>('{"status": "failed", "severity": 5}');
  const [result, setResult] = useState<{ matches?: boolean; error?: string } | null>(null);
  const [loading, setLoading] = useState(false);

  async function test() {
    setLoading(true);
    setResult(null);
    try {
      let parsedPayload: any = {};
      try {
        parsedPayload = JSON.parse(payload);
      } catch (e: any) {
        setResult({ error: "Invalid payload JSON" });
        setLoading(false);
        return;
      }
      const res = await fetch("/api/automations/test-condition", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ condition, payload: parsedPayload }),
      });
      const data = await res.json();
      if (data.ok) {
        setResult({ matches: data.matches });
      } else {
        setResult({ error: data.error || "Test failed" });
      }
    } catch (e: any) {
      setResult({ error: e.message || "Test failed" });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ marginTop: 8, padding: 12, border: "1px solid var(--border)", borderRadius: 8 }}>
      <label style={{ display: "block", marginBottom: 6, fontSize: "0.8rem", fontWeight: 600 }}>Test payload (JSON)</label>
      <textarea
        className="input"
        rows={3}
        value={payload}
        onChange={(e) => setPayload(e.target.value)}
        style={{ marginBottom: 8 }}
      />
      <button type="button" className="btn btn-sm" onClick={test} disabled={loading}>
        {loading ? "Testing…" : "Test Condition"}
      </button>
      {result && (
        <div style={{ marginTop: 8, fontSize: "0.85rem" }}>
          {typeof result.matches === "boolean" ? (
            <span style={{ color: result.matches ? "#22c55e" : "#ef4444", fontWeight: 600 }}>
              {result.matches ? "✅ Matches" : "❌ Does not match"}
            </span>
          ) : (
            <span style={{ color: "#ef4444" }}>{result.error}</span>
          )}
        </div>
      )}
    </div>
  );
}

export default function AutomationsPage() {
  const [rules, setRules] = useState<AutomationRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<AutomationRule | null>(null);
  const [executions, setExecutions] = useState<Execution[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [webhooks, setWebhooks] = useState<InboundWebhook[]>([]);
  const [webhookName, setWebhookName] = useState("");
  const [copiedToken, setCopiedToken] = useState<string | null>(null);

  const [form, setForm] = useState<Partial<AutomationRule>>({
    name: "",
    event_type: "workflow_status",
    condition: {},
    action_type: "webhook",
    action_config: {},
    enabled: true,
    approval_required: false,
    schedule_type: "event",
    cron_expression: "",
  });

  useEffect(() => {
    loadRules();
    loadWebhooks();
  }, []);

  async function loadRules() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/automations");
      const data = await res.json();
      if (data.ok && Array.isArray(data.rules)) {
        setRules(data.rules);
      } else {
        setError(data.error || "Failed to load rules");
      }
    } catch (e: any) {
      setError(e.message || "Failed to load rules");
    } finally {
      setLoading(false);
    }
  }

  async function loadWebhooks() {
    try {
      const res = await fetch("/api/inbound-webhooks");
      const data = await res.json();
      if (data.ok && Array.isArray(data.webhooks)) {
        setWebhooks(data.webhooks);
      }
    } catch {}
  }

  async function createWebhook(e: React.FormEvent) {
    e.preventDefault();
    try {
      const res = await fetch("/api/inbound-webhooks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: webhookName || "Inbound Webhook" }),
      });
      const data = await res.json();
      if (data.ok) {
        setWebhookName("");
        await loadWebhooks();
      } else {
        setError(data.error || "Failed to create webhook");
      }
    } catch (e: any) {
      setError(e.message || "Failed to create webhook");
    }
  }

  async function deleteWebhook(id: string) {
    if (!confirm("Delete this inbound webhook? External systems using it will stop working.")) return;
    try {
      await fetch(`/api/inbound-webhooks/${id}`, { method: "DELETE" });
      await loadWebhooks();
    } catch {}
  }

  function copyUrl(url: string) {
    navigator.clipboard.writeText(url).then(() => {
      setCopiedToken(url);
      setTimeout(() => setCopiedToken(null), 2000);
    });
  }

  async function loadExecutions(rule: AutomationRule) {
    setSelected(rule);
    setExecutions([]);
    try {
      const res = await fetch(`/api/automations/${rule.id}/executions`);
      const data = await res.json();
      if (data.ok && Array.isArray(data.executions)) {
        setExecutions(data.executions);
      }
    } catch {}
  }

  async function createRule(e: React.FormEvent) {
    e.preventDefault();
    try {
      const res = await fetch("/api/automations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (data.ok) {
        setShowForm(false);
        setForm({
          name: "",
          event_type: "workflow_status",
          condition: {},
          action_type: "webhook",
          action_config: {},
          enabled: true,
          approval_required: false,
          schedule_type: "event",
          cron_expression: "",
        });
        await loadRules();
      } else {
        setError(data.error || "Failed to create rule");
      }
    } catch (e: any) {
      setError(e.message || "Failed to create rule");
    }
  }

  async function toggleRule(rule: AutomationRule) {
    try {
      const res = await fetch(`/api/automations/${rule.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: !rule.enabled }),
      });
      const data = await res.json();
      if (data.ok) {
        await loadRules();
      }
    } catch {}
  }

  async function deleteRule(id: string) {
    if (!confirm("Delete this automation rule?")) return;
    try {
      await fetch(`/api/automations/${id}`, { method: "DELETE" });
      await loadRules();
      if (selected?.id === id) setSelected(null);
    } catch {}
  }

  async function runRuleNow(id: string) {
    try {
      const res = await fetch(`/api/automations/${id}/run`, { method: "POST" });
      const data = await res.json();
      if (data.ok) {
        alert("Rule executed successfully");
      } else {
        setError(data.error || "Failed to run rule");
      }
    } catch (e: any) {
      setError(e.message || "Failed to run rule");
    }
  }

  function updateActionConfig(key: string, value: string) {
    setForm((prev) => ({
      ...prev,
      action_config: { ...(prev.action_config || {}), [key]: value },
    }));
  }

  return (
    <div className="os-page" style={{ padding: 24 }}>
      <header className="os-header" style={{ marginBottom: 20, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h1 style={{ background: "var(--grad)", WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent" }}>
            🤖 Automations
          </h1>
          <p className="dashboard-subtitle">Event-driven rules that trigger webhooks, swarms, or workflows.</p>
        </div>
        <div style={{ display: "flex", gap: 12 }}>
          <button className="btn btn-primary" onClick={() => setShowForm(true)}>
            + New Rule
          </button>
          <Link href="/os" className="btn btn-sm">
            ← Back to OS
          </Link>
        </div>
      </header>

      {error && (
        <div className="module-alert danger" style={{ marginBottom: 16 }}>
          {error}
        </div>
      )}

      {showForm && (
        <section
          style={{
            border: "1px solid var(--border)",
            borderRadius: 12,
            padding: 20,
            background: "var(--bg)",
            marginBottom: 24,
          }}
        >
          <h3 style={{ marginTop: 0 }}>Create Automation Rule</h3>
          <form onSubmit={createRule}>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 16, marginBottom: 16 }}>
              <div>
                <label style={{ display: "block", marginBottom: 6, fontSize: "0.8rem", fontWeight: 600 }}>Name</label>
                <input
                  className="input"
                  value={form.name || ""}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="e.g. Failed workflow alert"
                  required
                />
              </div>
              <div>
                <label style={{ display: "block", marginBottom: 6, fontSize: "0.8rem", fontWeight: 600 }}>Event Type</label>
                <select
                  className="input"
                  value={form.event_type}
                  onChange={(e) => setForm({ ...form, event_type: e.target.value })}
                >
                  {EVENT_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label style={{ display: "block", marginBottom: 6, fontSize: "0.8rem", fontWeight: 600 }}>Action Type</label>
                <select
                  className="input"
                  value={form.action_type}
                  onChange={(e) => setForm({ ...form, action_type: e.target.value, action_config: {} })}
                >
                  {ACTION_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div style={{ marginBottom: 16 }}>
              <label style={{ display: "block", marginBottom: 6, fontSize: "0.8rem", fontWeight: 600 }}>Condition (JSON)</label>
              <textarea
                className="input"
                rows={3}
                value={JSON.stringify(form.condition || {})}
                onChange={(e) => {
                  try {
                    setForm({ ...form, condition: JSON.parse(e.target.value) });
                  } catch {}
                }}
                placeholder='{"status": "failed"}'
              />
              <div style={{ fontSize: "0.75rem", color: "var(--fg-mute)", marginTop: 4 }}>
                Operators: {"$eq"}, {"$neq"}, {"$gt"}, {"$lt"}, {"$gte"}, {"$lte"}, {"$in"}, {"$contains"}, {"$exists"}, {"$regex"}. Use {"$and"} / {"$or"} / {"$not"} for logic.
              </div>
              <TestConditionButton condition={form.condition || {}} />
            </div>

            <div style={{ marginBottom: 16, display: "flex", alignItems: "center", gap: 8 }}>
              <input
                type="checkbox"
                id="approval_required"
                checked={!!form.approval_required}
                onChange={(e) => setForm({ ...form, approval_required: e.target.checked })}
              />
              <label htmlFor="approval_required" style={{ fontSize: "0.85rem", fontWeight: 600 }}>
                Require human approval before executing
              </label>
            </div>

            <div style={{ marginBottom: 16 }}>
              <label style={{ display: "block", marginBottom: 6, fontSize: "0.8rem", fontWeight: 600 }}>
                Trigger
              </label>
              <div style={{ display: "flex", gap: 12 }}>
                <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "0.85rem" }}>
                  <input
                    type="radio"
                    name="schedule_type"
                    value="event"
                    checked={form.schedule_type === "event"}
                    onChange={() => setForm({ ...form, schedule_type: "event" })}
                  />
                  Event-driven
                </label>
                <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "0.85rem" }}>
                  <input
                    type="radio"
                    name="schedule_type"
                    value="cron"
                    checked={form.schedule_type === "cron"}
                    onChange={() => setForm({ ...form, schedule_type: "cron" })}
                  />
                  Scheduled (cron)
                </label>
              </div>
            </div>

            {form.schedule_type === "cron" && (
              <div style={{ marginBottom: 16 }}>
                <label style={{ display: "block", marginBottom: 6, fontSize: "0.8rem", fontWeight: 600 }}>
                  Cron Expression
                </label>
                <input
                  className="input"
                  value={form.cron_expression || ""}
                  onChange={(e) => setForm({ ...form, cron_expression: e.target.value })}
                  placeholder="*/5 * * * *"
                  required={form.schedule_type === "cron"}
                />
                <div style={{ fontSize: "0.75rem", color: "var(--fg-mute)", marginTop: 4 }}>
                  Standard 5-field cron: minute hour day month weekday
                </div>
              </div>
            )}

            <div style={{ marginBottom: 16 }}>
              <label style={{ display: "block", marginBottom: 6, fontSize: "0.8rem", fontWeight: 600 }}>Action Config</label>
              {form.action_type === "webhook" && (
                <input
                  className="input"
                  placeholder="Webhook URL"
                  onChange={(e) => updateActionConfig("url", e.target.value)}
                />
              )}
              {form.action_type === "outbound_webhook" && (
                <>
                  <select
                    className="input"
                    value={(form.action_config?.method as string) || "POST"}
                    onChange={(e) => updateActionConfig("method", e.target.value)}
                    style={{ marginBottom: 8 }}
                  >
                    {["GET", "POST", "PUT", "PATCH", "DELETE"].map((m) => (
                      <option key={m} value={m}>
                        {m}
                      </option>
                    ))}
                  </select>
                  <input
                    className="input"
                    placeholder="URL (supports {{ event.payload.key }} templates)"
                    onChange={(e) => updateActionConfig("url", e.target.value)}
                    style={{ marginBottom: 8 }}
                  />
                  <textarea
                    className="input"
                    rows={3}
                    placeholder="Headers (JSON)"
                    onChange={(e) => {
                      try {
                        updateActionConfig("headers", e.target.value ? JSON.parse(e.target.value) : {});
                      } catch {}
                    }}
                    style={{ marginBottom: 8 }}
                  />
                  <textarea
                    className="input"
                    rows={3}
                    placeholder="Body (JSON or text)"
                    onChange={(e) => updateActionConfig("body", e.target.value)}
                  />
                  <div style={{ fontSize: "0.75rem", color: "var(--fg-mute)", marginTop: 4 }}>
                    Use templates like {"{{ event.payload.issue }}"}, {"{{ event.type }}"}, {"{{ rule.name }}"} in URL,
                    headers, and body.
                  </div>
                </>
              )}
              {form.action_type === "swarm" && (
                <>
                  <input
                    className="input"
                    placeholder="Prompt"
                    onChange={(e) => updateActionConfig("prompt", e.target.value)}
                    style={{ marginBottom: 8 }}
                  />
                  <input
                    className="input"
                    placeholder="App IDs (comma separated)"
                    onChange={(e) => updateActionConfig("app_ids", e.target.value)}
                  />
                </>
              )}
              {form.action_type === "workflow" && (
                <>
                  <input
                    className="input"
                    placeholder="Workflow ID"
                    onChange={(e) => updateActionConfig("workflow_id", e.target.value)}
                    style={{ marginBottom: 8 }}
                  />
                  <input
                    className="input"
                    placeholder="Initial input"
                    onChange={(e) => updateActionConfig("initial_input", e.target.value)}
                  />
                </>
              )}
            </div>

            <div style={{ display: "flex", gap: 12 }}>
              <button type="submit" className="btn btn-primary">
                Save Rule
              </button>
              <button type="button" className="btn" onClick={() => setShowForm(false)}>
                Cancel
              </button>
            </div>
          </form>
        </section>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 360px", gap: 24 }}>
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
          ) : rules.length === 0 ? (
            <div style={{ padding: 60, textAlign: "center", color: "var(--fg-mute)" }}>
              <div style={{ fontSize: "2rem", marginBottom: 12, opacity: 0.5 }}>🤖</div>
              <p>No automation rules yet.</p>
              <p style={{ fontSize: "0.78rem" }}>Create a rule to react to events in real time.</p>
            </div>
          ) : (
            <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
              {rules.map((rule) => (
                <li
                  key={rule.id}
                  style={{
                    padding: "14px 18px",
                    borderBottom: "1px solid var(--border)",
                    cursor: "pointer",
                    background: selected?.id === rule.id ? "var(--bg-1)" : "transparent",
                  }}
                  onClick={() => loadExecutions(rule)}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div>
                      <div style={{ fontWeight: 600 }}>{rule.name}</div>
                      <div style={{ fontSize: "0.78rem", color: "var(--fg-mute)" }}>
                        {rule.schedule_type === "cron" ? `⏰ ${rule.cron_expression}` : rule.event_type} → {rule.action_type}
                      </div>
                      {rule.schedule_type === "cron" && (
                        <div style={{ fontSize: "0.72rem", color: "var(--fg-mute)" }}>
                          {rule.next_run_at
                            ? `Next run: ${new Date(rule.next_run_at).toLocaleString()}`
                            : "Next run: not scheduled"}
                          {rule.last_run_at && ` · Last run: ${new Date(rule.last_run_at).toLocaleString()}`}
                        </div>
                      )}
                    </div>
                    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                      {rule.approval_required && (
                        <span
                          style={{
                            fontSize: "0.72rem",
                            padding: "2px 8px",
                            borderRadius: 999,
                            background: "#f59e0b20",
                            color: "#f59e0b",
                          }}
                        >
                          approval
                        </span>
                      )}
                      <span
                        style={{
                          fontSize: "0.72rem",
                          padding: "2px 8px",
                          borderRadius: 999,
                          background: rule.enabled ? "#22c55e20" : "#94a3b820",
                          color: rule.enabled ? "#22c55e" : "var(--fg-mute)",
                        }}
                      >
                        {rule.enabled ? "enabled" : "disabled"}
                      </span>
                      <button
                        className="btn btn-sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleRule(rule);
                        }}
                      >
                        {rule.enabled ? "Disable" : "Enable"}
                      </button>
                      <button
                        className="btn btn-sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          runRuleNow(rule.id);
                        }}
                      >
                        Run Now
                      </button>
                      <button
                        className="btn btn-sm btn-danger"
                        onClick={(e) => {
                          e.stopPropagation();
                          deleteRule(rule.id);
                        }}
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section
          style={{
            border: "1px solid var(--border)",
            borderRadius: 12,
            background: "var(--bg)",
            padding: 20,
            minHeight: 400,
          }}
        >
          <h3 style={{ marginTop: 0 }}>Recent Executions</h3>
          {selected ? (
            executions.length === 0 ? (
              <p style={{ color: "var(--fg-mute)" }}>No executions for this rule yet.</p>
            ) : (
              <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
                {executions.map((ex) => (
                  <li
                    key={ex.id}
                    style={{
                      padding: "10px 0",
                      borderBottom: "1px solid var(--border)",
                      fontSize: "0.85rem",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span>{ex.event_type}</span>
                      <span
                        style={{
                          color: ex.status === "triggered" ? "#22c55e" : "#ef4444",
                          fontWeight: 600,
                        }}
                      >
                        {ex.status}
                      </span>
                    </div>
                    <div style={{ color: "var(--fg-mute)", fontSize: "0.72rem" }}>
                      {new Date(ex.created_at).toLocaleString()}
                    </div>
                  </li>
                ))}
              </ul>
            )
          ) : (
            <p style={{ color: "var(--fg-mute)" }}>Select a rule to view executions.</p>
          )}
        </section>
      </div>

      <section
        style={{
          border: "1px solid var(--border)",
          borderRadius: 12,
          padding: 20,
          background: "var(--bg)",
          marginTop: 24,
        }}
      >
        <h3 style={{ marginTop: 0 }}>🔗 Inbound Webhooks</h3>
        <p style={{ color: "var(--fg-mute)", fontSize: "0.85rem" }}>
          External services can POST to these URLs to trigger AEON automations. Create a webhook, then build a rule with
          Event Type <strong>inbound_webhook</strong>.
        </p>
        <form onSubmit={createWebhook} style={{ display: "flex", gap: 12, marginBottom: 16 }}>
          <input
            className="input"
            placeholder="Webhook name"
            value={webhookName}
            onChange={(e) => setWebhookName(e.target.value)}
            style={{ flex: 1 }}
          />
          <button type="submit" className="btn btn-primary">
            Create Webhook
          </button>
        </form>
        {webhooks.length === 0 ? (
          <p style={{ color: "var(--fg-mute)" }}>No inbound webhooks yet.</p>
        ) : (
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {webhooks.map((hook) => {
              const url = `${typeof window !== "undefined" ? window.location.origin : ""}/inbound/${hook.token}`;
              return (
                <li
                  key={hook.id}
                  style={{
                    padding: "12px 0",
                    borderBottom: "1px solid var(--border)",
                  }}
                >
                  <div style={{ fontWeight: 600 }}>{hook.name}</div>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      marginTop: 6,
                      fontSize: "0.78rem",
                      fontFamily: "monospace",
                      wordBreak: "break-all",
                    }}
                  >
                    <span style={{ color: "var(--fg-mute)", flex: 1 }}>{url}</span>
                    <button className="btn btn-sm" onClick={() => copyUrl(url)}>
                      {copiedToken === url ? "Copied!" : "Copy"}
                    </button>
                    <button className="btn btn-sm btn-danger" onClick={() => deleteWebhook(hook.id)}>
                      Delete
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}
