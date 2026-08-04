"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSession } from "next-auth/react";
import { getAuthHeaders } from "@/lib/flask-auth";

type UsageSummary = {
  period_days: number;
  workspace_id?: string;
  total_events: number;
  total_quantity: number;
  total_cost: number;
  by_action: Record<string, { quantity: number; cost: number; count: number }>;
  by_module: Record<string, { quantity: number; cost: number; count: number }>;
  by_day: Record<string, { quantity: number; cost: number; count: number }>;
};

type BillingStatus = {
  workspace_id: string;
  plan: { id: string; name: string; limits: Record<string, number> };
  credits: number;
  usage: { requests: number; tokens: number; workflows: number; integrations: number };
  limits: Record<string, number>;
  estimated_cost: number;
  remaining_credits: number;
  quota_usage_pct: Record<string, number>;
};

type HealthStatus = {
  ok: boolean;
  timestamp: number;
  kernel: { status: string; backend: string };
  agents: { app_id: string; ticks: number; vitals: Record<string, any> }[];
  queue: { size: number; status: string };
  integrations: { id: string; name: string; type: string; enabled: boolean }[];
  storage: { usage_events_bytes?: number; usage_events_mb?: number; error?: string };
};

type OperationsSnapshot = {
  ok: boolean;
  error?: string;
  workspace_id?: string;
  generated_at?: string;
  runtime?: {
    backend: string;
    ready: boolean;
    environment?: { ok?: boolean; missing?: string[]; warnings?: string[] };
  };
  agent?: { app_id: string; ticks: number; vitals: Record<string, any> };
  memory?: {
    episodic_events: number;
    semantic_nodes: number;
    semantic_edges: number;
    procedural_skills: number;
  };
  goals?: { open: number; total: number };
  worker?: {
    pending: number;
    workers: number;
    tracked_jobs: number;
    status_counts: Record<string, number>;
  };
  automations?: {
    policies: { total: number; enabled: number };
    budgets: { total: number; enabled: number };
    executions_last_24h: number;
    execution_statuses: Record<string, number>;
  };
};

function statusColor(status: string | undefined, healthy = "#22c55e") {
  if (status === "ok" || status === "healthy") return healthy;
  if (status === "warning" || status === "degraded") return "#f59e0b";
  return "var(--fg-mute)";
}

function SnapshotStat({
  label,
  value,
  detail,
}: {
  label: string;
  value: string | number;
  detail?: string;
}) {
  return (
    <div
      style={{
        padding: "14px 16px",
        background: "var(--bg-elevated)",
        borderRadius: 10,
        border: "1px solid var(--border)",
      }}
    >
      <div
        style={{
          fontSize: "0.72rem",
          color: "var(--fg-mute)",
          textTransform: "uppercase",
          letterSpacing: 0.8,
        }}
      >
        {label}
      </div>
      <div style={{ fontSize: "1.55rem", fontWeight: 700, marginTop: 5 }}>{value}</div>
      {detail && (
        <div style={{ fontSize: "0.75rem", color: "var(--fg-mute)", marginTop: 3 }}>{detail}</div>
      )}
    </div>
  );
}

function useFetch<T>(url: string, authenticated = false) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    fetch(url, {
      cache: "no-store",
      headers: authenticated ? getAuthHeaders() : undefined,
    })
      .then(async (response) => {
        const payload = await response.json();
        if (!response.ok || payload?.ok === false) {
          throw new Error(payload?.error || `Request failed (${response.status})`);
        }
        return payload;
      })
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
  }, [authenticated, url]);

  return { data, loading, error };
}

function Card({
  title,
  children,
  className = "",
}: {
  title?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`os-card ${className}`} style={{ padding: 20 }}>
      {title && (
        <h3
          style={{
            margin: "0 0 16px",
            fontSize: "0.95rem",
            textTransform: "uppercase",
            letterSpacing: 1,
            color: "var(--fg-mute)",
          }}
        >
          {title}
        </h3>
      )}
      {children}
    </div>
  );
}

