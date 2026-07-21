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
      <div className="live-bar-indicator" title={error ? "Error" : data ? "Streaming live" : "Connecting..."}>
        <span className={`live-dot ${error ? "danger" : data ? "ok" : "pending"}`} />
        <span className="live-label">
          {error ? "OFFLINE" : data ? "LIVE" : "CONNECTING"}
        </span>
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
            <span className="live-metric-label" style={{ color: sys.memory_mb > 600 ? "var(--danger)" : undefined }}>
              Memory
            </span>
            <span className="live-metric-value" style={{ color: sys.memory_mb > 600 ? "var(--danger)" : undefined }}>
              {fmt(sys.memory_mb)} MB
            </span>
          </div>
          <div className="live-metric">
            <span className="live-metric-label" style={{ color: sys.cpu_pct > 80 ? "var(--danger)" : undefined }}>
              CPU
            </span>
            <span className="live-metric-value" style={{ color: sys.cpu_pct > 80 ? "var(--danger)" : undefined }}>
              {Math.round(sys.cpu_pct)}%
            </span>
          </div>
          <div className="live-metric">
            <span className="live-metric-label">Success Rate</span>
            <span className="live-metric-value" style={{ color: sys.tool_success_rate < 0.85 ? "var(--warning)" : "var(--success)" }}>
              {(sys.tool_success_rate * 100).toFixed(0)}%
            </span>
          </div>
          <div className="live-metric">
            <span className="live-metric-label">Goals Active</span>
            <span className="live-metric-value">{sys.active_goals}</span>
          </div>
          <div className="live-metric">
            <span className="live-metric-label">Status</span>
            <span className={`live-status-badge ${isHealthy ? "ok" : "warn"}`}>
              {sys.status}
            </span>
          </div>
        </>
      )}

      <div className="live-bar-timer">
        {new Date(data?.ts ?? Date.now()).toLocaleTimeString()}
      </div>
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
                  <span
                    className={`live-diff ${isUp ? "up" : isDown ? "down" : ""}`}
                  >
                    {isUp ? "↑" : isDown ? "↓" : "—"}{" "}
                    {Math.abs(Math.round(diff))}
                  </span>
                  <span
                    className={`live-status-indicator ${m.status}`}
                    title={m.status}
                  />
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

/** Global system health panel for the root dashboard */
export function SystemHealthPanel() {
  // Poll all active module health endpoints
  const moduleIds = [
    "cybersecurity", "health", "finance", "retail", "transport",
    "manufacturing", "tourism", "cultural_heritage", "professional",
    "utilities", "sme",
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

  const healthyCount = Object.values(moduleHealth).filter(
    (m) => m.status === "healthy",
  ).length;
  const warnCount = Object.values(moduleHealth).filter(
    (m) => m.status === "warning",
  ).length;
  const criticalCount = Object.values(moduleHealth).filter(
    (m) => m.status === "critical",
  ).length;

  return (
    <div className="live-system-panel">
      <div className="system-panel-header">
        <div className="system-panel-title-row">
          <h3>🧬 System Health</h3>
          <span className={`live-dot ok`} />
        </div>
        <div className="system-panel-stats">
          <span className="system-stat ok">{healthyCount} healthy</span>
          {warnCount > 0 && (
            <span className="system-stat warn">{warnCount} warning</span>
          )}
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
              {h && (
                <span className="sm-meta">
                  CPU {Math.round(h.cpu)}%
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
