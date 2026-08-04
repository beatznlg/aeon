"use client";

import { useEffect, useMemo, useState } from "react";

type EntryPoint = Record<string, string>;

type Plugin = {
  id: string;
  name: string;
  version: string;
  description: string;
  author: string;
  category: string;
  icon: string;
  permissions: string[];
  entry_points: EntryPoint;
  config_schema: Record<
    string,
    { type?: string; default?: unknown; required?: boolean; description?: string }
  >;
  verified: boolean;
  source: string;
  tags: string[];
  installed: boolean;
  enabled: boolean;
  installed_version?: string | null;
};

type Summary = { plugins: number; verified: number; categories: string[]; version: number };

const CATEGORY_LABELS: Record<string, string> = {
  ai: "AI",
  analytics: "Analytics",
  automation: "Automation",
  communication: "Communication",
  data: "Data",
  devops: "DevOps",
  integration: "Integration",
  productivity: "Productivity",
  security: "Security",
  sector: "Sector",
};

const CATEGORY_ICONS: Record<string, string> = {
  ai: "🧠",
  analytics: "📊",
  automation: "⚙️",
  communication: "💬",
  data: "🗃️",
  devops: "🛠️",
  integration: "🔌",
  productivity: "🧩",
  security: "🛡️",
  sector: "🏭",
};

// Fixed, stable order for the filter bar (module categories first, sector last).
const CATEGORY_ORDER: string[] = [
  "automation",
  "ai",
  "communication",
  "data",
  "analytics",
  "security",
  "integration",
  "productivity",
  "devops",
  "sector",
];

async function apiGet(): Promise<{ plugins: Plugin[]; summary: Summary }> {
  const res = await fetch("/api/os/marketplace", { cache: "no-store" });
  const data = await res.json();
  if (!data.ok) throw new Error(data.error || "failed to load marketplace");
  return data;
}

async function apiAction(
  action: string,
  plugin_id: string,
  extra: Record<string, unknown> = {}
): Promise<any> {
  const res = await fetch("/api/os/marketplace", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, plugin_id, ...extra }),
  });
  const data = await res.json();
  if (!data.ok) throw new Error(data.error || `action '${action}' failed`);
  return data;
}

