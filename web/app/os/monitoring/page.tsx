"use client";

import { useEffect, useState, useMemo, useCallback } from "react";
import { useSession } from "next-auth/react";
import Link from "next/link";
import { getAuthHeaders } from "@/lib/flask-auth";
import ErrorState from "@/components/ui/ErrorState";

type MetricPoint = { label: string; value: number; color?: string };

type HealthSnapshot = {
  ok: boolean;
  timestamp: number;
  kernel: { status: string; backend: string };
  agents: { app_id: string; ticks: number; vitals: Record<string, any> }[];
  queue: { size: number; status: string };
  integrations: { id: string; name: string; type: string; enabled: boolean }[];
  storage: { usage_events_bytes?: number; usage_events_mb?: number; error?: string };
};

type MetricsSummary = {
  ok: boolean;
  metrics: {
    total_events: number;
    total_quantity: number;
    total_cost: number;
    by_action: Record<string, { count: number; cost: number }>;
    by_day: Record<string, { count: number }>;
  };
};

type AlertRule = {
  name: string;
  description: string;
  severity: string;
  expr: string;
  for: string;
  service: string;
  runbook?: string;
};

type Incident = {
  id: string;
  title: string;
  severity: "critical" | "warning" | "info";
  status: "open" | "acknowledged" | "resolved" | "closed";
  created_at: string | null;
  updated_at: string | null;
  resolved_at: string | null;
  metadata?: Record<string, unknown>;
};

const ALERT_RULES: AlertRule[] = [
  {
    name: "AeonHighErrorRate",
    description: "HTTP 5xx rate above 5% for 2 minutes",
    severity: "critical",
    expr: "error_ratio_5m > 0.05",
    for: "2m",
    service: "aeon-kernel",
    runbook: "AeonHighErrorRate",
  },
  {
    name: "AeonHighLatency",
    description: "P99 latency above 1 second for 3 minutes",
    severity: "warning",
    expr: "http_request_latency_p99_5m > 1.0",
    for: "3m",
    service: "aeon-kernel",
    runbook: "AeonHighLatency",
  },
  {
    name: "AeonJobQueueDeep",
    description: "Job queue depth above 50 for 5 minutes",
    severity: "warning",
    expr: "job_queue_size > 50",
    for: "5m",
    service: "aeon-kernel",
    runbook: "AeonJobQueueDeep",
  },
  {
    name: "AeonAgentTickErrors",
    description: "Agent tick errors above 0.1/s for 2 minutes",
    severity: "critical",
    expr: "agent_tick_error_rate > 0.1",
    for: "2m",
    service: "aeon-kernel",
    runbook: "AeonAgentTickErrors",
  },
  {
    name: "AeonKernelDown",
    description: "Kernel is unreachable by Prometheus",
    severity: "critical",
    expr: "up == 0",
    for: "1m",
    service: "aeon-kernel",
  },
  {
    name: "AeonWorkflowFailures",
    description: "Workflow failure rate elevated over 10 minutes",
    severity: "warning",
    expr: "workflow_failure_rate > 0.5",
    for: "3m",
    service: "aeon-kernel",
  },
  {
    name: "AeonWebhookFailures",
    description: "Webhook delivery failures elevated",
    severity: "warning",
    expr: "webhook_failure_rate > 1",
    for: "5m",
    service: "aeon-kernel",
  },
];

function useFetch<T>(url: string) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    fetch(url, { cache: "no-store" })
      .then((r) => r.json())
      .then((d) => {
        if (!mounted) return;
        setData(d);
        setLoading(false);
      })
      .catch((e) => {
        if (!mounted) return;
        setError(String(e));
        setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [url]);

  return { data, loading, error };
}

function MetricCard({
  title,
  value,
  subtitle,
  color,
}: {
  title: string;
  value: string | number;
  subtitle?: string;
  color?: string;
}) {
  return (
    <div className="mon-card">
      <div className="mon-card-label">{title}</div>
      <div className="mon-card-value" style={{ color: color || "var(--fg)" }}>
        {value}
      </div>
      {subtitle && <div className="mon-card-subtitle">{subtitle}</div>}
    </div>
  );
}

function MiniBar({ data }: { data: MetricPoint[] }) {
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <div className="mon-bar-chart">
      {data.map((d, i) => (
        <div key={i} className="mon-bar-group">
          <div
            className="mon-bar-fill"
            style={{
              height: `${(d.value / max) * 100}%`,
              background: d.color || "var(--accent)",
            }}
          />
          <span className="mon-bar-label">{d.label}</span>
        </div>
      ))}
    </div>
  );
}

