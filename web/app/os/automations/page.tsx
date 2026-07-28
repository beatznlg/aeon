"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

interface AutomationRule {
  id: string;
  name: string;
  event_type: string;
  condition: Record<string, any>;
  action_type?: string;
  action_config?: Record<string, any>;
  actions?: {
    type: string;
    config: Record<string, any>;
    run_if?: Record<string, any>;
    loop_over?: string;
    on_error?: { type: string; config: Record<string, any> };
    continue_on_error?: boolean;
  }[];
  enabled: boolean;
  approval_required?: boolean;
  schedule_type?: "event" | "cron";
  cron_expression?: string;
  last_run_at?: string;
  next_run_at?: string;
  cooldown_minutes?: number;
  last_triggered_at?: string;
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

const ACTION_TYPES = [
  "webhook",
  "outbound_webhook",
  "swarm",
  "workflow",
  "delay",
  "wait_for_event",
  "set_variable",
  "get_variable",
  "delete_variable",
  "increment_variable",
  "call_rule",
  "transform",
  "parallel",
];

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

function ActionConfigEditor({
  actionType,
  config,
  updateConfig,
}: {
  actionType: string;
  config: Record<string, any>;
  updateConfig: (key: string, value: any) => void;
}) {
  return (
    <>
      {actionType === "webhook" && (
        <input
          className="input"
          placeholder="Webhook URL"
          onChange={(e) => updateConfig("url", e.target.value)}
        />
      )}
      {actionType === "outbound_webhook" && (
        <>
          <select
            className="input"
            value={(config?.method as string) || "POST"}
            onChange={(e) => updateConfig("method", e.target.value)}
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
            onChange={(e) => updateConfig("url", e.target.value)}
            style={{ marginBottom: 8 }}
          />
          <textarea
            className="input"
            rows={3}
            placeholder="Headers (JSON)"
            onChange={(e) => {
              try {
                updateConfig("headers", e.target.value ? JSON.parse(e.target.value) : {});
              } catch {}
            }}
            style={{ marginBottom: 8 }}
          />
          <textarea
            className="input"
            rows={3}
            placeholder="Body (JSON or text)"
            onChange={(e) => updateConfig("body", e.target.value)}
          />
          <div style={{ fontSize: "0.75rem", color: "var(--fg-mute)", marginTop: 4 }}>
            Use templates like {"{{ event.payload.issue }}"}, {"{{ event.type }}"}, {"{{ rule.name }}"} in URL,
            headers, and body.
          </div>
        </>
      )}
      {actionType === "swarm" && (
        <>
          <input
            className="input"
            placeholder="Prompt"
            onChange={(e) => updateConfig("prompt", e.target.value)}
            style={{ marginBottom: 8 }}
          />
          <input
            className="input"
            placeholder="App IDs (comma separated)"
            onChange={(e) => updateConfig("app_ids", e.target.value)}
          />
        </>
      )}
      {actionType === "workflow" && (
        <>
          <input
            className="input"
            placeholder="Workflow ID"
            onChange={(e) => updateConfig("workflow_id", e.target.value)}
            style={{ marginBottom: 8 }}
          />
          <input
            className="input"
            placeholder="Initial input"
            onChange={(e) => updateConfig("initial_input", e.target.value)}
          />
        </>
      )}
      {actionType === "delay" && (
        <>
          <input
            className="input"
            type="number"
            min={1}
            placeholder="Duration (minutes)"
            onChange={(e) => updateConfig("duration_minutes", parseInt(e.target.value || "1", 10))}
            style={{ marginBottom: 8 }}
          />
          <div style={{ fontSize: "0.75rem", color: "var(--fg-mute)" }}>
            Pause the automation chain for this many minutes, then resume from the next step.
          </div>
        </>
      )}
      {actionType === "wait_for_event" && (
        <>
          <input
            className="input"
            placeholder="Event type to wait for (e.g. stripe.invoice.paid)"
            onChange={(e) => updateConfig("event_type", e.target.value)}
            style={{ marginBottom: 8 }}
          />
          <input
            className="input"
            placeholder="Correlation key path (e.g. data.id)"
            onChange={(e) => updateConfig("correlation_key", e.target.value)}
            style={{ marginBottom: 8 }}
          />
          <input
            className="input"
            placeholder="Expected correlation value (supports {{ event.payload.x }} templates)"
            onChange={(e) => updateConfig("correlation_value", e.target.value)}
            style={{ marginBottom: 8 }}
          />
          <input
            className="input"
            type="number"
            min={1}
            placeholder="Timeout (minutes)"
            onChange={(e) => updateConfig("timeout_minutes", parseInt(e.target.value || "1440", 10))}
            style={{ marginBottom: 8 }}
          />
          <div style={{ fontSize: "0.75rem", color: "var(--fg-mute)" }}>
            Suspend the automation until an event of the specified type arrives with a matching correlation value. Resumes after the timeout if no matching event is received.
          </div>
        </>
      )}
      {(actionType === "set_variable" || actionType === "get_variable" || actionType === "delete_variable") && (
        <>
          <input
            className="input"
            placeholder="Variable key"
            onChange={(e) => updateConfig("key", e.target.value)}
            style={{ marginBottom: 8 }}
          />
          {actionType === "set_variable" && (
            <>
              <textarea
                className="input"
                rows={3}
                placeholder="Value (JSON)"
                onChange={(e) => {
                  try {
                    updateConfig("value", e.target.value ? JSON.parse(e.target.value) : null);
                  } catch {}
                }}
                style={{ marginBottom: 8 }}
              />
              <input
                className="input"
                type="number"
                min={1}
                placeholder="TTL (minutes, optional)"
                onChange={(e) => updateConfig("ttl_minutes", e.target.value ? parseInt(e.target.value, 10) : undefined)}
                style={{ marginBottom: 8 }}
              />
            </>
          )}
          <div style={{ fontSize: "0.75rem", color: "var(--fg-mute)" }}>
            {actionType === "set_variable" && "Store a variable in the workspace state. Reference it later with {{ state.MY_KEY }}."}
            {actionType === "get_variable" && "Read a workspace variable. The value is available in subsequent steps via {{ steps.N.value }}."}
            {actionType === "delete_variable" && "Remove a variable from the workspace state."}
          </div>
        </>
      )}
      {actionType === "increment_variable" && (
        <>
          <input
            className="input"
            placeholder="Variable key"
            onChange={(e) => updateConfig("key", e.target.value)}
            style={{ marginBottom: 8 }}
          />
          <input
            className="input"
            type="number"
            placeholder="Amount (default 1)"
            onChange={(e) => updateConfig("amount", parseFloat(e.target.value || "1"))}
            style={{ marginBottom: 8 }}
          />
          <div style={{ fontSize: "0.75rem", color: "var(--fg-mute)" }}>
            Atomically increment a numeric variable by the given amount. Creates the variable if it does not exist.
          </div>
        </>
      )}
      {actionType === "call_rule" && (
        <>
          <input
            className="input"
            placeholder="Target rule ID"
            onChange={(e) => updateConfig("rule_id", e.target.value)}
            style={{ marginBottom: 8 }}
          />
          <textarea
            className="input"
            rows={3}
            placeholder="Payload (JSON, supports {{ event.payload.key }} templates)"
            onChange={(e) => {
              try {
                updateConfig("payload", e.target.value ? JSON.parse(e.target.value) : {});
              } catch {}
            }}
            style={{ marginBottom: 8 }}
          />
          <input
            className="input"
            placeholder="Event type for synthetic sub-event (default: sub_request)"
            onChange={(e) => updateConfig("event_type", e.target.value)}
            style={{ marginBottom: 8 }}
          />
          <label style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8, fontSize: "0.85rem" }}>
            <input
              type="checkbox"
              defaultChecked
              onChange={(e) => updateConfig("wait_for_completion", e.target.checked)}
            />
            Wait for sub-rule to complete before continuing
          </label>
          <div style={{ fontSize: "0.75rem", color: "var(--fg-mute)" }}>
            Invoke another automation rule as a sub-workflow. The sub-rule&apos;s result is available via{" "}
            {"{{ steps.N.sub_result }}"}. Circular calls are blocked at a depth of 5.
          </div>
        </>
      )}
      {actionType === "transform" && (
        <>
          <select
            className="input"
            value={(config?.operation as string) || "math"}
            onChange={(e) => updateConfig("operation", e.target.value)}
            style={{ marginBottom: 8 }}
          >
            {["math", "date_format", "regex_extract", "json_parse", "json_stringify"].map((op) => (
              <option key={op} value={op}>
                {op}
              </option>
            ))}
          </select>
          {config?.operation === "math" && (
            <>
              <input
                className="input"
                type="number"
                placeholder="Left operand"
                onChange={(e) => updateConfig("left", parseFloat(e.target.value))}
                style={{ marginBottom: 8 }}
              />
              <select
                className="input"
                value={(config?.operator as string) || "+"}
                onChange={(e) => updateConfig("operator", e.target.value)}
                style={{ marginBottom: 8 }}
              >
                {["+", "-", "*", "/"].map((op) => (
                  <option key={op} value={op}>
                    {op}
                  </option>
                ))}
              </select>
              <input
                className="input"
                type="number"
                placeholder="Right operand"
                onChange={(e) => updateConfig("right", parseFloat(e.target.value))}
                style={{ marginBottom: 8 }}
              />
            </>
          )}
          {config?.operation === "date_format" && (
            <>
              <input
                className="input"
                placeholder="Input timestamp"
                onChange={(e) => updateConfig("input", e.target.value)}
                style={{ marginBottom: 8 }}
              />
              <input
                className="input"
                placeholder="Output strftime format (e.g. %Y-%m-%d %H:%M)"
                onChange={(e) => updateConfig("output_format", e.target.value)}
                style={{ marginBottom: 8 }}
              />
              <input
                className="input"
                placeholder="Input strptime format (optional)"
                onChange={(e) => updateConfig("input_format", e.target.value || undefined)}
                style={{ marginBottom: 8 }}
              />
            </>
          )}
          {config?.operation === "regex_extract" && (
            <>
              <input
                className="input"
                placeholder="Pattern"
                onChange={(e) => updateConfig("pattern", e.target.value)}
                style={{ marginBottom: 8 }}
              />
              <input
                className="input"
                placeholder="Input string"
                onChange={(e) => updateConfig("input", e.target.value)}
                style={{ marginBottom: 8 }}
              />
              <input
                className="input"
                type="number"
                placeholder="Group index (default 0)"
                onChange={(e) => updateConfig("group", parseInt(e.target.value || "0", 10))}
                style={{ marginBottom: 8 }}
              />
            </>
          )}
          {(config?.operation === "json_parse" || config?.operation === "json_stringify") && (
            <textarea
              className="input"
              rows={3}
              placeholder={
                config?.operation === "json_parse"
                  ? "JSON string to parse"
                  : "Value to serialize (JSON)"
              }
              onChange={(e) => {
                try {
                  updateConfig("input", e.target.value ? JSON.parse(e.target.value) : null);
                } catch {}
              }}
              style={{ marginBottom: 8 }}
            />
          )}
          <div style={{ fontSize: "0.75rem", color: "var(--fg-mute)" }}>
            Transform data and store the result in{" "}
            {"{{ steps.N.result }}"} for use by later steps.
          </div>
        </>
      )}
      {actionType === "parallel" && (
        <ParallelBranchEditor config={config} updateConfig={updateConfig} />
      )}
    </>
  );
}