export default function MarketplacePage() {
  const [plugins, setPlugins] = useState<Plugin[]>([]);
  const [summary, setSummary] = useState<Summary>({
    plugins: 0,
    verified: 0,
    categories: [],
    version: 0,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [category, setCategory] = useState<string>("all");
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  // config modal
  const [configFor, setConfigFor] = useState<Plugin | null>(null);
  const [configValues, setConfigValues] = useState<Record<string, string>>({});

  // bulk uninstall confirmation
  const [confirmBulk, setConfirmBulk] = useState<{
    action: "install" | "uninstall";
    groupId: string;
    groupLabel: string;
    plugins: Plugin[];
  } | null>(null);
  const [detailFor, setDetailFor] = useState<Plugin | null>(null);

  // run panel
  const [runFor, setRunFor] = useState<Plugin | null>(null);
  const [runEntry, setRunEntry] = useState<string>("");
  const [runParams, setRunParams] = useState("");
  const [runResult, setRunResult] = useState<any>(null);
  const [runLoading, setRunLoading] = useState(false);

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 3200);
    return () => clearTimeout(t);
  }, [toast]);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiGet();
      setPlugins(data.plugins);
      setSummary(data.summary);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  const act = async (action: string, plugin: Plugin, extra: Record<string, unknown> = {}) => {
    setBusy(`${action}:${plugin.id}`);
    setToast(null);
    try {
      await apiAction(action, plugin.id, extra);
      setToast(`${action} ${plugin.name} — done`);
      const data = await apiGet();
      setPlugins(data.plugins);
    } catch (e) {
      setToast(String(e));
    } finally {
      setBusy(null);
    }
  };

  // Sequentially run a lifecycle action (install/uninstall) over a category's plugins.
  const bulkAction = async (
    action: "install" | "uninstall",
    groupId: string,
    pluginsToAct: Plugin[]
  ) => {
    if (busy) return;
    setBusy(`${action}-all:${groupId}`);
    setToast(null);
    let done = 0;
    const total = pluginsToAct.length;
    const gerund = action === "install" ? "Installing" : "Uninstalling";
    const past = action === "install" ? "Installed" : "Uninstalled";
    try {
      for (const plugin of pluginsToAct) {
        setBusy(`${action}:${plugin.id}`);
        try {
          await apiAction(action, plugin.id, {});
          done += 1;
          setToast(`${gerund} ${plugin.name} (${done}/${total})…`);
        } catch {
          setToast(`${past} failed for ${plugin.name} — skipping`);
        }
      }
      setToast(`${past} ${done}/${total} plugins in ${CATEGORY_LABELS[groupId] || groupId}`);
      const data = await apiGet();
      setPlugins(data.plugins);
    } finally {
      setBusy(null);
    }
  };

  const openConfig = (plugin: Plugin) => {
    const values: Record<string, string> = {};
    for (const [key, spec] of Object.entries(plugin.config_schema || {})) {
      values[key] = spec.default !== undefined ? String(spec.default) : "";
    }
    setConfigValues(values);
    setConfigFor(plugin);
  };

  const saveConfig = async () => {
    if (!configFor) return;
    const config: Record<string, unknown> = {};
    for (const [key, spec] of Object.entries(configFor.config_schema || {})) {
      const raw = configValues[key] ?? "";
      if (spec.type === "boolean") config[key] = raw === "true";
      else if (spec.type === "number") config[key] = raw === "" ? undefined : Number(raw);
      else config[key] = raw;
    }
    await act("config", configFor, { config });
    setConfigFor(null);
  };

  const openRun = (plugin: Plugin) => {
    setRunEntry(Object.keys(plugin.entry_points || {})[0] || "");
    setRunParams("");
    setRunResult(null);
    setRunFor(plugin);
  };

  const run = async () => {
    if (!runFor || !runEntry) return;
    setRunLoading(true);
    setRunResult(null);
    try {
      let params: Record<string, unknown> = {};
      try {
        params = runParams.trim() ? JSON.parse(runParams) : {};
      } catch {
        params = { text: runParams };
      }
      setRunResult(await apiAction("run", runFor.id, { entry: runEntry, params }));
    } catch (e) {
      setRunResult({ ok: false, error: String(e) });
    } finally {
      setRunLoading(false);
    }
  };

  const filtered = useMemo(() => {
    return plugins.filter((p) => {
      const matchCategory = category === "all" || p.category === category;
      const q = query.trim().toLowerCase();
      const matchQuery =
        !q ||
        p.name.toLowerCase().includes(q) ||
        p.description.toLowerCase().includes(q) ||
        p.tags.some((t) => t.toLowerCase().includes(q));
      return matchCategory && matchQuery;
    });
  }, [plugins, category, query]);

  // Filter-bar categories derived from the loaded catalog: guaranteed complete
  // even if the backend summary is empty, ordered by CATEGORY_ORDER, with counts.
  const filterCategories = useMemo(() => {
    const present = new Set(plugins.map((p) => p.category));
    const counts = new Map<string, number>();
    for (const p of plugins) counts.set(p.category, (counts.get(p.category) || 0) + 1);
    const ordered = CATEGORY_ORDER.filter((c) => present.has(c));
    const extra = Array.from(present)
      .filter((c) => !CATEGORY_ORDER.includes(c))
      .sort();
    return [...ordered, ...extra].map((c) => ({ id: c, count: counts.get(c) || 0 }));
  }, [plugins]);

  // Group the filtered plugins by category (CATEGORY_ORDER) for the "All" view.
  const grouped = useMemo(() => {
    if (category !== "all") return [];
    const groups = new Map<string, Plugin[]>();
    for (const p of filtered) {
      const list = groups.get(p.category) || [];
      list.push(p);
      groups.set(p.category, list);
    }
    const order = [
      ...CATEGORY_ORDER,
      ...Array.from(groups.keys())
        .filter((c) => !CATEGORY_ORDER.includes(c))
        .sort(),
    ];
    return order
      .filter((c) => groups.has(c))
      .map((c) => ({ id: c, label: CATEGORY_LABELS[c] || c, items: groups.get(c) || [] }));
  }, [filtered, category]);

  const renderCard = (plugin: Plugin) => (
    <div key={plugin.id} className="integration-marketplace-card">
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          gap: 8,
        }}
      >
        <div className="integration-marketplace-icon">{plugin.icon}</div>
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          {plugin.verified && (
            <span className="os-status-pill active" title="Verified by AEON Labs">
              ✓ Verified
            </span>
          )}
          {plugin.installed && (
            <span className="os-status-pill active">{plugin.enabled ? "Enabled" : "Disabled"}</span>
          )}
        </div>
      </div>

      <div className="integration-marketplace-info">
        <h4>
          {plugin.name}{" "}
          <span style={{ color: "var(--fg-mute)", fontWeight: 400, fontSize: "0.75rem" }}>
            v{plugin.version}
          </span>
        </h4>
        <p>{plugin.description}</p>

        <div className="integration-marketplace-meta" style={{ marginBottom: 10 }}>
          <span className="marketplace-type">
            {CATEGORY_LABELS[plugin.category] || plugin.category}
          </span>
          <span className="marketplace-type" style={{ opacity: 0.7 }}>
            by {plugin.author}
          </span>
          {plugin.tags.slice(0, 3).map((tag) => (
            <span key={tag} className="marketplace-secrets">
              #{tag}
            </span>
          ))}
        </div>

        <div
          style={{
            fontSize: "0.75rem",
            color: "var(--fg-mute)",
            marginBottom: 12,
            display: "flex",
            flexWrap: "wrap",
            gap: 6,
          }}
        >
          {Object.keys(plugin.entry_points || {}).map((entry) => (
            <code
              key={entry}
              style={{
                background: "var(--bg, #0f172a)",
                padding: "2px 6px",
                borderRadius: 4,
                border: "1px solid var(--border, #334155)",
              }}
            >
              {entry}
            </code>
          ))}
        </div>
      </div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: "auto" }}>
        <button
          className="btn btn-sm btn-ghost"
          disabled={busy !== null}
          onClick={() => setDetailFor(plugin)}
          title="View entry points, config schema, and permissions"
        >
          ℹ️ Details
        </button>
        {!plugin.installed ? (
          <button
            className="btn btn-primary btn-sm"
            disabled={busy === `install:${plugin.id}`}
            onClick={() => act("install", plugin)}
          >
            {busy === `install:${plugin.id}` ? "Installing…" : "+ Install"}
          </button>
        ) : (
          <>
            <button
              className="btn btn-sm"
              disabled={busy !== null}
              onClick={() => (plugin.enabled ? act("disable", plugin) : act("enable", plugin))}
            >
              {plugin.enabled ? "Disable" : "Enable"}
            </button>
            {Object.keys(plugin.config_schema || {}).length > 0 && (
              <button
                className="btn btn-sm"
                disabled={busy !== null}
                onClick={() => openConfig(plugin)}
              >
                ⚙ Configure
              </button>
            )}
            <button className="btn btn-sm" disabled={busy !== null} onClick={() => openRun(plugin)}>
              ▶ Run
            </button>
            <button
              className="btn btn-sm btn-ghost"
              disabled={busy !== null}
              onClick={() => act("uninstall", plugin)}
            >
              Uninstall
            </button>
          </>
        )}
      </div>
    </div>
  );

  return (
    <main style={{ padding: 28, maxWidth: 1200, margin: "0 auto" }}>
      {/* header */}
      <header style={{ marginBottom: 24 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ fontSize: "2rem" }}>🏪</span>
          <div>
            <h1 style={{ fontSize: "1.6rem", fontWeight: 700, margin: 0 }}>Plugin Marketplace</h1>
            <p style={{ margin: "4px 0 0", color: "var(--fg-soft)", fontSize: "0.9rem" }}>
              Extend AEON OS with connectors, analytics, sector tools, and automation capabilities.
            </p>
          </div>
        </div>

        <div style={{ display: "flex", gap: 12, marginTop: 16, flexWrap: "wrap" }}>
          <span className="os-status-pill active">{summary.plugins} plugins</span>
          <span className="os-status-pill active">{summary.verified} verified</span>
          {(summary.categories && summary.categories.length > 0
            ? summary.categories
            : filterCategories.map((fc) => fc.id)
          ).map((c) => (
            <span key={c} className="os-status-pill">
              {CATEGORY_LABELS[c] || c}
            </span>
          ))}
        </div>

        {error && (
          <div
            style={{
              marginTop: 16,
              padding: "12px 16px",
              borderRadius: 8,
              background: "rgba(239,68,68,0.12)",
              border: "1px solid rgba(239,68,68,0.4)",
              color: "#fca5a5",
            }}
          >
            {error}{" "}
            <button className="btn btn-sm btn-ghost" onClick={load}>
              Retry
            </button>
          </div>
        )}
        {toast && (
          <div
            style={{
              marginTop: 16,
              padding: "10px 16px",
              borderRadius: 8,
              background: "rgba(16,185,129,0.12)",
              border: "1px solid rgba(16,185,129,0.4)",
              color: "#6ee7b7",
              fontSize: "0.85rem",
            }}
          >
            {toast}
          </div>
        )}
      </header>

      {/* filters */}
      <div
        style={{
          display: "flex",
          gap: 12,
          marginBottom: 20,
          flexWrap: "wrap",
          alignItems: "center",
        }}
      >
        <input
          className="os-input"
          placeholder="Search plugins…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          style={{ maxWidth: 280 }}
        />
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          <button
            className="btn btn-sm"
            onClick={() => setCategory("all")}
            style={{
              background: category === "all" ? "var(--accent, #6366f1)" : "transparent",
              color: category === "all" ? "#fff" : "var(--fg-soft)",
              borderColor: category === "all" ? "var(--accent, #6366f1)" : "var(--border, #334155)",
            }}
          >
            All <span className="marketplace-filter-count">{plugins.length}</span>
          </button>
          {filterCategories.map(({ id: c, count }) => (
            <button
              key={c}
              className="btn btn-sm"
              onClick={() => setCategory(c)}
              style={{
                background: category === c ? "var(--accent, #6366f1)" : "transparent",
                color: category === c ? "#fff" : "var(--fg-soft)",
                borderColor: category === c ? "var(--accent, #6366f1)" : "var(--border, #334155)",
              }}
            >
              <span className="marketplace-filter-icon" aria-hidden="true">
                {CATEGORY_ICONS[c] || "📦"}
              </span>
              {CATEGORY_LABELS[c] || c}
              <span className="marketplace-filter-count">{count}</span>
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <p style={{ color: "var(--fg-soft)" }}>Loading marketplace…</p>
      ) : category === "all" && grouped.length > 0 ? (
        <div>
          {grouped.map((group) => {
            const uninstalled = group.items.filter((p) => !p.installed);
            const installed = group.items.filter((p) => p.installed);
            return (
              <section key={group.id} className="marketplace-section">
                <div className="marketplace-section-header">
                  <h2 className="marketplace-section-title">
                    <span className="marketplace-category-icon">
                      {CATEGORY_ICONS[group.id] || "📦"}
                    </span>
                    {group.label}
                  </h2>
                  <div className="marketplace-section-actions">
                    <span className="os-status-pill">
                      {group.items.length} plugin{group.items.length === 1 ? "" : "s"}
                    </span>
                    {uninstalled.length > 0 && (
                      <button
                        className="btn btn-sm marketplace-install-all"
                        disabled={busy !== null}
                        onClick={() =>
                          setConfirmBulk({
                            action: "install",
                            groupId: group.id,
                            groupLabel: group.label,
                            plugins: uninstalled,
                          })
                        }
                      >
                        {busy === `install-all:${group.id}`
                          ? `Installing ${uninstalled.length}…`
                          : `+ Install all (${uninstalled.length})`}
                      </button>
                    )}
                    {installed.length > 0 && (
                      <button
                        className="btn btn-sm btn-ghost marketplace-uninstall-all"
                        disabled={busy !== null}
                        onClick={() =>
                          setConfirmBulk({
                            action: "uninstall",
                            groupId: group.id,
                            groupLabel: group.label,
                            plugins: installed,
                          })
                        }
                      >
                        {busy === `uninstall-all:${group.id}`
                          ? `Uninstalling ${installed.length}…`
                          : `− Uninstall all (${installed.length})`}
                      </button>
                    )}
                  </div>
                </div>
                <div className="integration-marketplace">{group.items.map(renderCard)}</div>
              </section>
            );
          })}
        </div>
      ) : (
        <div className="integration-marketplace">
          {filtered.map(renderCard)}
          {filtered.length === 0 && (
            <p style={{ color: "var(--fg-soft)", gridColumn: "1 / -1" }}>
              No plugins match your filters.
            </p>
          )}
        </div>
      )}

      {/* config modal */}
      {configFor && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.6)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 100,
            padding: 16,
          }}
          onClick={() => setConfigFor(null)}
        >
          <div
            style={{
              background: "var(--bg-1, #1e293b)",
              border: "1px solid var(--border, #334155)",
              borderRadius: 12,
              padding: 24,
              maxWidth: 460,
              width: "100%",
              maxHeight: "80vh",
              overflowY: "auto",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ margin: "0 0 4px" }}>
              {configFor.icon} Configure {configFor.name}
            </h3>
            <p style={{ color: "var(--fg-soft)", fontSize: "0.85rem", margin: "0 0 16px" }}>
              v{configFor.version} · {CATEGORY_LABELS[configFor.category] || configFor.category}
            </p>
            {Object.entries(configFor.config_schema || {}).map(([key, spec]) => (
              <label key={key} style={{ display: "block", marginBottom: 12 }}>
                <div style={{ fontSize: "0.8rem", color: "var(--fg-soft)", marginBottom: 4 }}>
                  {key}
                  {spec.required ? " *" : ""}
                </div>
                {spec.type === "boolean" ? (
                  <select
                    className="os-input"
                    value={configValues[key] ?? "false"}
                    onChange={(e) =>
                      setConfigValues((prev) => ({ ...prev, [key]: e.target.value }))
                    }
                  >
                    <option value="true">true</option>
                    <option value="false">false</option>
                  </select>
                ) : (
                  <input
                    className="os-input"
                    value={configValues[key] ?? ""}
                    placeholder={spec.description || ""}
                    onChange={(e) =>
                      setConfigValues((prev) => ({ ...prev, [key]: e.target.value }))
                    }
                  />
                )}
              </label>
            ))}
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 16 }}>
              <button className="btn btn-sm btn-ghost" onClick={() => setConfigFor(null)}>
                Cancel
              </button>
              <button
                className="btn btn-primary btn-sm"
                disabled={busy !== null}
                onClick={saveConfig}
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}

      {/* run modal */}
      {runFor && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.6)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 100,
            padding: 16,
          }}
          onClick={() => setRunFor(null)}
        >
          <div
            style={{
              background: "var(--bg-1, #1e293b)",
              border: "1px solid var(--border, #334155)",
              borderRadius: 12,
              padding: 24,
              maxWidth: 520,
              width: "100%",
              maxHeight: "80vh",
              overflowY: "auto",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ margin: "0 0 4px" }}>
              {runFor.icon} Run {runFor.name}
            </h3>
            <p style={{ color: "var(--fg-soft)", fontSize: "0.85rem", margin: "0 0 16px" }}>
              Invoke an entry point. Built-in plugins execute deterministic handlers; third-party
              code runs only inside a sandbox.
            </p>
            <select
              className="os-input"
              value={runEntry}
              onChange={(e) => setRunEntry(e.target.value)}
              style={{ marginBottom: 8 }}
            >
              {Object.entries(runFor.entry_points || {}).map(([entry, desc]) => (
                <option key={entry} value={entry}>
                  {entry} — {desc}
                </option>
              ))}
            </select>
            <textarea
              className="os-input"
              rows={3}
              placeholder={'JSON params, e.g. {"text":"hello"} — or plain text'}
              value={runParams}
              onChange={(e) => setRunParams(e.target.value)}
              style={{ marginBottom: 12, width: "100%" }}
            />
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginBottom: 12 }}>
              <button className="btn btn-sm btn-ghost" onClick={() => setRunFor(null)}>
                Close
              </button>
              <button className="btn btn-primary btn-sm" disabled={runLoading} onClick={run}>
                {runLoading ? "Running…" : "Run"}
              </button>
            </div>
            {runResult && (
              <pre
                style={{
                  background: "var(--bg, #0f172a)",
                  border: "1px solid var(--border, #334155)",
                  borderRadius: 8,
                  padding: 12,
                  fontSize: "0.78rem",
                  overflowX: "auto",
                  color: runResult.ok ? "#a5b4fc" : "#fca5a5",
                  whiteSpace: "pre-wrap",
                }}
              >
                {JSON.stringify(runResult, null, 2)}
              </pre>
            )}
          </div>
        </div>
      )}

      {/* bulk uninstall confirmation modal */}
      {confirmBulk && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.6)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 110,
            padding: 16,
          }}
          onClick={() => setConfirmBulk(null)}
        >
          <div
            style={{
              background: "var(--bg-1, #1e293b)",
              border: "1px solid var(--border, #334155)",
              borderRadius: 12,
              padding: 24,
              maxWidth: 480,
              width: "100%",
              maxHeight: "80vh",
              display: "flex",
              flexDirection: "column",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ margin: "0 0 6px", fontSize: "1.05rem", color: "var(--fg, #f1f5f9)" }}>
              {confirmBulk.action === "install" ? "Install" : "Uninstall"}{" "}
              {confirmBulk.plugins.length} plugin
              {confirmBulk.plugins.length === 1 ? "" : "s"}?
            </h3>
            <p
              style={{ margin: "0 0 14px", fontSize: "0.85rem", color: "var(--fg-soft, #94a3b8)" }}
            >
              {confirmBulk.action === "install"
                ? `This will install every ${confirmBulk.groupLabel} plugin into this workspace and make them callable by agents, automations, and workflows.`
                : `This will remove every ${confirmBulk.groupLabel} plugin from this workspace. Agents, automations, and workflows will lose access to them immediately.`}
            </p>

            <div style={{ overflowY: "auto", flex: 1, marginBottom: 16 }}>
              {confirmBulk.plugins.map((plugin) => (
                <div
                  key={plugin.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    padding: "8px 10px",
                    borderRadius: 8,
                    background: "var(--bg, #0f172a)",
                    border: "1px solid var(--border, #334155)",
                    marginBottom: 6,
                  }}
                >
                  <span style={{ fontSize: "1rem" }}>{plugin.icon}</span>
                  <span
                    style={{ fontSize: "0.85rem", color: "var(--fg, #f1f5f9)", fontWeight: 500 }}
                  >
                    {plugin.name}
                  </span>
                  <span
                    style={{
                      marginLeft: "auto",
                      fontSize: "0.72rem",
                      color: "var(--fg-mute, #475569)",
                    }}
                  >
                    v{plugin.version}
                  </span>
                </div>
              ))}
            </div>

            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button
                className="btn btn-sm btn-ghost"
                onClick={() => setConfirmBulk(null)}
                disabled={busy !== null}
              >
                Cancel
              </button>
              <button
                className={
                  confirmBulk.action === "install"
                    ? "btn btn-sm marketplace-install-all"
                    : "btn btn-sm marketplace-uninstall-all"
                }
                disabled={busy !== null}
                onClick={() => {
                  const { action, groupId, plugins } = confirmBulk;
                  setConfirmBulk(null);
                  bulkAction(action, groupId, plugins);
                }}
              >
                {confirmBulk.action === "install" ? "Install" : "Uninstall"}{" "}
                {confirmBulk.plugins.length}
              </button>
            </div>
          </div>
        </div>
      )}

      {detailFor && (
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
          onClick={() => setDetailFor(null)}
        >
          <div
            style={{
              background: "var(--bg-1, #1e293b)",
              border: "1px solid var(--border, #334155)",
              borderRadius: 12,
              padding: 24,
              maxWidth: 560,
              width: "100%",
              maxHeight: "85vh",
              display: "flex",
              flexDirection: "column",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* header */}
            <div style={{ display: "flex", alignItems: "flex-start", gap: 12, marginBottom: 10 }}>
              <div
                style={{
                  fontSize: "1.6rem",
                  width: 48,
                  height: 48,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  borderRadius: 10,
                  background: "var(--bg, #0f172a)",
                  border: "1px solid var(--border, #334155)",
                  flexShrink: 0,
                }}
              >
                {detailFor.icon}
              </div>
              <div style={{ minWidth: 0, flex: 1 }}>
                <h3
                  style={{
                    margin: 0,
                    fontSize: "1.1rem",
                    color: "var(--fg, #f1f5f9)",
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                  }}
                >
                  {detailFor.name}
                  <span style={{ color: "var(--fg-mute)", fontWeight: 400, fontSize: "0.78rem" }}>
                    v{detailFor.version}
                  </span>
                  {detailFor.verified && (
                    <span className="os-status-pill active" style={{ fontSize: "0.7rem" }}>
                      ✓ Verified
                    </span>
                  )}
                </h3>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 6 }}>
                  <span className="marketplace-type">
                    {CATEGORY_LABELS[detailFor.category] || detailFor.category}
                  </span>
                  <span className="marketplace-type" style={{ opacity: 0.7 }}>
                    by {detailFor.author}
                  </span>
                  {detailFor.source && (
                    <span className="marketplace-type" style={{ opacity: 0.7 }}>
                      src: {detailFor.source}
                    </span>
                  )}
                  {detailFor.installed && (
                    <span className={`os-status-pill ${detailFor.enabled ? "active" : ""}`}>
                      {detailFor.enabled ? "Enabled" : "Disabled"}
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* body */}
            <div style={{ overflowY: "auto", flex: 1, paddingRight: 4 }}>
              <p
                style={{
                  margin: "0 0 14px",
                  fontSize: "0.88rem",
                  color: "var(--fg-soft, #94a3b8)",
                  lineHeight: 1.5,
                }}
              >
                {detailFor.description}
              </p>

              {detailFor.tags.length > 0 && (
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 14 }}>
                  {detailFor.tags.map((tag) => (
                    <span key={tag} className="marketplace-secrets">
                      #{tag}
                    </span>
                  ))}
                </div>
              )}

              {/* entry points */}
              <div style={{ marginBottom: 14 }}>
                <div
                  style={{
                    fontSize: "0.72rem",
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                    color: "var(--fg-mute, #475569)",
                    marginBottom: 6,
                  }}
                >
                  Entry points
                </div>
                {Object.entries(detailFor.entry_points || {}).length === 0 ? (
                  <div style={{ fontSize: "0.82rem", color: "var(--fg-mute, #475569)" }}>
                    No entry points exposed.
                  </div>
                ) : (
                  Object.entries(detailFor.entry_points || {}).map(([entry, desc]) => (
                    <div
                      key={entry}
                      style={{
                        display: "flex",
                        alignItems: "baseline",
                        gap: 10,
                        padding: "7px 10px",
                        borderRadius: 8,
                        background: "var(--bg, #0f172a)",
                        border: "1px solid var(--border, #334155)",
                        marginBottom: 6,
                      }}
                    >
                      <code
                        style={{
                          fontSize: "0.8rem",
                          color: "var(--accent, #38bdf8)",
                          flexShrink: 0,
                        }}
                      >
                        {entry}
                      </code>
                      <span style={{ fontSize: "0.8rem", color: "var(--fg-soft, #94a3b8)" }}>
                        {desc}
                      </span>
                    </div>
                  ))
                )}
              </div>

              {/* config schema */}
              <div style={{ marginBottom: 14 }}>
                <div
                  style={{
                    fontSize: "0.72rem",
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                    color: "var(--fg-mute, #475569)",
                    marginBottom: 6,
                  }}
                >
                  Configuration
                </div>
                {Object.entries(detailFor.config_schema || {}).length === 0 ? (
                  <div style={{ fontSize: "0.82rem", color: "var(--fg-mute, #475569)" }}>
                    No configuration required.
                  </div>
                ) : (
                  Object.entries(detailFor.config_schema || {}).map(([key, spec]) => (
                    <div
                      key={key}
                      style={{
                        padding: "7px 10px",
                        borderRadius: 8,
                        background: "var(--bg, #0f172a)",
                        border: "1px solid var(--border, #334155)",
                        marginBottom: 6,
                      }}
                    >
                      <div
                        style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 2 }}
                      >
                        <code style={{ fontSize: "0.8rem", color: "var(--fg, #f1f5f9)" }}>
                          {key}
                        </code>
                        {spec.required && (
                          <span style={{ fontSize: "0.68rem", color: "var(--danger, #f87171)" }}>
                            required
                          </span>
                        )}
                        {spec.type && (
                          <span
                            style={{
                              fontSize: "0.68rem",
                              color: "var(--fg-mute, #475569)",
                              marginLeft: "auto",
                            }}
                          >
                            {spec.type}
                          </span>
                        )}
                      </div>
                      {spec.description && (
                        <div style={{ fontSize: "0.78rem", color: "var(--fg-soft, #94a3b8)" }}>
                          {spec.description}
                        </div>
                      )}
                      {spec.default !== undefined && (
                        <div
                          style={{
                            fontSize: "0.74rem",
                            color: "var(--fg-mute, #475569)",
                            marginTop: 2,
                          }}
                        >
                          default:{" "}
                          <code style={{ fontSize: "0.72rem" }}>{String(spec.default)}</code>
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>

              {/* permissions */}
              <div>
                <div
                  style={{
                    fontSize: "0.72rem",
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                    color: "var(--fg-mute, #475569)",
                    marginBottom: 6,
                  }}
                >
                  Permissions
                </div>
                {detailFor.permissions.length === 0 ? (
                  <div style={{ fontSize: "0.82rem", color: "var(--fg-mute, #475569)" }}>
                    No special permissions.
                  </div>
                ) : (
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                    {detailFor.permissions.map((perm) => (
                      <code
                        key={perm}
                        style={{
                          fontSize: "0.72rem",
                          padding: "3px 8px",
                          borderRadius: 999,
                          background: "rgba(56, 189, 248, 0.08)",
                          border: "1px solid rgba(56, 189, 248, 0.25)",
                          color: "var(--accent, #38bdf8)",
                        }}
                      >
                        {perm}
                      </code>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* footer */}
            <div
              style={{
                display: "flex",
                gap: 8,
                justifyContent: "flex-end",
                marginTop: 16,
                flexWrap: "wrap",
              }}
            >
              <button className="btn btn-sm btn-ghost" onClick={() => setDetailFor(null)}>
                Close
              </button>
              {!detailFor.installed ? (
                <button
                  className="btn btn-primary btn-sm"
                  disabled={busy === `install:${detailFor.id}`}
                  onClick={() => {
                    const plugin = detailFor;
                    setDetailFor(null);
                    act("install", plugin);
                  }}
                >
                  {busy === `install:${detailFor.id}` ? "Installing…" : "+ Install"}
                </button>
              ) : (
                <>
                  {Object.keys(detailFor.config_schema || {}).length > 0 && (
                    <button
                      className="btn btn-sm"
                      disabled={busy !== null}
                      onClick={() => {
                        openConfig(detailFor);
                        setDetailFor(null);
                      }}
                    >
                      ⚙ Configure
                    </button>
                  )}
                  <button
                    className="btn btn-sm"
                    disabled={busy !== null}
                    onClick={() => {
                      openRun(detailFor);
                      setDetailFor(null);
                    }}
                  >
                    ▶ Run
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