function StatusDot({ status }: { status: string }) {
  const colors: Record<string, string> = {
    ok: "#22c55e",
    healthy: "#22c55e",
    active: "#22c55e",
    warning: "#f59e0b",
    congested: "#f59e0b",
    past_due: "#f59e0b",
    error: "#ef4444",
    critical: "#ef4444",
    down: "#ef4444",
    firing: "#ef4444",
    unknown: "#94a3b8",
  };
  return (
    <span className="mon-status-dot" style={{ background: colors[status] || colors.unknown }} />
  );
}

export default function MonitoringPage() {
  const { data: session } = useSession();
  const workspaceId = ((session?.user as any)?.workspaceId as string) || "default";

  const [activeTab, setActiveTab] = useState<"overview" | "alerts" | "incidents">("overview");
  const [metrics, setMetrics] = useState<MetricsSummary | null>(null);
  const [health, setHealth] = useState<HealthSnapshot | null>(null);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [incidentError, setIncidentError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [healthRes, metricsRes, incidentsRes] = await Promise.all([
        fetch("/api/os/observability/health", { cache: "no-store" }),
        fetch("/api/os/observability/metrics", { cache: "no-store" }),
        fetch("/api/os/observability/incidents", {
          cache: "no-store",
          headers: getAuthHeaders(),
        }),
      ]);
      const h = await healthRes.json();
      const m = await metricsRes.json();
      const i = await incidentsRes.json();
      if (h.ok) setHealth(h);
      if (m.ok) setMetrics(m);
      if (i.ok) {
        setIncidents(Array.isArray(i.incidents) ? i.incidents : []);
        setIncidentError(null);
      } else {
        setIncidentError(i.error || `Incident request failed (${incidentsRes.status})`);
      }
    } catch (error) {
      setIncidentError(error instanceof Error ? error.message : "Monitoring request failed");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const actionData = useMemo(() => {
    const byAction = metrics?.metrics?.by_action || {};
    return Object.entries(byAction)
      .sort((a, b) => (b[1]?.count || 0) - (a[1]?.count || 0))
      .slice(0, 8)
      .map(([k, v]) => ({ label: k, value: v.count }));
  }, [metrics]);

  const dailyData = useMemo(() => {
    const byDay = metrics?.metrics?.by_day || {};
    return Object.entries(byDay)
      .slice(-14)
      .map(([k, v]) => ({ label: k.slice(5), value: v.count }));
  }, [metrics]);

  const kernelStatus = health?.kernel?.status || "unknown";
  const queueSize = health?.queue?.size ?? 0;
  const queueStatus = health?.queue?.status || "unknown";
  const agentCount = health?.agents?.length ?? 0;
  const integrationCount = health?.integrations?.length ?? 0;
  const storageMb = health?.storage?.usage_events_mb ?? 0;
  const totalEvents = metrics?.metrics?.total_events ?? 0;
  const totalCost = metrics?.metrics?.total_cost ?? 0;

  return (
    <div className="os-page">
      <header className="os-header">
        <div>
          <h1>📈 Monitoring & Alerting</h1>
          <p className="dashboard-subtitle">
            Live system health, Prometheus alert rules, and incident timeline
          </p>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <Link href="/os/observability" className="btn btn-sm">
            Observability
          </Link>
          <Link href="/os" className="btn btn-sm">
            ← OS Launcher
          </Link>
        </div>
      </header>

      {/* ── Tab Navigation ── */}
      <div className="mon-tabs">
        {(["overview", "alerts", "incidents"] as const).map((tab) => (
          <button
            key={tab}
            className={`mon-tab ${activeTab === tab ? "active" : ""}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab === "overview" && "📊 "}
            {tab === "alerts" && "🔔 "}
            {tab === "incidents" && "🚨 "}
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>

      {incidentError && (
        <div className="mb-4">
          <ErrorState
            error={incidentError}
            onRetry={loadData}
            title="Could not load monitoring data"
          />
        </div>
      )}

      {loading && (
        <div style={{ color: "var(--fg-mute)", padding: 40, textAlign: "center" }}>
          Loading monitoring data…
        </div>
      )}

      {/* ════════════════════════════════════════════════
          OVERVIEW TAB
          ════════════════════════════════════════════════ */}
      {activeTab === "overview" && (
        <>
          {/* KPI Row */}
          <section className="mon-grid-5">
            <MetricCard
              title="Kernel"
              value={kernelStatus === "ok" ? "Healthy" : kernelStatus}
              color={kernelStatus === "ok" ? "#22c55e" : "#ef4444"}
              subtitle={health?.kernel?.backend || ""}
            />
            <MetricCard
              title="Active Agents"
              value={agentCount}
              subtitle={`${agentCount} context(s) loaded`}
              color="#6366f1"
            />
            <MetricCard
              title="Job Queue"
              value={queueSize}
              subtitle={`Status: ${queueStatus}`}
              color={queueSize > 50 ? "#ef4444" : queueSize > 20 ? "#f59e0b" : "#22c55e"}
            />
            <MetricCard
              title="Integrations"
              value={integrationCount}
              subtitle="Connected connectors"
              color="#6366f1"
            />
            <MetricCard
              title="Storage"
              value={`${storageMb.toFixed(2)} MB`}
              subtitle="Usage events"
              color="#94a3b8"
            />
          </section>

          {/* Stats Row */}
          <section className="mon-grid-2col">
            {/* Left: System Health */}
            <div className="mon-card-panel">
              <h3 className="mon-panel-title">System Health</h3>
              <div className="mon-health-list">
                <div className="mon-health-row">
                  <span className="mon-health-key">
                    <StatusDot status={kernelStatus} /> Kernel
                  </span>
                  <span className="mon-health-value">{health?.kernel?.status || "unknown"}</span>
                </div>
                <div className="mon-health-row">
                  <span className="mon-health-key">
                    <StatusDot status={queueStatus} /> Queue
                  </span>
                  <span className="mon-health-value">
                    {queueSize} items ({queueStatus})
                  </span>
                </div>
                <div className="mon-health-row">
                  <span className="mon-health-key">
                    <StatusDot status={kernelStatus === "ok" ? "ok" : "error"} /> Backend
                  </span>
                  <span
                    className="mon-health-value"
                    style={{ fontFamily: "monospace", fontSize: "0.8rem" }}
                  >
                    {health?.kernel?.backend || "unknown"}
                  </span>
                </div>
                <div className="mon-health-row">
                  <span className="mon-health-key">ℹ️ Total Events</span>
                  <span className="mon-health-value">{totalEvents.toLocaleString()}</span>
                </div>
                <div className="mon-health-row">
                  <span className="mon-health-key">💰 Estimated Cost</span>
                  <span className="mon-health-value" style={{ color: "#f59e0b" }}>
                    ${totalCost.toFixed(4)}
                  </span>
                </div>
              </div>
              <div className="mon-panel-footer">
                <Link href="/api/stripe/config" className="mon-link">
                  Prometheus /metrics →
                </Link>
                <span className="mon-timestamp">Updated {new Date().toLocaleTimeString()}</span>
              </div>
            </div>

            {/* Right: Agent Activity / Active Agents */}
            <div className="mon-card-panel">
              <h3 className="mon-panel-title">Active Agent Contexts</h3>
              {health?.agents?.length ? (
                <div className="mon-agent-list">
                  {health.agents.map((agent) => (
                    <div key={agent.app_id} className="mon-agent-row">
                      <div className="mon-agent-info">
                        <span className="mon-agent-id">{agent.app_id}</span>
                        <span className="mon-agent-ticks">{agent.ticks} ticks</span>
                      </div>
                      <div className="mon-agent-vitals">
                        {agent.vitals?.energy != null && (
                          <span
                            className="mon-agent-vital"
                            style={{
                              color:
                                agent.vitals.energy > 0.5
                                  ? "#22c55e"
                                  : agent.vitals.energy > 0.2
                                    ? "#f59e0b"
                                    : "#ef4444",
                            }}
                          >
                            {Math.round(agent.vitals.energy * 100)}%
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="mon-empty">No active agent contexts</div>
              )}
            </div>
          </section>

          {/* Charts Row */}
          <section className="mon-grid-2col">
            <div className="mon-card-panel">
              <h3 className="mon-panel-title">Usage by Action (Last 30d)</h3>
              {actionData.length > 0 ? (
                <MiniBar data={actionData} />
              ) : (
                <div className="mon-empty">No usage data yet</div>
              )}
            </div>
            <div className="mon-card-panel">
              <h3 className="mon-panel-title">Daily Activity (Last 14 days)</h3>
              {dailyData.length > 0 ? (
                <MiniBar data={dailyData} />
              ) : (
                <div className="mon-empty">No daily data yet</div>
              )}
            </div>
          </section>

          {/* Prometheus / Grafana Links */}
          <section className="mon-card-panel">
            <h3 className="mon-panel-title">External Tools</h3>
            <p style={{ color: "var(--fg-soft)", fontSize: "0.85rem", marginBottom: 16 }}>
              The AEON kernel exposes the /metrics endpoint in Prometheus text format. Start the
              monitoring stack for full observability:
            </p>
            <div className="mon-tool-links">
              <code className="mon-code-block">cd monitoring && docker compose up --build</code>
              <div className="mon-external-links">
                <a
                  href="http://localhost:9090"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mon-external-link"
                >
                  Prometheus →
                </a>
                <a
                  href="http://localhost:3000"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mon-external-link"
                >
                  Grafana →
                </a>
                <a
                  href="http://localhost:9093"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mon-external-link"
                >
                  Alertmanager →
                </a>
              </div>
            </div>
          </section>
        </>
      )}

      {/* ════════════════════════════════════════════════
          ALERTS TAB
          ════════════════════════════════════════════════ */}
      {activeTab === "alerts" && (
        <section className="mon-card-panel">
          <h3 className="mon-panel-title">Prometheus Alert Rules (7 rules)</h3>
          <p style={{ color: "var(--fg-soft)", fontSize: "0.85rem", marginBottom: 16 }}>
            Configured in <code>monitoring/prometheus/rules/alert-rules.yml</code>. Auto-loaded by
            Prometheus on startup.
          </p>
          <div className="mon-alert-rules">
            {ALERT_RULES.map((rule) => (
              <div key={rule.name} className="mon-alert-rule">
                <div className="mon-alert-rule-header">
                  <span className={`mon-alert-severity ${rule.severity}`}>{rule.severity}</span>
                  <strong className="mon-alert-rule-name">{rule.name}</strong>
                  <span className="mon-alert-rule-for">{rule.for}</span>
                </div>
                <div className="mon-alert-rule-desc">{rule.description}</div>
                <div className="mon-alert-rule-meta">
                  <code className="mon-alert-rule-expr">{rule.expr}</code>
                  <span className="mon-alert-rule-service">Service: {rule.service}</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ════════════════════════════════════════════════
          INCIDENTS TAB
          ════════════════════════════════════════════════ */}
      {activeTab === "incidents" && (
        <section className="mon-card-panel">
          <h3 className="mon-panel-title">Incident Timeline</h3>
          <p style={{ color: "var(--fg-soft)", fontSize: "0.85rem", marginBottom: 16 }}>
            Recent incidents detected by the monitoring stack. Firing incidents require attention.
          </p>
          {incidentError && (
            <div style={{ color: "var(--fg-mute)", padding: "10px 0 16px" }} role="status">
              Live incidents are unavailable. Check the backend connection and try again.
            </div>
          )}
          <div className="mon-incident-list">
            {incidents.length === 0 && !incidentError ? (
              <div className="mon-empty">No incidents recorded for this workspace</div>
            ) : (
              incidents.map((inc) => (
                <div key={inc.id} className="mon-incident-item">
                  <div className="mon-incident-left">
                    <StatusDot
                      status={
                        inc.status === "resolved" || inc.status === "closed" ? "ok" : "warning"
                      }
                    />
                    <div className="mon-incident-info">
                      <div className="mon-incident-header">
                        <strong className="mon-incident-title">{inc.title}</strong>
                        <span className={`mon-incident-severity ${inc.severity}`}>
                          {inc.severity}
                        </span>
                      </div>
                      <div className="mon-incident-meta">
                        <span>{inc.id}</span>
                        <span className="mon-incident-dot">·</span>
                        <span>
                          {inc.created_at
                            ? new Date(inc.created_at).toLocaleString()
                            : "Unknown time"}
                        </span>
                        <span className="mon-incident-dot">·</span>
                        <span>{inc.resolved_at ? "Resolved" : "Ongoing"}</span>
                        <span className="mon-incident-dot">·</span>
                        <span>
                          Source:{" "}
                          {typeof inc.metadata?.source === "string" ? inc.metadata.source : "AEON"}
                        </span>
                      </div>
                    </div>
                  </div>
                  <div className={`mon-incident-status ${inc.status}`}>{inc.status}</div>
                </div>
              ))
            )}
          </div>
        </section>
      )}
    </div>
  );
}