interface ParallelBranch {
  name?: string;
  actions: { type: string; config: Record<string, any> }[];
}

function ParallelBranchEditor({
  config,
  updateConfig,
}: {
  config: Record<string, any>;
  updateConfig: (key: string, value: any) => void;
}) {
  const branches = (config?.branches || []) as ParallelBranch[];

  function updateBranches(next: ParallelBranch[]) {
    updateConfig("branches", next);
  }

  return (
    <div>
      <div style={{ fontSize: "0.75rem", color: "var(--fg-mute)", marginBottom: 12 }}>
        Run multiple action branches concurrently. Each branch has its own action chain.
      </div>
      {branches.map((branch, bidx) => (
        <div
          key={bidx}
          style={{
            border: "1px solid var(--border)",
            borderRadius: 8,
            padding: 12,
            marginBottom: 12,
          }}
        >
          <div style={{ display: "flex", gap: 8, marginBottom: 12, alignItems: "center" }}>
            <input
              className="input"
              placeholder="Branch name"
              value={branch.name || `Branch ${bidx + 1}`}
              onChange={(e) => {
                const next = [...branches];
                next[bidx] = { ...next[bidx], name: e.target.value };
                updateBranches(next);
              }}
              style={{ flex: 1 }}
            />
            <button
              type="button"
              className="btn btn-sm btn-danger"
              onClick={() => {
                const next = [...branches];
                next.splice(bidx, 1);
                updateBranches(next);
              }}
            >
              Remove
            </button>
          </div>

          {branch.actions.map((act, aidx) => (
            <div
              key={aidx}
              style={{
                marginBottom: 8,
                padding: 8,
                border: "1px dashed var(--border)",
                borderRadius: 6,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                <span style={{ fontSize: "0.8rem", fontWeight: 600 }}>Action {aidx + 1}</span>
                <button
                  type="button"
                  className="btn btn-sm btn-danger"
                  onClick={() => {
                    const next = [...branches];
                    next[bidx].actions = next[bidx].actions.filter((_, i) => i !== aidx);
                    updateBranches(next);
                  }}
                >
                  Remove
                </button>
              </div>
              <select
                className="input"
                value={act.type}
                onChange={(e) => {
                  const next = [...branches];
                  next[bidx].actions[aidx] = { ...next[bidx].actions[aidx], type: e.target.value, config: {} };
                  updateBranches(next);
                }}
                style={{ marginBottom: 8 }}
              >
                  {ACTION_TYPES.filter((t) => t !== "parallel").map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
              </select>
              <ActionConfigEditor
                actionType={act.type}
                config={act.config || {}}
                updateConfig={(k, v) => {
                  const next = [...branches];
                  next[bidx].actions[aidx] = {
                    ...next[bidx].actions[aidx],
                    config: { ...next[bidx].actions[aidx].config, [k]: v },
                  };
                  updateBranches(next);
                }}
              />
            </div>
          ))}
          <button
            type="button"
            className="btn btn-sm"
            onClick={() => {
              const next = [...branches];
              next[bidx].actions = [...(next[bidx].actions || []), { type: "webhook", config: {} }];
              updateBranches(next);
            }}
          >
            + Add Action to Branch
          </button>
        </div>
      ))}
      <button
        type="button"
        className="btn btn-sm"
        onClick={() => {
          updateBranches([
            ...branches,
            { name: `Branch ${branches.length + 1}`, actions: [{ type: "webhook", config: {} }] },
          ]);
        }}
      >
        + Add Branch
      </button>
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
  const [runResult, setRunResult] = useState<{ dry_run?: boolean; result?: any } | null>(null);
  const [showImportModal, setShowImportModal] = useState(false);
  const [showBlueprintsModal, setShowBlueprintsModal] = useState(false);
  const [blueprints, setBlueprints] = useState<any[]>([]);
  const [importText, setImportText] = useState("");
  const [importLoading, setImportLoading] = useState(false);
  const [importResult, setImportResult] = useState<{ ok?: boolean; imported?: number; error?: string } | null>(null);

  const [form, setForm] = useState<Partial<AutomationRule>>({
    name: "",
    event_type: "workflow_status",
    condition: {},
    action_type: "webhook",
    action_config: {},
    actions: [],
    enabled: true,
    approval_required: false,
    schedule_type: "event",
    cron_expression: "",
    cooldown_minutes: 0,
  });

  useEffect(() => {
    loadRules();
    loadWebhooks();
    loadBlueprints();
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
      const payload = { ...form };
      if (!payload.actions || payload.actions.length === 0) {
        delete payload.actions;
      }

      const res = await fetch("/api/automations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
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
          actions: [],
          enabled: true,
          approval_required: false,
          schedule_type: "event",
          cron_expression: "",
          cooldown_minutes: 0,
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

  async function runRuleNow(id: string, dryRun = false) {
    try {
      const res = await fetch(`/api/automations/${id}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dry_run: dryRun }),
      });
      const data = await res.json();
      if (data.ok) {
        if (dryRun) {
          setRunResult(data);
        } else {
          alert("Rule executed successfully");
        }
      } else {
        setError(data.error || "Failed to run rule");
      }
    } catch (e: any) {
      setError(e.message || "Failed to run rule");
    }
  }

  async function exportAllRules() {
    try {
      const res = await fetch("/api/automations/export");
      const data = await res.json();
      if (data.ok) {
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `aeon-automations-${new Date().toISOString()}.json`;
        a.click();
        URL.revokeObjectURL(url);
      } else {
        setError(data.error || "Failed to export rules");
      }
    } catch (e: any) {
      setError(e.message || "Failed to export rules");
    }
  }

  async function exportRule(rule: AutomationRule) {
    try {
      const res = await fetch(`/api/automations/export?rule_id=${rule.id}`);
      const data = await res.json();
      if (data.ok) {
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `aeon-automation-${rule.name.replace(/\s+/g, "_")}-${rule.id}.json`;
        a.click();
        URL.revokeObjectURL(url);
      } else {
        setError(data.error || "Failed to export rule");
      }
    } catch (e: any) {
      setError(e.message || "Failed to export rule");
    }
  }

  async function loadBlueprints() {
    try {
      const res = await fetch("/api/automations/blueprints");
      const data = await res.json();
      if (data.ok && Array.isArray(data.blueprints)) {
        setBlueprints(data.blueprints);
      }
    } catch {}
  }

  async function importRules() {
    setImportLoading(true);
    setImportResult(null);
    try {
      let payload: any;
      try {
        payload = JSON.parse(importText);
      } catch {
        setImportResult({ ok: false, error: "Invalid JSON" });
        setImportLoading(false);
        return;
      }
      const res = await fetch("/api/automations/import", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (data.ok) {
        setImportResult({ ok: true, imported: data.imported });
        setImportText("");
        await loadRules();
        setTimeout(() => setShowImportModal(false), 1500);
      } else {
        setImportResult({ ok: false, error: data.error || "Import failed" });
      }
    } catch (e: any) {
      setImportResult({ ok: false, error: e.message || "Import failed" });
    } finally {
      setImportLoading(false);
    }
  }

  function applyBlueprint(blueprint: any) {
    setForm({
      name: blueprint.name || "",
      event_type: blueprint.event_type || "workflow_status",
      condition: blueprint.condition || {},
      action_type: undefined,
      action_config: {},
      actions: (blueprint.actions || []).map((a: any) => ({ ...a })),
      enabled: blueprint.enabled ?? true,
      approval_required: false,
      schedule_type: blueprint.schedule_type || "event",
      cron_expression: blueprint.cron_expression || "",
      cooldown_minutes: blueprint.cooldown_minutes ?? 0,
    });
    setShowBlueprintsModal(false);
    setShowForm(true);
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
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <Link href="/os/automations/metrics" className="btn btn-sm">
            📊 Metrics
          </Link>
          <button className="btn" onClick={() => setShowImportModal(true)}>
            Import JSON
          </button>
          <button className="btn" onClick={exportAllRules}>
            Export All
          </button>
          <button className="btn btn-primary" onClick={() => setShowBlueprintsModal(true)}>
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
              {(!form.actions || form.actions.length === 0) && (
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
              )}
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
              <label style={{ display: "block", marginBottom: 6, fontSize: "0.8rem", fontWeight: 600 }}>
                Cooldown (minutes)
              </label>
              <input
                className="input"
                type="number"
                min={0}
                value={form.cooldown_minutes ?? 0}
                onChange={(e) => setForm({ ...form, cooldown_minutes: parseInt(e.target.value || "0", 10) })}
                placeholder="0"
              />
              <div style={{ fontSize: "0.75rem", color: "var(--fg-mute)", marginTop: 4 }}>
                Minimum minutes between execution. 0 = no cooldown.
              </div>
            </div>

            {(!form.actions || form.actions.length === 0) ? (
              <div style={{ marginBottom: 16 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                  <label style={{ fontSize: "0.8rem", fontWeight: 600 }}>Action Config</label>
                  <button
                    type="button"
                    className="btn btn-sm"
                    onClick={() =>
                      setForm({
                        ...form,
                        actions: [
                          { type: form.action_type || "webhook", config: form.action_config || {} },
                          { type: "webhook", config: {} },
                        ],
                      })
                    }
                  >
                    + Add Step (Chain)
                  </button>
                </div>
                <ActionConfigEditor
                  actionType={form.action_type || "webhook"}
                  config={form.action_config || {}}
                  updateConfig={updateActionConfig}
                />
              </div>
            ) : (
              <div style={{ marginBottom: 16 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                  <label style={{ fontSize: "0.8rem", fontWeight: 600 }}>Action Steps</label>
                  <button
                    type="button"
                    className="btn btn-sm"
                    onClick={() =>
                      setForm({
                        ...form,
                        actions: [...form.actions!, { type: "webhook", config: {} }],
                      })
                    }
                  >
                    + Add Step
                  </button>
                </div>
                {form.actions.map((act, idx) => (
                  <div key={idx} style={{ border: "1px solid var(--border)", padding: 12, borderRadius: 8, marginBottom: 8 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                      <span style={{ fontWeight: 600, fontSize: "0.85rem" }}>Step {idx + 1}</span>
                      <button
                        type="button"
                        className="btn btn-sm btn-danger"
                        onClick={() => {
                          const newActions = [...form.actions!];
                          newActions.splice(idx, 1);
                          setForm({ ...form, actions: newActions });
                        }}
                      >
                        Remove
                      </button>
                    </div>
                    <select
                      className="input"
                      value={act.type}
                      onChange={(e) => {
                        const newActions = [...form.actions!];
                        newActions[idx] = { ...newActions[idx], type: e.target.value, config: {} };
                        setForm({ ...form, actions: newActions });
                      }}
                      style={{ marginBottom: 8 }}
                    >
                      {ACTION_TYPES.map((t) => (
                        <option key={t} value={t}>
                          {t}
                        </option>
                      ))}
                    </select>
                    <input
                      className="input"
                      placeholder="Loop over (optional) e.g. {{ event.payload.items }}"
                      value={act.loop_over || ""}
                      onChange={(e) => {
                        const newActions = [...form.actions!];
                        newActions[idx] = { ...newActions[idx], loop_over: e.target.value || undefined };
                        setForm({ ...form, actions: newActions });
                      }}
                      style={{ marginBottom: 8 }}
                    />
                    <ActionConfigEditor
                      actionType={act.type}
                      config={act.config}
                      updateConfig={(k, v) => {
                        const newActions = [...form.actions!];
                        newActions[idx] = { ...newActions[idx], config: { ...newActions[idx].config, [k]: v } };
                        setForm({ ...form, actions: newActions });
                      }}
                    />
                    <div style={{ marginTop: 12, padding: 10, border: "1px dashed var(--border)", borderRadius: 6 }}>
                      <label style={{ fontSize: "0.75rem", fontWeight: 600, display: "block", marginBottom: 4 }}>
                        Run condition (run_if)
                      </label>
                      <textarea
                        className="input"
                        rows={3}
                        value={JSON.stringify(act.run_if || {})}
                        onChange={(e) => {
                          try {
                            const runIf = JSON.parse(e.target.value);
                            const newActions = [...form.actions!];
                            newActions[idx] = { ...newActions[idx], run_if: runIf };
                            setForm({ ...form, actions: newActions });
                          } catch {}
                        }}
                        placeholder='{"event.payload.status": "failed"}'
                        style={{ marginBottom: 4 }}
                      />
                      <div style={{ fontSize: "0.7rem", color: "var(--fg-mute)", marginTop: 4 }}>
                        Leave {"{}"} to always run. Paths: event.payload.x, steps.0.data.y, rule.name.
                      </div>
                    </div>

                    <div style={{ marginTop: 12, padding: 10, border: "1px dashed var(--border)", borderRadius: 6 }}>
                      <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "0.85rem", fontWeight: 600 }}>
                        <input
                          type="checkbox"
                          checked={!!act.continue_on_error}
                          onChange={(e) => {
                            const newActions = [...form.actions!];
                            newActions[idx] = { ...newActions[idx], continue_on_error: e.target.checked };
                            setForm({ ...form, actions: newActions });
                          }}
                        />
                        Continue to next step if this step fails
                      </label>
                      <div style={{ fontSize: "0.7rem", color: "var(--fg-mute)", marginTop: 4 }}>
                        When enabled, a failure here will not stop the chain; the on_error fallback (if any) still
                        runs first.
                      </div>
                    </div>

                    <div style={{ marginTop: 12, padding: 10, border: "1px dashed var(--border)", borderRadius: 6 }}>
                      <label style={{ fontSize: "0.75rem", fontWeight: 600, display: "block", marginBottom: 4 }}>
                        On-error fallback (on_error)
                      </label>
                      <select
                        className="input"
                        value={act.on_error?.type || ""}
                        onChange={(e) => {
                          const type = e.target.value || undefined;
                          const newActions = [...form.actions!];
                          newActions[idx] = {
                            ...newActions[idx],
                            on_error: type ? { type, config: act.on_error?.config || {} } : undefined,
                          };
                          setForm({ ...form, actions: newActions });
                        }}
                        style={{ marginBottom: 8 }}
                      >
                        <option value="">None</option>
                        {ACTION_TYPES.map((t) => (
                          <option key={t} value={t}>
                            {t}
                          </option>
                        ))}
                      </select>
                      {act.on_error?.type && (
                        <ActionConfigEditor
                          actionType={act.on_error.type}
                          config={act.on_error.config}
                          updateConfig={(k, v) => {
                            const newActions = [...form.actions!];
                            newActions[idx] = {
                              ...newActions[idx],
                              on_error: { ...newActions[idx].on_error!, config: { ...newActions[idx].on_error!.config, [k]: v } },
                            };
                            setForm({ ...form, actions: newActions });
                          }}
                        />
                      )}
                      <div style={{ fontSize: "0.7rem", color: "var(--fg-mute)", marginTop: 4 }}>
                        Runs when this step fails. Templates: {"{{ error.message }}"}, {"{{ error.step }}"}, event,
                        rule, steps.
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

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
                        {rule.schedule_type === "cron" ? `⏰ ${rule.cron_expression}` : rule.event_type} →{" "}
                        {rule.actions && rule.actions.length > 0
                          ? `${rule.actions[0].type} (${rule.actions.length} steps)`
                          : rule.action_type}
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
                        className="btn btn-sm"
                        style={{ background: "var(--accent)", color: "#fff" }}
                        onClick={(e) => {
                          e.stopPropagation();
                          runRuleNow(rule.id, true);
                        }}
                      >
                        Dry Run
                      </button>
                      <button
                        className="btn btn-sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          exportRule(rule);
                        }}
                      >
                        Export
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

      {runResult && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.6)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
            padding: 24,
          }}
          onClick={() => setRunResult(null)}
        >
          <div
            style={{
              background: "var(--bg)",
              border: "1px solid var(--border)",
              borderRadius: 12,
              maxWidth: 720,
              width: "100%",
              maxHeight: "80vh",
              overflow: "auto",
              padding: 24,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <h3 style={{ margin: 0 }}>{runResult.dry_run ? "Dry Run Result" : "Run Result"}</h3>
              <button className="btn btn-sm" onClick={() => setRunResult(null)}>
                Close
              </button>
            </div>
            <pre
              style={{
                background: "var(--bg-elevated)",
                border: "1px solid var(--border)",
                borderRadius: 8,
                padding: 12,
                fontSize: "0.8rem",
                overflow: "auto",
              }}
            >
              {JSON.stringify(runResult.result, null, 2)}
            </pre>
          </div>
        </div>
      )}

      {showImportModal && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.6)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
            padding: 24,
          }}
          onClick={() => setShowImportModal(false)}
        >
          <div
            style={{
              background: "var(--bg)",
              border: "1px solid var(--border)",
              borderRadius: 12,
              maxWidth: 640,
              width: "100%",
              maxHeight: "80vh",
              overflow: "auto",
              padding: 24,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <h3 style={{ margin: 0 }}>Import Automation Rules</h3>
              <button className="btn btn-sm" onClick={() => setShowImportModal(false)}>
                Close
              </button>
            </div>
            <p style={{ color: "var(--fg-mute)", fontSize: "0.85rem" }}>
              Paste the exported JSON below. You can import a single rule, an array of rules, or an object with a{" "}
              <code>rules</code> property.
            </p>
            <textarea
              className="input"
              rows={10}
              value={importText}
              onChange={(e) => setImportText(e.target.value)}
              placeholder='{"rules": [{"name": "..."}]}'
              style={{ marginBottom: 12, fontFamily: "monospace", fontSize: "0.8rem" }}
            />
            {importResult && (
              <div
                style={{
                  padding: 12,
                  borderRadius: 8,
                  marginBottom: 12,
                  background: importResult.ok ? "#22c55e20" : "#ef444420",
                  color: importResult.ok ? "#22c55e" : "#ef4444",
                  fontSize: "0.85rem",
                }}
              >
                {importResult.ok
                  ? `Imported ${importResult.imported} rule(s) successfully`
                  : importResult.error}
              </div>
            )}
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 12 }}>
              <button className="btn" onClick={() => setShowImportModal(false)}>
                Cancel
              </button>
              <button className="btn btn-primary" onClick={importRules} disabled={importLoading}>
                {importLoading ? "Importing…" : "Import Rules"}
              </button>
            </div>
          </div>
        </div>
      )}

      {showBlueprintsModal && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.6)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
            padding: 24,
          }}
          onClick={() => setShowBlueprintsModal(false)}
        >
          <div
            style={{
              background: "var(--bg)",
              border: "1px solid var(--border)",
              borderRadius: 12,
              maxWidth: 800,
              width: "100%",
              maxHeight: "80vh",
              overflow: "auto",
              padding: 24,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <h3 style={{ margin: 0 }}>Create Automation</h3>
              <button className="btn btn-sm" onClick={() => setShowBlueprintsModal(false)}>
                Close
              </button>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 16 }}>
              <button
                onClick={() => {
                  setShowBlueprintsModal(false);
                  setShowForm(true);
                }}
                style={{
                  padding: 16,
                  border: "1px dashed var(--border)",
                  borderRadius: 12,
                  background: "var(--bg-elevated)",
                  textAlign: "left",
                  cursor: "pointer",
                }}
              >
                <div style={{ fontWeight: 600, marginBottom: 4 }}>Blank Automation</div>
                <div style={{ fontSize: "0.78rem", color: "var(--fg-mute)" }}>Start from scratch with a custom rule.</div>
              </button>
              {blueprints.map((bp) => (
                <button
                  key={bp.id}
                  onClick={() => applyBlueprint(bp)}
                  style={{
                    padding: 16,
                    border: "1px solid var(--border)",
                    borderRadius: 12,
                    background: "var(--bg-elevated)",
                    textAlign: "left",
                    cursor: "pointer",
                  }}
                >
                  <div style={{ fontWeight: 600, marginBottom: 4 }}>{bp.name}</div>
                  <div style={{ fontSize: "0.78rem", color: "var(--fg-mute)" }}>{bp.description}</div>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