function Progress({ value, label }: { value: number; label: string }) {
  const pct = Math.min(100, Math.max(0, value));
  return (
    <div style={{ marginBottom: 12 }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          fontSize: "0.85rem",
          marginBottom: 4,
        }}
      >
        <span>{label}</span>
        <span>{pct.toFixed(1)}%</span>
      </div>
      <div
        style={{ height: 8, background: "var(--bg-elevated)", borderRadius: 4, overflow: "hidden" }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: "100%",
            background: "var(--accent)",
            borderRadius: 4,
            transition: "width 0.3s ease",
          }}
        />
      </div>
    </div>
  );
}

function BarChart({ data }: { data: { label: string; value: number }[] }) {
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 8, height: 120, paddingTop: 10 }}>
      {data.map((d, i) => (
        <div
          key={i}
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 4,
          }}
        >
          <div
            style={{
              width: "100%",
              height: `${(d.value / max) * 100}%`,
              background: "var(--accent)",
              borderRadius: 4,
              minHeight: 4,
              opacity: 0.85,
            }}
          />
          <span style={{ fontSize: "0.7rem", color: "var(--fg-mute)", textAlign: "center" }}>
            {d.label}
          </span>
        </div>
      ))}
    </div>
  );
}

export default function ObservabilityPage() {
  const { data: session } = useSession();
  const workspaceId = ((session?.user as any)?.workspaceId as string) || "default";

  const { data: usage, loading: usageLoading } = useFetch<{ ok: boolean; summary: UsageSummary }>(
    "/api/os/observability/usage"
  );
  const { data: billing, loading: billingLoading } = useFetch<{
    ok: boolean;
    billing: BillingStatus;
  }>("/api/os/observability/billing");
  const { data: health, loading: healthLoading } = useFetch<{ ok: boolean } & HealthStatus>(
    "/api/os/observability/health"
  );
  const { data: metrics } = useFetch<{ ok: boolean; metrics: UsageSummary }>(
    "/api/os/observability/metrics"
  );
  const {
    data: snapshot,
    loading: snapshotLoading,
    error: snapshotError,
  } = useFetch<OperationsSnapshot>("/api/os/observability/snapshot", true);

  const actionBars = useMemo(() => {
    const byAction = usage?.summary?.by_action || {};
    return Object.entries(byAction).map(([k, v]) => ({ label: k, value: v.count || 0 }));
  }, [usage]);

  const moduleBars = useMemo(() => {
    const byModule = usage?.summary?.by_module || {};
    return Object.entries(byModule).map(([k, v]) => ({ label: k, value: v.count || 0 }));
  }, [usage]);

  const dailyBars = useMemo(() => {
    const byDay = metrics?.metrics?.by_day || usage?.summary?.by_day || {};
    return Object.entries(byDay)
      .slice(-14)
      .map(([k, v]) => ({ label: k.slice(5), value: v.count || 0 }));
  }, [metrics, usage]);

  return (
    <div className="os-page">
      <header className="os-header">
        <div>
          <h1
            style={{
              background: "var(--grad)",
              WebkitBackgroundClip: "text",
              backgroundClip: "text",
              color: "transparent",
            }}
          >
            📊 Observability & Billing
          </h1>
          <p className="dashboard-subtitle">
            Usage metering, cost visibility, and system health for AEON OS
          </p>
        </div>
        <Link href="/os" className="btn btn-sm">
          ← OS Launcher
        </Link>
      </header>

      {(usageLoading || billingLoading || healthLoading || snapshotLoading) && (
        <div className="skeleton-page" role="status" aria-label="Loading observability">
          <span className="sr-only">Loading observability data…</span>
          <div
            className="os-grid"
            style={{ gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}
          >
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="skeleton-card" style={{ flexDirection: "column" }}>
                <div
                  className="skeleton-shimmer"
                  style={{ height: "0.7rem", width: "40%", marginBottom: "0.75rem" }}
                />
                <div
                  className="skeleton-shimmer"
                  style={{ height: "2rem", width: "30%", marginBottom: "0.5rem" }}
                />
              </div>
            ))}
          </div>
        </div>
      )}

      {snapshotError && (
        <div
          role="status"
          style={{
            marginTop: 16,
            padding: "12px 16px",
            border: "1px solid color-mix(in srgb, var(--accent) 35%, var(--border))",
            borderRadius: 10,
            color: "var(--fg-mute)",
          }}
        >
          Live operations data is temporarily unavailable. Usage and billing data remain available.
        </div>
      )}

      {/* KPIs */}
      <section
        className="os-grid"
        style={{ gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}
      >
        <Card title="Total Events">
          <div style={{ fontSize: "2rem", fontWeight: 700 }}>
            {usage?.summary?.total_events ?? 0}
          </div>
          <div style={{ fontSize: "0.85rem", color: "var(--fg-mute)" }}>
            Last {usage?.summary?.period_days ?? 30} days
          </div>
        </Card>
        <Card title="Compute Units">
          <div style={{ fontSize: "2rem", fontWeight: 700 }}>
            {(usage?.summary?.total_quantity ?? 0).toLocaleString()}
          </div>
          <div style={{ fontSize: "0.85rem", color: "var(--fg-mute)" }}>
            Tokens / requests / ticks
          </div>
        </Card>
        <Card title="Estimated Cost">
          <div style={{ fontSize: "2rem", fontWeight: 700 }}>
            ${(billing?.billing?.estimated_cost ?? 0).toFixed(4)}
          </div>
          <div style={{ fontSize: "0.85rem", color: "var(--fg-mute)" }}>Based on plan pricing</div>
        </Card>
        <Card title="Queue Health">
          <div style={{ fontSize: "2rem", fontWeight: 700 }}>{health?.queue?.size ?? 0}</div>
          <div style={{ fontSize: "0.85rem", color: "var(--fg-mute)" }}>
            {health?.queue?.status ?? "unknown"}
          </div>
        </Card>
      </section>

      {/* Live Operations Snapshot */}
      <section style={{ marginTop: 24 }}>
        <Card title="Live Operations Snapshot">
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              gap: 16,
              marginBottom: 16,
            }}
          >
            <div style={{ color: "var(--fg-mute)", fontSize: "0.85rem" }}>
              Workspace-scoped runtime, memory, worker, and automation state.
            </div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 7,
                whiteSpace: "nowrap",
                fontSize: "0.82rem",
              }}
            >
              <span
                aria-hidden="true"
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: statusColor(snapshot?.runtime?.ready ? "ok" : "unknown"),
                  display: "inline-block",
                }}
              />
              {snapshot?.runtime?.ready
                ? "Runtime ready"
                : snapshot
                  ? "Runtime needs attention"
                  : "Waiting for runtime"}
            </div>
          </div>
          <div
            className="os-grid"
            style={{ gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))" }}
          >
            <SnapshotStat
              label="Agent ticks"
              value={snapshot?.agent?.ticks ?? 0}
              detail={snapshot?.agent?.app_id ?? "No workspace agent"}
            />
            <SnapshotStat
              label="Open goals"
              value={snapshot?.goals?.open ?? 0}
              detail={`${snapshot?.goals?.total ?? 0} total`}
            />
            <SnapshotStat
              label="Memory events"
              value={snapshot?.memory?.episodic_events ?? 0}
              detail={`${snapshot?.memory?.semantic_nodes ?? 0} semantic nodes`}
            />
            <SnapshotStat
              label="Pending work"
              value={snapshot?.worker?.pending ?? 0}
              detail={`${snapshot?.worker?.workers ?? 0} workers`}
            />
            <SnapshotStat
              label="Policies"
              value={snapshot?.automations?.policies?.enabled ?? 0}
              detail={`${snapshot?.automations?.policies?.total ?? 0} total`}
            />
            <SnapshotStat
              label="Executions · 24h"
              value={snapshot?.automations?.executions_last_24h ?? 0}
              detail={`${snapshot?.automations?.budgets?.enabled ?? 0} budgets enabled`}
            />
          </div>
        </Card>
      </section>

      {/* Billing & Usage */}
      <section
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
          gap: 24,
          marginTop: 24,
        }}
      >
        <Card title="Plan & Quotas" className="billing-card">
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: 16,
            }}
          >
            <span style={{ fontSize: "1.1rem", fontWeight: 600 }}>
              {billing?.billing?.plan?.name ?? "Free"}
            </span>
            <span style={{ fontSize: "0.85rem", color: "var(--fg-mute)" }}>
              Workspace: {workspaceId}
            </span>
          </div>{" "}
          {billing?.billing?.plan?.limits &&
            Object.entries(billing.billing.plan.limits).map(([key]) => {
              const pct = billing.billing?.quota_usage_pct?.[key] ?? 0;
              return <Progress key={key} label={key} value={pct} />;
            })}
          <div style={{ marginTop: 16, paddingTop: 16, borderTop: "1px solid var(--border)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.9rem" }}>
              <span>Credits</span>
              <span>${(billing?.billing?.credits ?? 0).toFixed(2)}</span>
            </div>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                fontSize: "0.9rem",
                marginTop: 4,
              }}
            >
              <span>Remaining</span>
              <span>${(billing?.billing?.remaining_credits ?? 0).toFixed(2)}</span>
            </div>
          </div>
        </Card>

        <Card title="Usage by Action">
          {actionBars.length > 0 ? (
            <BarChart data={actionBars} />
          ) : (
            <div style={{ color: "var(--fg-mute)", padding: 20, textAlign: "center" }}>
              No usage yet
            </div>
          )}
        </Card>

        <Card title="Usage by Module">
          {moduleBars.length > 0 ? (
            <BarChart data={moduleBars} />
          ) : (
            <div style={{ color: "var(--fg-mute)", padding: 20, textAlign: "center" }}>
              No module usage yet
            </div>
          )}
        </Card>
      </section>

      {/* Time series & Health */}
      <section
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
          gap: 24,
          marginTop: 24,
        }}
      >
        <Card title="Daily Activity" className="chart-card">
          {dailyBars.length > 0 ? (
            <BarChart data={dailyBars} />
          ) : (
            <div style={{ color: "var(--fg-mute)", padding: 20, textAlign: "center" }}>
              No daily data yet
            </div>
          )}
        </Card>

        <Card title="System Health">
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
            <span>Kernel</span>
            <span
              className={`settings-status ${health?.kernel?.status === "ok" ? "connected" : "disconnected"}`}
            >
              {health?.kernel?.status ?? "unknown"}
            </span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
            <span>Backend</span>
            <span style={{ fontFamily: "monospace", fontSize: "0.8rem" }}>
              {health?.kernel?.backend ?? "unknown"}
            </span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
            <span>Active Agents</span>
            <span>{health?.agents?.length ?? 0}</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
            <span>Integrations</span>
            <span>{health?.integrations?.length ?? 0}</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
            <span>Storage</span>
            <span>{health?.storage?.usage_events_mb?.toFixed(2) ?? 0} MB</span>
          </div>
        </Card>

        <Card title="Active Agents">
          {health?.agents?.length ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {health.agents.map((agent) => (
                <div
                  key={agent.app_id}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    padding: "8px 12px",
                    background: "var(--bg-elevated)",
                    borderRadius: 8,
                  }}
                >
                  <span>{agent.app_id}</span>
                  <span style={{ fontSize: "0.8rem", color: "var(--fg-mute)" }}>
                    {agent.ticks} ticks
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ color: "var(--fg-mute)", padding: 20, textAlign: "center" }}>
              No active agents
            </div>
          )}
        </Card>
      </section>
    </div>
  );
}
