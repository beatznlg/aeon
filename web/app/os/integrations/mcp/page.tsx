"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { getAuthHeaders } from "@/lib/flask-auth";

type McpTool = {
  name: string;
  description?: string;
  inputSchema?: Record<string, any>;
};

type McpServer = {
  id: string;
  workspace_id: string;
  name: string;
  url: string;
  enabled: boolean;
  added_at: number;
  last_synced: number | null;
  token_masked: string;
  tool_count: number;
  tools: McpTool[];
  server_info: Record<string, any>;
};

type AgentTool = {
  server_id: string;
  server_name: string;
  tool: string;
  description: string;
  input_schema: Record<string, any>;
  source: string;
};

const PROTOCOL_BADGE = "MCP · JSON-RPC 2.0 · Streamable HTTP";

export default function McpPage() {
  const [servers, setServers] = useState<McpServer[]>([]);
  const [agentTools, setAgentTools] = useState<AgentTool[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [form, setForm] = useState({ name: "", url: "", token: "", enabled: true });
  const [saving, setSaving] = useState(false);
  const [busy, setBusy] = useState<Record<string, string>>({});

  // tool-call modal state
  const [callFor, setCallFor] = useState<McpServer | null>(null);
  const [callTool, setCallTool] = useState("");
  const [callArgs, setCallArgs] = useState("{}");
  const [callLoading, setCallLoading] = useState(false);
  const [callResult, setCallResult] = useState<any>(null);
  const [callError, setCallError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [serversRes, toolsRes] = await Promise.all([
        fetch("/api/os/mcp", { headers: getAuthHeaders(), cache: "no-store" }).then((r) =>
          r.json()
        ),
        fetch("/api/os/mcp/agent-tools", { headers: getAuthHeaders(), cache: "no-store" }).then(
          (r) => r.json()
        ),
      ]);
      if (serversRes.ok) setServers(serversRes.servers || []);
      else setError(serversRes.error || "failed to load MCP servers");
      if (toolsRes.ok) setAgentTools(toolsRes.tools || []);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const setBusyKey = (id: string, action: string) => setBusy((prev) => ({ ...prev, [id]: action }));

  const clearBusyKey = (id: string) =>
    setBusy((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });

  const addServer = async () => {
    setError(null);
    setNotice(null);
    if (!form.name.trim() || !form.url.trim()) {
      setError("Name and URL are required");
      return;
    }
    setSaving(true);
    try {
      const res = await fetch("/api/os/mcp", {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify({
          name: form.name.trim(),
          url: form.url.trim(),
          token: form.token.trim(),
          enabled: form.enabled,
        }),
      });
      const data = await res.json();
      if (data.ok) {
        setNotice(`Registered "${data.server.name}" — sync its tools to start using them.`);
        setForm({ name: "", url: "", token: "", enabled: true });
        await loadData();
      } else {
        setError(data.error || "failed to register server");
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  };

  const removeServer = async (server: McpServer) => {
    if (!window.confirm(`Remove MCP server "${server.name}"? Its tools leave the workspace.`))
      return;
    setBusyKey(server.id, "deleting");
    try {
      const res = await fetch(`/api/os/mcp/${server.id}`, {
        method: "DELETE",
        headers: getAuthHeaders(),
      });
      const data = await res.json();
      if (data.ok) {
        setNotice(`Removed "${server.name}".`);
        await loadData();
      } else {
        setError(data.error || "failed to remove server");
      }
    } catch (e) {
      setError(String(e));
    } finally {
      clearBusyKey(server.id);
    }
  };

  const toggleServer = async (server: McpServer, enabled: boolean) => {
    setBusyKey(server.id, enabled ? "enabling" : "disabling");
    try {
      const res = await fetch(`/api/os/mcp/${server.id}/${enabled ? "enable" : "disable"}`, {
        method: "POST",
        headers: getAuthHeaders(),
      });
      const data = await res.json();
      if (data.ok) setNotice(`"${server.name}" is now ${enabled ? "enabled" : "disabled"}.`);
      else setError(data.error || "toggle failed");
      await loadData();
    } catch (e) {
      setError(String(e));
    } finally {
      clearBusyKey(server.id);
    }
  };

  const syncServer = async (server: McpServer) => {
    setBusyKey(server.id, "syncing");
    setNotice(null);
    try {
      const res = await fetch(`/api/os/mcp/${server.id}/refresh`, {
        method: "POST",
        headers: getAuthHeaders(),
      });
      const data = await res.json();
      if (data.ok) {
        setNotice(
          `Synced "${server.name}" — ${data.tool_count} tool${data.tool_count === 1 ? "" : "s"} discovered.`
        );
      } else {
        setError(data.error || "sync failed (is the server reachable and MCP-compatible?)");
      }
      await loadData();
    } catch (e) {
      setError(String(e));
    } finally {
      clearBusyKey(server.id);
    }
  };

  const openCall = (server: McpServer) => {
    setCallFor(server);
    setCallTool(server.tools[0]?.name || "");
    setCallArgs("{}");
    setCallResult(null);
    setCallError(null);
  };

  const runToolCall = async () => {
    if (!callFor || !callTool) return;
    setCallLoading(true);
    setCallResult(null);
    setCallError(null);
    let argumentsParsed: Record<string, any>;
    try {
      argumentsParsed = JSON.parse(callArgs || "{}");
    } catch {
      setCallError('Arguments must be valid JSON (e.g. {"key": "value"})');
      setCallLoading(false);
      return;
    }
    try {
      const res = await fetch("/api/os/mcp/tools/call", {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify({
          server_id: callFor.id,
          tool: callTool,
          arguments: argumentsParsed,
        }),
      });
      const data = await res.json();
      if (data.ok) setCallResult(data.result);
      else setCallError(data.error || "tool call failed");
    } catch (e) {
      setCallError(String(e));
    } finally {
      setCallLoading(false);
    }
  };

  const enabledCount = servers.filter((s) => s.enabled).length;
  const syncedCount = servers.reduce((acc, s) => acc + (s.tools?.length || 0), 0);

  const groupedAgentTools = useMemo(() => {
    const groups: Record<string, AgentTool[]> = {};
    for (const t of agentTools) {
      (groups[t.server_name] = groups[t.server_name] || []).push(t);
    }
    return groups;
  }, [agentTools]);

  const schemaSummary = (schema: Record<string, any> | undefined): string => {
    if (!schema) return "no input schema";
    const props = schema.properties ? Object.keys(schema.properties) : [];
    if (!props.length) return "no arguments";
    return props.join(", ");
  };

  if (loading) {
    return (
      <div className="os-page">
        <div style={{ padding: 40, textAlign: "center", color: "var(--fg-mute)" }}>
          Loading MCP servers…
        </div>
      </div>
    );
  }

  return (
    <div className="os-page">
      <header className="os-header">
        <div>
          <Link href="/os/integrations" className="os-back">
            ← Integrations
          </Link>
          <h1>🔌 MCP Servers</h1>
          <p className="dashboard-subtitle">
            Register Model Context Protocol servers and expose their tools to agents, automations,
            and workflows. {PROTOCOL_BADGE}
          </p>
        </div>
      </header>

      {error && <div className="module-alert danger">{error}</div>}
      {notice && <div className="module-alert success">{notice}</div>}

      {/* ── Stats ── */}
      <div className="module-widgets-grid" style={{ marginBottom: 20 }}>
        {[
          { label: "Registered", value: servers.length },
          { label: "Enabled", value: enabledCount },
          { label: "Synced tools", value: syncedCount },
          { label: "Agent-visible tools", value: agentTools.length },
        ].map((stat) => (
          <div key={stat.label} className="module-widget">
            <h3>{stat.label}</h3>
            <div style={{ fontSize: 28, fontWeight: 700, color: "var(--fg)" }}>{stat.value}</div>
          </div>
        ))}
      </div>

      {/* ── Register ── */}
      <section className="module-widget" style={{ marginBottom: 24 }}>
        <h3>➕ Register an MCP server</h3>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
            gap: 8,
          }}
        >
          <input
            className="os-input"
            placeholder="Name (e.g. Filesystem, GitHub, Weather)"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
          <input
            className="os-input"
            placeholder="URL (https://mcp.example.com)"
            value={form.url}
            onChange={(e) => setForm({ ...form, url: e.target.value })}
          />
          <input
            className="os-input"
            placeholder="Bearer token (optional)"
            value={form.token}
            type="password"
            onChange={(e) => setForm({ ...form, token: e.target.value })}
          />
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 16, marginTop: 10 }}>
          <label style={{ display: "flex", alignItems: "center", gap: 8, color: "var(--fg-soft)" }}>
            <input
              type="checkbox"
              checked={form.enabled}
              onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
            />
            Enabled on registration
          </label>
          <button className="btn btn-primary" onClick={addServer} disabled={saving}>
            {saving ? "Registering…" : "Register server"}
          </button>
        </div>
      </section>

      {/* ── Servers ── */}
      <section className="module-widgets-grid">
        {servers.length === 0 && (
          <div className="module-widget" style={{ gridColumn: "1 / -1" }}>
            <p style={{ color: "var(--fg-mute)" }}>
              No MCP servers registered yet. Add one above — after registering, hit{" "}
              <strong>Sync tools</strong> to discover its tools.
            </p>
          </div>
        )}
        {servers.map((server) => (
          <div
            key={server.id}
            className="module-widget"
            style={{ display: "flex", flexDirection: "column", gap: 8 }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "flex-start",
                gap: 8,
              }}
            >
              <div>
                <h3 style={{ margin: 0 }}>
                  {server.enabled ? "🟢" : "⚪"} {server.name}
                </h3>
                <code style={{ fontSize: 12, color: "var(--fg-mute)", wordBreak: "break-all" }}>
                  {server.url}
                </code>
              </div>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  padding: "2px 8px",
                  borderRadius: 999,
                  border: "1px solid var(--border)",
                  color: server.enabled ? "var(--success)" : "var(--fg-mute)",
                  whiteSpace: "nowrap",
                }}
              >
                {server.enabled ? "ENABLED" : "DISABLED"}
              </span>
            </div>

            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: 6,
                fontSize: 12,
                color: "var(--fg-soft)",
              }}
            >
              <span>
                Tools: <strong>{server.tool_count}</strong>
              </span>
              <span>·</span>
              <span>
                {server.last_synced
                  ? `Synced ${new Date(server.last_synced * 1000).toLocaleString()}`
                  : "Never synced"}
              </span>
              {server.token_masked && (
                <>
                  <span>·</span>
                  <span>Token {server.token_masked}</span>
                </>
              )}
            </div>

            {server.server_info && (server.server_info.name || server.server_info.version) && (
              <div style={{ fontSize: 12, color: "var(--fg-mute)" }}>
                {server.server_info.name}
                {server.server_info.version ? ` · v${server.server_info.version}` : ""}
                {server.server_info.instructions ? " · has instructions" : ""}
              </div>
            )}

            {/* tools preview */}
            {server.tools && server.tools.length > 0 && (
              <div style={{ maxHeight: 120, overflowY: "auto", fontSize: 12 }}>
                {server.tools.map((tool) => (
                  <div
                    key={tool.name}
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      gap: 8,
                      padding: "4px 8px",
                      marginBottom: 4,
                      border: "1px solid var(--border)",
                      borderRadius: 8,
                      background: "var(--bg, transparent)",
                    }}
                  >
                    <code style={{ fontSize: 12 }}>{tool.name}</code>
                    <span style={{ color: "var(--fg-mute)", textAlign: "right", maxWidth: "55%" }}>
                      {tool.description || schemaSummary(tool.inputSchema)}
                    </span>
                  </div>
                ))}
              </div>
            )}

            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: 8,
                marginTop: "auto",
                paddingTop: 4,
              }}
            >
              <button
                className="btn btn-sm"
                onClick={() => syncServer(server)}
                disabled={!!busy[server.id]}
              >
                {busy[server.id] === "syncing" ? "Syncing…" : "⟳ Sync tools"}
              </button>
              <button
                className="btn btn-sm"
                onClick={() => toggleServer(server, !server.enabled)}
                disabled={!!busy[server.id]}
              >
                {server.enabled ? "Disable" : "Enable"}
              </button>
              <button
                className="btn btn-sm"
                onClick={() => openCall(server)}
                disabled={!!busy[server.id] || server.tools.length === 0}
                title={server.tools.length === 0 ? "Sync tools first" : "Call a tool"}
              >
                ▶ Call tool
              </button>
              <button
                className="btn btn-sm"
                style={{ marginLeft: "auto", color: "var(--danger, #ef4444)" }}
                onClick={() => removeServer(server)}
                disabled={!!busy[server.id]}
              >
                {busy[server.id] === "deleting" ? "Removing…" : "🗑 Remove"}
              </button>
            </div>
          </div>
        ))}
      </section>

      {/* ── Agent discoverability ── */}
      <section style={{ marginTop: 28 }}>
        <h2 style={{ fontSize: 18, marginBottom: 12 }}>🤖 What agents can call</h2>
        {agentTools.length === 0 ? (
          <div className="module-widget">
            <p style={{ color: "var(--fg-mute)" }}>
              No MCP tools are visible to agents yet. Register and sync an enabled server above.
            </p>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {Object.entries(groupedAgentTools).map(([serverName, tools]) => (
              <div key={serverName} className="module-widget">
                <h3 style={{ marginBottom: 8 }}>
                  🟢 {serverName}{" "}
                  <span style={{ fontSize: 12, fontWeight: 400, color: "var(--fg-mute)" }}>
                    ({tools.length} tool{tools.length === 1 ? "" : "s"})
                  </span>
                </h3>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                  {tools.map((t) => (
                    <div
                      key={t.server_id + t.tool}
                      style={{
                        padding: "6px 10px",
                        border: "1px solid var(--border)",
                        borderRadius: 8,
                        background: "var(--bg, transparent)",
                        maxWidth: 320,
                      }}
                    >
                      <code style={{ fontSize: 12 }}>{t.tool}</code>
                      <div style={{ fontSize: 11, color: "var(--fg-mute)", marginTop: 2 }}>
                        {t.description || "No description"}
                      </div>
                      <div style={{ fontSize: 10, color: "var(--fg-mute)", marginTop: 2 }}>
                        args: {schemaSummary(t.input_schema)}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* ── Tool call modal ── */}
      {callFor && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.6)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 120,
            padding: 16,
          }}
          onClick={() => setCallFor(null)}
        >
          <div
            style={{
              background: "var(--bg-1, #1e293b)",
              border: "1px solid var(--border, #334155)",
              borderRadius: 12,
              maxWidth: 640,
              width: "100%",
              maxHeight: "85vh",
              overflowY: "auto",
              padding: 20,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: 12,
              }}
            >
              <h3 style={{ margin: 0 }}>▶ Call MCP tool · {callFor.name}</h3>
              <button className="btn btn-sm" onClick={() => setCallFor(null)}>
                ✕
              </button>
            </div>

            <label
              style={{ display: "block", fontSize: 12, color: "var(--fg-soft)", marginBottom: 6 }}
            >
              Tool
            </label>
            <select
              className="os-input"
              value={callTool}
              onChange={(e) => setCallTool(e.target.value)}
              style={{ marginBottom: 12 }}
            >
              {callFor.tools.map((tool) => (
                <option key={tool.name} value={tool.name}>
                  {tool.name}
                  {tool.description ? ` — ${tool.description}` : ""}
                </option>
              ))}
            </select>

            <label
              style={{ display: "block", fontSize: 12, color: "var(--fg-soft)", marginBottom: 6 }}
            >
              Arguments (JSON)
            </label>
            <textarea
              className="os-input"
              rows={5}
              style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 12 }}
              value={callArgs}
              onChange={(e) => setCallArgs(e.target.value)}
              placeholder='{"query": "hello"}'
            />

            <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
              <button className="btn btn-primary" onClick={runToolCall} disabled={callLoading}>
                {callLoading ? "Calling…" : "Call tool"}
              </button>
            </div>

            {callError && (
              <div className="module-alert danger" style={{ marginTop: 12 }}>
                {callError}
              </div>
            )}
            {callResult !== null && callResult !== undefined && (
              <div
                className="module-alert"
                style={{ marginTop: 12, maxHeight: 240, overflowY: "auto" }}
              >
                <div style={{ fontSize: 11, fontWeight: 600, marginBottom: 6 }}>Result</div>
                <pre
                  style={{
                    margin: 0,
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                    fontSize: 12,
                    fontFamily: "var(--font-mono, monospace)",
                  }}
                >
                  {typeof callResult === "string"
                    ? callResult
                    : JSON.stringify(callResult, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
