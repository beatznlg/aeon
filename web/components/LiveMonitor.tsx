"use client";

import { useEffect, useState, useCallback } from "react";

// ── Types ────────────────────────────────────────────────────────────

export type LiveData = {
  ok: boolean;
  ts: number;
  app_id: string;
  system: {
    uptime_s: number;
    requests_per_min: number;
    avg_response_ms: number;
    memory_mb: number;
    cpu_pct: number;
    active_goals: number;
    tool_success_rate: number;
    status: string;
  };
  metrics: Array<{
    label: string;
    value: number;
    prev: number;
    unit: string;
    status: string;
  }>;
};

// ── Hook ─────────────────────────────────────────────────────────────

export function useLiveMonitor(appId: string | null, intervalMs = 5000) {
  const [data, setData] = useState<LiveData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const refetch = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    if (!appId) return;
    let cancelled = false;

    const load = async () => {
      try {
        const res = await fetch(`/api/os/apps/${appId}/live`, {
          cache: "no-store",
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const d: LiveData = await res.json();
        if (!cancelled) {
          setData(d);
          setError(null);
        }
      } catch (e: any) {
        if (!cancelled) setError(e.message ?? "poll failed");
      }
    };

    load();
    const timer = setInterval(load, intervalMs);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [appId, intervalMs, tick]);

  return { data, error, refetch };
}

// ── Helpers ──────────────────────────────────────────────────────────

function formatUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m ${Math.floor(seconds % 60)}s`;
}

function fmt(v: number): string {
  if (v >= 1000000) return (v / 1000000).toFixed(1) + "M";
  if (v >= 1000) return (v / 1000).toFixed(1) + "K";
  return v.toFixed(v % 1 === 0 ? 0 : 1);
}

// ── Components ───────────────────────────────────────────────────────

/** Full-width live monitor strip — shows system vitals with animated pulse */
export function LiveMonitorBar({ appId }: { appId: string }) {
  const { data, error } = useLiveMonitor(appId);
  const sys = data?.system;
  const isHealthy = sys?.status === "healthy";

  return (
    <div className="live-bar">
      {/* Live indicator */}
      <div
        className="live-bar-indicator"
        title={error ? "Error" : data ? "Streaming live" : "Connecting..."}
      >
        <span className={`live-dot ${error ? "danger" : data ? "ok" : "pending"}`} />
        <span className="live-label">{error ? "OFFLINE" : data ? "LIVE" : "CONNECTING"}</span>
      </div>

      {sys && (
        <>
          <div className="live-metric">
            <span className="live-metric-label">Uptime</span>
            <span className="live-metric-value">{formatUptime(sys.uptime_s)}</span>
          </div>
          <div className="live-metric">
            <span className="live-metric-label">Requests</span>
            <span className="live-metric-value">{fmt(sys.requests_per_min)}/min</span>
          </div>
          <div className="live-metric">
            <span className="live-metric-label">Avg Response</span>
            <span className="live-metric-value">{Math.round(sys.avg_response_ms)}ms</span>
          </div>
          <div className="live-metric">
            <span
              className="live-metric-label"
              style={{ color: sys.memory_mb > 600 ? "var(--danger)" : undefined }}
            >
              Memory
            </span>
            <span
              className="live-metric-value"
              style={{ color: sys.memory_mb > 600 ? "var(--danger)" : undefined }}
            >
              {fmt(sys.memory_mb)} MB
            </span>
          </div>
          <div className="live-metric">
            <span
              className="live-metric-label"
              style={{ color: sys.cpu_pct > 80 ? "var(--danger)" : undefined }}
            >
              CPU
            </span>
            <span
              className="live-metric-value"
              style={{ color: sys.cpu_pct > 80 ? "var(--danger)" : undefined }}
            >
              {Math.round(sys.cpu_pct)}%
            </span>
          </div>
          <div className="live-metric">
            <span className="live-metric-label">Success Rate</span>
            <span
              className="live-metric-value"
              style={{ color: sys.tool_success_rate < 0.85 ? "var(--warning)" : "var(--success)" }}
            >
              {(sys.tool_success_rate * 100).toFixed(0)}%
            </span>
          </div>
          <div className="live-metric">
            <span className="live-metric-label">Goals Active</span>
            <span className="live-metric-value">{sys.active_goals}</span>
          </div>
          <div className="live-metric">
            <span className="live-metric-label">Status</span>
            <span className={`live-status-badge ${isHealthy ? "ok" : "warn"}`}>{sys.status}</span>
          </div>
        </>
      )}

      <div className="live-bar-timer">{new Date(data?.ts ?? Date.now()).toLocaleTimeString()}</div>
    </div>
  );
}

/** Standalone widget with auto-refresh live data table */
export function LiveMonitorWidget({
  appId,
  title = "Live Metrics",
}: {
  appId: string;
  title?: string;
}) {
  const { data, error } = useLiveMonitor(appId);
  const metrics = data?.metrics ?? [];

  return (
    <div className="live-widget">
      <div className="live-widget-header">
        <div className="live-widget-title-row">
          <span className={`live-dot ${data ? "ok" : error ? "danger" : "pending"}`} />
          <h3>{title}</h3>
        </div>
        <div className="live-widget-meta">
          {data ? (
            <span title={new Date(data.ts).toISOString()}>
              Updated {new Date(data.ts).toLocaleTimeString()}
            </span>
          ) : error ? (
            <span style={{ color: "var(--danger)" }}>{error}</span>
          ) : (
            <span>Connecting…</span>
          )}
        </div>
      </div>

      {metrics.length > 0 ? (
        <div className="live-metrics-grid">
          {metrics.map((m, i) => {
            const diff = m.value - m.prev;
            const isUp = diff > 0;
            const isDown = diff < 0;
            return (
              <div key={i} className="live-metric-card">
                <div className="live-metric-card-label">{m.label}</div>
                <div className="live-metric-card-value">
                  {m.unit === "%" ? `${Math.round(m.value)}%` : fmt(m.value)}
                </div>
                <div className="live-metric-card-diff">
                  <span className={`live-diff ${isUp ? "up" : isDown ? "down" : ""}`}>
                    {isUp ? "↑" : isDown ? "↓" : "—"} {Math.abs(Math.round(diff))}
                  </span>
                  <span className={`live-status-indicator ${m.status}`} title={m.status} />
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="module-empty" style={{ padding: 20 }}>
          {error ? "Connection error" : "Waiting for data..."}
        </div>
      )}
    </div>
  );
}

// ── Alert Types ──────────────────────────────────────────────────────

export interface Alert {
  id: string;
  module_id: string;
  module_name: string;
  severity: "critical" | "warning" | "info";
  title: string;
  message: string;
  metric: string;
  value: number;
  threshold: number;
  detected_at: number;
}

export interface AlertsResponse {
  ok: boolean;
  ts: number;
  total: number;
  critical_count: number;
  warning_count: number;
  alerts: Alert[];
  summary: {
    has_critical: boolean;
    has_warning: boolean;
    highest_severity: string;
  };
}

// ── Alert Hook ────────────────────────────────────────────────────────

export function useAlerts(intervalMs = 8000) {
  const [data, setData] = useState<AlertsResponse | null>(null);
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const res = await fetch("/api/os/apps/alerts", { cache: "no-store" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const d: AlertsResponse = await res.json();
        if (!cancelled) {
          setData(d);
          setError(null);
        }
      } catch (e: any) {
        if (!cancelled) setError(e.message ?? "poll failed");
      }
    };
    load();
    const timer = setInterval(load, intervalMs);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [intervalMs]);

  const dismissAlert = useCallback((id: string) => {
    setDismissed((prev) => new Set(prev).add(id));
  }, []);

  const dismissAll = useCallback(() => {
    if (!data) return;
    setDismissed(new Set(data.alerts.map((a) => a.id)));
  }, [data]);

  const activeAlerts = (data?.alerts ?? []).filter((a) => !dismissed.has(a.id));
  const activeCritical = activeAlerts.filter((a) => a.severity === "critical");
  const activeWarning = activeAlerts.filter((a) => a.severity === "warning");
  const activeInfo = activeAlerts.filter((a) => a.severity === "info");

  return {
    data,
    error,
    activeAlerts,
    activeCritical,
    activeWarning,
    activeInfo,
    dismissAlert,
    dismissAll,
    hasCritical: activeCritical.length > 0,
    totalActive: activeAlerts.length,
  };
}

// ── Alert Components ──────────────────────────────────────────────────

/** Banner shown at the top of the page for critical alerts */
export function AlertBanner() {
  const { activeCritical, activeWarning, dismissAlert, hasCritical } = useAlerts(10000);

  if (activeCritical.length === 0 && activeWarning.length === 0) return null;

  const topAlert = activeCritical.length > 0 ? activeCritical[0] : activeWarning[0];

  return (
    <div className={`alert-banner ${hasCritical ? "critical" : "warning"}`}>
      <span className="alert-banner-icon">{hasCritical ? "🚨" : "⚠️"}</span>
      <div className="alert-banner-content">
        <strong>{topAlert.title}</strong>
        <span>{topAlert.message}</span>
        {activeCritical.length > 1 && (
          <span className="alert-banner-count">
            +{activeCritical.length + activeWarning.length - 1} more
          </span>
        )}
      </div>
      <button className="btn btn-sm" onClick={() => dismissAlert(topAlert.id)}>
        Dismiss
      </button>
    </div>
  );
}

/** Full alert center panel */
export function AlertPanel() {
  const {
    activeAlerts,
    activeCritical,
    activeWarning,
    activeInfo,
    dismissAlert,
    dismissAll,
    totalActive,
    error,
  } = useAlerts(8000);

  return (
    <div className="alert-panel">
      <div className="alert-panel-header">
        <div className="alert-panel-title-row">
          <h3>{totalActive > 0 ? "🔔 Active Alerts" : "✅ All Clear"}</h3>
          {(activeCritical.length > 0 || activeWarning.length > 0) && (
            <div className="alert-panel-counts">
              {activeCritical.length > 0 && (
                <span className="alert-count-badge critical">{activeCritical.length} Critical</span>
              )}
              {activeWarning.length > 0 && (
                <span className="alert-count-badge warning">{activeWarning.length} Warning</span>
              )}
            </div>
          )}
        </div>
        <div className="alert-panel-actions">
          <span className="alert-refresh-note">Auto-refreshes every 8s</span>
          {totalActive > 0 && (
            <button className="btn btn-sm" onClick={dismissAll}>
              Dismiss All
            </button>
          )}
        </div>
      </div>

      {error && <div className="alert-empty">Unable to fetch alerts: {error}</div>}

      {!error && activeAlerts.length === 0 && (
        <div className="alert-empty">
          <div className="alert-empty-icon">✓</div>
          <div className="alert-empty-text">All modules operating normally</div>
          <div className="alert-empty-sub">No warnings or critical alerts detected.</div>
        </div>
      )}

      {activeAlerts.length > 0 && (
        <div className="alert-list">
          {/* Critical alerts first */}
          {activeCritical.map((alert) => (
            <AlertItem key={alert.id} alert={alert} onDismiss={dismissAlert} />
          ))}
          {activeWarning.map((alert) => (
            <AlertItem key={alert.id} alert={alert} onDismiss={dismissAlert} />
          ))}
          {activeInfo.map((alert) => (
            <AlertItem key={alert.id} alert={alert} onDismiss={dismissAlert} />
          ))}
        </div>
      )}
    </div>
  );
}

function AlertItem({ alert, onDismiss }: { alert: Alert; onDismiss: (id: string) => void }) {
  const timeAgo = formatTimeAgo(alert.detected_at);

  return (
    <div className={`alert-item ${alert.severity}`}>
      <div className="alert-item-left">
        <span className={`alert-item-icon ${alert.severity}`}>
          {alert.severity === "critical" ? "🔴" : alert.severity === "warning" ? "🟡" : "🔵"}
        </span>
        <div className="alert-item-body">
          <div className="alert-item-title">{alert.title}</div>
          <div className="alert-item-message">{alert.message}</div>
          <div className="alert-item-meta">
            <span className="alert-item-module">{alert.module_name}</span>
            <span className="alert-item-metric">
              {alert.metric}: {alert.value} (threshold: {alert.threshold})
            </span>
            <span className="alert-item-time">{timeAgo}</span>
          </div>
        </div>
      </div>
      <button className="btn-icon" onClick={() => onDismiss(alert.id)} title="Dismiss">
        ✕
      </button>
    </div>
  );
}

function formatTimeAgo(ts: number): string {
  const diff = Date.now() - ts;
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

/** Global system health panel for the root dashboard */
export function SystemHealthPanel() {
  // Poll all active module health endpoints
  const moduleIds = [
    "cybersecurity",
    "health",
    "finance",
    "retail",
    "transport",
    "manufacturing",
    "tourism",
    "cultural_heritage",
    "professional",
    "utilities",
    "sme",
  ];

  const [moduleHealth, setModuleHealth] = useState<
    Record<string, { status: string; cpu: number; memory: number }>
  >({});

  useEffect(() => {
    const loadAll = async () => {
      const results: Record<string, any> = {};
      for (const id of moduleIds) {
        try {
          const res = await fetch(`/api/os/apps/${id}/live`, { cache: "no-store" });
          const d: LiveData = await res.json();
          if (d.ok) {
            results[id] = {
              status: d.system.status,
              cpu: d.system.cpu_pct,
              memory: d.system.memory_mb,
            };
          }
        } catch {
          // silently skip
        }
      }
      setModuleHealth(results);
    };
    loadAll();
    const t = setInterval(loadAll, 10000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const healthyCount = Object.values(moduleHealth).filter((m) => m.status === "healthy").length;
  const warnCount = Object.values(moduleHealth).filter((m) => m.status === "warning").length;
  const criticalCount = Object.values(moduleHealth).filter((m) => m.status === "critical").length;

  return (
    <div className="live-system-panel">
      <div className="system-panel-header">
        <div className="system-panel-title-row">
          <h3>🧬 System Health</h3>
          <span className={`live-dot ok`} />
        </div>
        <div className="system-panel-stats">
          <span className="system-stat ok">{healthyCount} healthy</span>
          {warnCount > 0 && <span className="system-stat warn">{warnCount} warning</span>}
          {criticalCount > 0 && (
            <span className="system-stat danger">{criticalCount} critical</span>
          )}
          <span className="system-stat muted">
            {Object.keys(moduleHealth).length} / {moduleIds.length} reporting
          </span>
        </div>
      </div>
      <div className="system-modules-grid">
        {moduleIds.map((id) => {
          const h = moduleHealth[id];
          return (
            <div key={id} className="system-module-chip">
              <span
                className={`live-dot ${!h ? "pending" : h.status === "healthy" ? "ok" : h.status === "warning" ? "warn" : "danger"}`}
              />
              <span className="sm-name">{id.replace(/_/g, " ")}</span>
              {h && <span className="sm-meta">CPU {Math.round(h.cpu)}%</span>}
            </div>
          );
        })}
      </div>
    </div>
  );
}
