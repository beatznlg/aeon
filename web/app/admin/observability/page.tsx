"use client";

import { useCallback, useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { redirect } from "next/navigation";
import Link from "next/link";
import { getAuthHeaders } from "@/lib/flask-auth";
import ErrorState from "@/components/ui/ErrorState";

/* ── Types ─────────────────────────────────────────────────────────────── */

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
  ai_ledger?: {
    ok?: boolean;
    total_records?: number;
    total_tokens?: number;
    total_cost_usd?: number;
    avg_latency_ms?: number;
    by_status?: Record<string, number>;
    by_sector?: Record<string, number>;
    by_provider?: Record<string, number>;
    daily?: {
      date: string;
      executions: number;
      tokens: number;
      cost_usd: number;
      latency_ms: number;
    }[];
  };
  dead_letters?: {
    total: number;
    recent: {
      job_id: string;
      attempts: number;
      error: string;
      submitted_at: string;
    }[];
  };
};

type MetricsSummary = {
  ok: boolean;
  metrics?: {
    period_days: number;
    total_events: number;
    total_quantity: number;
    total_cost: number;
    by_action: Record<string, { quantity: number; cost: number; count: number }>;
    by_module: Record<string, { quantity: number; cost: number; count: number }>;
  };
};

type AIExecution = {
  id: string;
  timestamp: string;
  sector?: string;
  provider?: string;
  model?: string;
  status: string;
  risk_level?: string;
  latency_ms?: number;
  tokens_total?: number;
  cost_usd?: number;
  error?: string;
};

/* ── Helpers ───────────────────────────────────────────────────────────── */

function statusDot(ok: boolean) {
  return (
    <span
      className="inline-block h-2 w-2 rounded-full"
      style={{
        background: ok ? "#22c55e" : "#ef4444",
        boxShadow: ok
          ? "0 0 6px rgba(34,197,94,0.5)"
          : "0 0 6px rgba(239,68,68,0.5)",
      }}
    />
  );
}

function formatCost(usd: number): string {
  if (usd < 0.01) return "<$0.01";
  return `$${usd.toFixed(2)}`;
}

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function timeAgo(iso: string): string {
  if (!iso) return "—";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

/* ── Card components ───────────────────────────────────────────────────── */

function MetricCard({
  label,
  value,
  sub,
  color,
}: {
  label: string;
  value: string | number;
  sub?: string;
  color: string;
}) {
  return (
    <div className="os-card">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-xs font-semibold uppercase tracking-wider text-aeon-fg-mute">
          {label}
        </span>
      </div>
      <div className="text-2xl font-bold" style={{ color }}>
        {value}
      </div>
      {sub && <div className="text-xs text-aeon-fg-mute mt-1">{sub}</div>}
    </div>
  );
}

function SectionHeader({
  title,
  action,
}: {
  title: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between mb-4">
      <h2 className="text-lg font-bold text-aeon-fg">{title}</h2>
      {action}
    </div>
  );
}

/* ── Status breakdown bar ──────────────────────────────────────────────── */

function TrendChart({
  data,
  valueKey,
  label,
  color,
  formatter = (value) => String(value),
}: {
  data: NonNullable<OperationsSnapshot["ai_ledger"]>["daily"];
  valueKey: "executions" | "tokens" | "cost_usd" | "latency_ms";
  label: string;
  color: string;
  formatter?: (value: number) => string;
}) {
  if (!data?.length) {
    return (
      <div className="os-card min-h-[150px]">
        <div className="text-xs font-semibold uppercase tracking-wider text-aeon-fg-mute">{label}</div>
        <div className="flex h-24 items-center justify-center text-xs text-aeon-fg-mute">No trend data yet</div>
      </div>
    );
  }

  const values = data.map((point) => Number(point[valueKey]) || 0);
  const max = Math.max(...values, 1);
  const width = 320;
  const height = 92;
  const padding = 8;
  const points = values
    .map((value, index) => {
      const x = padding + (index / Math.max(values.length - 1, 1)) * (width - padding * 2);
      const y = height - padding - (value / max) * (height - padding * 2);
      return `${x},${y}`;
    })
    .join(" ");
  const latest = values[values.length - 1];

  return (
    <div className="os-card">
      <div className="flex items-center justify-between gap-3">
        <div className="text-xs font-semibold uppercase tracking-wider text-aeon-fg-mute">{label}</div>
        <div className="font-mono text-sm" style={{ color }}>{formatter(latest)}</div>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} className="mt-3 h-24 w-full" role="img" aria-label={`${label} trend`}>
        <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} stroke="rgba(255,255,255,0.08)" />
        <polyline points={points} fill="none" stroke={color} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        {values.length === 1 ? (
          <circle cx={padding} cy={height - padding - (latest / max) * (height - padding * 2)} r="3" fill={color} />
        ) : null}
      </svg>
      <div className="mt-1 flex justify-between text-[10px] text-aeon-fg-mute">
        <span>{data[0].date}</span>
        <span>{data[data.length - 1].date}</span>
      </div>
    </div>
  );
}

function IncidentFeed({
  deadLetters,
  executions,
}: {
  deadLetters?: OperationsSnapshot["dead_letters"];
  executions: AIExecution[];
}) {
  const incidents = [
    ...(deadLetters?.recent ?? []).map((entry) => ({
      id: `job-${entry.job_id}`,
      kind: "Dead letter",
      status: "failed",
      detail: entry.error || "Job exhausted retry attempts",
      meta: `${entry.attempts} attempts · ${timeAgo(entry.submitted_at)}`,
    })),
    ...executions
      .filter((execution) => ["failed", "error", "blocked_by_policy", "needs_review"].includes(execution.status))
      .map((execution) => ({
        id: `ai-${execution.id}`,
        kind: "AI execution",
        status: execution.status,
        detail: execution.error || `${execution.provider || "Unknown provider"} · ${execution.model || "Unknown model"}`,
        meta: `${execution.sector || "Unspecified sector"} · ${timeAgo(execution.timestamp)}`,
      })),
  ].slice(0, 12);

  return (
    <div className="os-card mb-8">
      {incidents.length ? (
        <div className="divide-y divide-white/5">
          {incidents.map((incident) => (
            <div key={incident.id} className="flex items-start gap-3 py-3 first:pt-0 last:pb-0">
              <span className="mt-1">{statusDot(false)}</span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  <span className="font-medium text-aeon-fg">{incident.kind}</span>
                  <span className="rounded-full bg-red-500/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-red-400">
                    {incident.status.replaceAll("_", " ")}
                  </span>
                </div>
                <p className="mt-1 truncate text-xs text-aeon-fg-soft" title={incident.detail}>
                  {incident.detail}
                </p>
                <p className="mt-1 text-[10px] text-aeon-fg-mute">{incident.meta}</p>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="py-4 text-center text-sm text-aeon-fg-soft">
          No failed jobs or policy-blocked AI executions in the recent feed.
        </div>
      )}
    </div>
  );
}

function StatusBreakdown({
  counts,
}: {
  counts: Record<string, number>;
}) {
  const total = Object.values(counts).reduce((s, v) => s + v, 0);
  if (total === 0) return <span className="text-xs text-aeon-fg-mute">No data</span>;

  const colors: Record<string, string> = {
    ok: "#22c55e",
    success: "#22c55e",
    completed: "#22c55e",
    failed: "#ef4444",
    error: "#ef4444",
    pending: "#f59e0b",
    running: "#6366f1",
    blocked_by_policy: "#f97316",
    needs_review: "#a855f7",
  };

  return (
    <div className="space-y-1.5">
      <div className="flex h-2 overflow-hidden rounded-full bg-white/5">
        {Object.entries(counts).map(([status, count]) => (
          <div
            key={status}
            style={{
              width: `${(count / total) * 100}%`,
              background: colors[status] || "#64748b",
            }}
            title={`${status}: ${count}`}
          />
        ))}
      </div>
      <div className="flex flex-wrap gap-3">
        {Object.entries(counts).map(([status, count]) => (
          <div key={status} className="flex items-center gap-1.5 text-xs">
            <span
              className="h-2 w-2 rounded-full"
              style={{ background: colors[status] || "#64748b" }}
            />
            <span className="text-aeon-fg-soft capitalize">{status}</span>
            <span className="font-mono text-aeon-fg-mute">{count}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Main page ─────────────────────────────────────────────────────────── */

export default function AdminObservabilityPage() {
  const { data: session } = useSession();
  const role = (session?.user as any)?.role;

  const [snapshot, setSnapshot] = useState<OperationsSnapshot | null>(null);
  const [metrics, setMetrics] = useState<MetricsSummary | null>(null);
  const [recentExecutions, setRecentExecutions] = useState<AIExecution[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [snapRes, metricsRes, executionsRes] = await Promise.all([
        fetch("/api/admin/observability", { cache: "no-store" }),
        fetch("/api/admin/observability/metrics", { cache: "no-store" }),
        fetch("/api/admin/observability/executions?limit=50", { cache: "no-store" }),
      ]);
      const snap = await snapRes.json();
      const met = await metricsRes.json();
      const executionData = await executionsRes.json();
      if (snap.ok) setSnapshot(snap);
      else setError(snap.error || "Failed to load observability data");
      if (met.ok) setMetrics(met);
      if (executionData.ok) setRecentExecutions(executionData.executions || []);
      setLastRefresh(new Date());
    } catch (e: any) {
      setError(e?.message || "Failed to load observability data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  if (role && role !== "ADMIN") {
    redirect("/settings");
    return null;
  }

  const worker = snapshot?.worker;
  const aiLedger = snapshot?.ai_ledger;
  const deadLetters = snapshot?.dead_letters;
  const automations = snapshot?.automations;
  const runtime = snapshot?.runtime;
  const agent = snapshot?.agent;

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
            🔭 Observability Dashboard
          </h1>
          <p className="dashboard-subtitle">
            Real-time system health, AI execution metrics, and operational signals.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {lastRefresh && (
            <span className="text-xs text-aeon-fg-mute">
              Updated {lastRefresh.toLocaleTimeString()}
            </span>
          )}
          <button
            onClick={fetchData}
            disabled={loading}
            className="btn btn-sm"
          >
            {loading ? "Refreshing..." : "Refresh"}
          </button>
        </div>
      </header>

      {error && (
        <div className="mb-4">
          <ErrorState error={error} onRetry={fetchData} />
        </div>
      )}

      {/* ── System Health Row ─────────────────────────────────────────── */}
      <SectionHeader title="System Health" />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
        <MetricCard
          label="Backend"
          value={runtime?.ready ? "Online" : "Offline"}
          sub={runtime?.backend || "—"}
          color={runtime?.ready ? "#22c55e" : "#ef4444"}
        />
        <MetricCard
          label="Agent Ticks"
          value={formatNumber(agent?.ticks ?? 0)}
          sub={agent?.app_id || "—"}
          color="#6366f1"
        />
        <MetricCard
          label="Worker Queue"
          value={worker?.pending ?? 0}
          sub={`${worker?.workers ?? 0} workers`}
          color="#f59e0b"
        />
        <MetricCard
          label="Dead Letters"
          value={deadLetters?.total ?? 0}
          sub="Failed jobs"
          color={deadLetters && deadLetters.total > 0 ? "#ef4444" : "#22c55e"}
        />
      </div>

      {/* ── Request and usage metrics ────────────────────────────────── */}
      <SectionHeader title="Request & Usage Metrics" />
      {metrics?.metrics ? (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 mb-4">
            <MetricCard
              label="Usage Events"
              value={formatNumber(metrics.metrics.total_events)}
              sub={`Last ${metrics.metrics.period_days} days`}
              color="#6366f1"
            />
            <MetricCard
              label="Units Processed"
              value={formatNumber(Math.round(metrics.metrics.total_quantity))}
              sub="Metered quantity"
              color="#06b6d4"
            />
            <MetricCard
              label="Metered Cost"
              value={formatCost(metrics.metrics.total_cost)}
              sub="Usage estimate"
              color="#f59e0b"
            />
            <MetricCard
              label="Action Types"
              value={Object.keys(metrics.metrics.by_action).length}
              sub="Observed actions"
              color="#10b981"
            />
          </div>
          {Object.keys(metrics.metrics.by_action).length > 0 && (
            <div className="os-card mb-8">
              <div className="text-xs font-semibold uppercase tracking-wider text-aeon-fg-mute mb-3">
                Usage by Action
              </div>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {Object.entries(metrics.metrics.by_action)
                  .sort((a, b) => b[1].count - a[1].count)
                  .slice(0, 9)
                  .map(([action, usage]) => (
                    <div key={action} className="flex items-center justify-between rounded-lg bg-white/[0.03] px-3 py-2 text-sm">
                      <span className="text-aeon-fg-soft">{action.replaceAll("_", " ")}</span>
                      <span className="font-mono text-xs text-aeon-fg-mute">{formatNumber(usage.count)}</span>
                    </div>
                  ))}
              </div>
            </div>
          )}
        </>
      ) : (
        <div className="os-card mb-8 py-6 text-center text-sm text-aeon-fg-mute">
          Request metrics will appear after usage events are recorded.
        </div>
      )}

      {/* ── AI Execution Summary ──────────────────────────────────────── */}
      <SectionHeader title="AI Execution Ledger" />
      {aiLedger && aiLedger.ok !== false ? (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            <MetricCard
              label="Total Calls"
              value={formatNumber(aiLedger.total_records ?? 0)}
              color="#6366f1"
            />
            <MetricCard
              label="Total Tokens"
              value={formatNumber(aiLedger.total_tokens ?? 0)}
              color="#06b6d4"
            />
            <MetricCard
              label="Total Cost"
              value={formatCost(aiLedger.total_cost_usd ?? 0)}
              color="#f59e0b"
            />
            <MetricCard
              label="Avg Latency"
              value={`${aiLedger.avg_latency_ms ?? 0}ms`}
              color="#8b5cf6"
            />
          </div>

          {aiLedger.by_status && Object.keys(aiLedger.by_status).length > 0 && (
            <div className="os-card mb-4">
              <div className="text-xs font-semibold uppercase tracking-wider text-aeon-fg-mute mb-3">
                Execution Status
              </div>
              <StatusBreakdown counts={aiLedger.by_status} />
            </div>
          )}

          <div className="mb-4 grid grid-cols-1 gap-3 md:grid-cols-3">
            <TrendChart
              data={aiLedger.daily}
              valueKey="executions"
              label="Daily executions"
              color="#6366f1"
              formatter={(value) => formatNumber(value)}
            />
            <TrendChart
              data={aiLedger.daily}
              valueKey="tokens"
              label="Daily tokens"
              color="#06b6d4"
              formatter={(value) => formatNumber(value)}
            />
            <TrendChart
              data={aiLedger.daily}
              valueKey="cost_usd"
              label="Daily AI cost"
              color="#f59e0b"
              formatter={formatCost}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-8">
            {aiLedger.by_sector && Object.keys(aiLedger.by_sector).length > 0 && (
              <div className="os-card">
                <div className="text-xs font-semibold uppercase tracking-wider text-aeon-fg-mute mb-3">
                  By Sector
                </div>
                <div className="space-y-1.5">
                  {Object.entries(aiLedger.by_sector)
                    .sort((a, b) => b[1] - a[1])
                    .slice(0, 8)
                    .map(([sector, count]) => (
                      <div key={sector} className="flex items-center justify-between text-sm">
                        <span className="text-aeon-fg-soft capitalize">{sector}</span>
                        <span className="font-mono text-aeon-fg-mute">{count}</span>
                      </div>
                    ))}
                </div>
              </div>
            )}

            {aiLedger.by_provider && Object.keys(aiLedger.by_provider).length > 0 && (
              <div className="os-card">
                <div className="text-xs font-semibold uppercase tracking-wider text-aeon-fg-mute mb-3">
                  By Provider
                </div>
                <div className="space-y-1.5">
                  {Object.entries(aiLedger.by_provider)
                    .sort((a, b) => b[1] - a[1])
                    .slice(0, 8)
                    .map(([provider, count]) => (
                      <div key={provider} className="flex items-center justify-between text-sm">
                        <span className="text-aeon-fg-soft">{provider}</span>
                        <span className="font-mono text-aeon-fg-mute">{count}</span>
                      </div>
                    ))}
                </div>
              </div>
            )}
          </div>
        </>
      ) : (
        <div className="os-card mb-8 text-center py-8 text-aeon-fg-mute text-sm">
          AI ledger data will appear here after the first chat or AI execution.
        </div>
      )}

      {/* ── Automations ───────────────────────────────────────────────── */}
      <SectionHeader title="Automation Health" />
      {automations ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <MetricCard
            label="Policies"
            value={automations.policies.total}
            sub={`${automations.policies.enabled} enabled`}
            color="#6366f1"
          />
          <MetricCard
            label="Budgets"
            value={automations.budgets.total}
            sub={`${automations.budgets.enabled} enabled`}
            color="#06b6d4"
          />
          <MetricCard
            label="Executions (24h)"
            value={automations.executions_last_24h}
            color="#f59e0b"
          />
          <div className="os-card">
            <div className="text-xs font-semibold uppercase tracking-wider text-aeon-fg-mute mb-2">
              Execution Status
            </div>
            <StatusBreakdown counts={automations.execution_statuses} />
          </div>
        </div>
      ) : (
        <div className="os-card mb-8 text-center py-8 text-aeon-fg-mute text-sm">
          No automation data available.
        </div>
      )}

      {/* ── Live incidents ───────────────────────────────────────────── */}
      <SectionHeader
        title="Recent Incidents"
        action={<span className="text-xs text-aeon-fg-mute">Auto-refreshes every 30s</span>}
      />
      <IncidentFeed deadLetters={deadLetters} executions={recentExecutions} />

      {/* ── Dead Letters ──────────────────────────────────────────────── */}
      <SectionHeader
        title="Dead Letter Queue"
        action={
          deadLetters && deadLetters.total > 0 ? (
            <span className="text-xs font-mono text-red-400">
              {deadLetters.total} failed
            </span>
          ) : undefined
        }
      />
      {deadLetters && deadLetters.recent.length > 0 ? (
        <div className="os-card mb-8 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/10 text-left text-xs uppercase tracking-wider text-aeon-fg-mute">
                <th className="pb-2 pr-4">Job ID</th>
                <th className="pb-2 pr-4">Attempts</th>
                <th className="pb-2 pr-4">Error</th>
                <th className="pb-2">Submitted</th>
              </tr>
            </thead>
            <tbody>
              {deadLetters.recent.map((entry, i) => (
                <tr key={i} className="border-b border-white/5">
                  <td className="py-2 pr-4 font-mono text-xs text-aeon-fg-soft">
                    {entry.job_id.slice(0, 12)}…
                  </td>
                  <td className="py-2 pr-4">
                    <span className="inline-flex items-center justify-center h-5 min-w-[20px] rounded-full bg-red-500/10 px-1.5 text-xs font-semibold text-red-400">
                      {entry.attempts}
                    </span>
                  </td>
                  <td className="py-2 pr-4 text-xs text-aeon-fg-soft max-w-xs truncate">
                    {entry.error || "—"}
                  </td>
                  <td className="py-2 text-xs text-aeon-fg-mute">
                    {timeAgo(entry.submitted_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="os-card mb-8 text-center py-6">
          <div className="text-2xl mb-2">✅</div>
          <div className="text-sm text-aeon-fg-soft">No dead letters — all jobs processed successfully.</div>
        </div>
      )}

      {/* ── Worker Queue ──────────────────────────────────────────────── */}
      <SectionHeader title="Worker Queue" />
      {worker ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
          <MetricCard
            label="Pending"
            value={worker.pending}
            color="#f59e0b"
          />
          <MetricCard
            label="Workers"
            value={worker.workers}
            color="#6366f1"
          />
          <MetricCard
            label="Tracked Jobs"
            value={worker.tracked_jobs}
            color="#06b6d4"
          />
          <div className="os-card">
            <div className="text-xs font-semibold uppercase tracking-wider text-aeon-fg-mute mb-2">
              Job Status
            </div>
            <StatusBreakdown counts={worker.status_counts} />
          </div>
        </div>
      ) : (
        <div className="os-card mb-8 text-center py-6 text-aeon-fg-mute text-sm">
          Worker data unavailable.
        </div>
      )}

      {/* ── Memory & Goals ────────────────────────────────────────────── */}
      {(snapshot?.memory || snapshot?.goals) && (
        <>
          <SectionHeader title="Agent State" />
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
            {snapshot.memory && (
              <>
                <MetricCard
                  label="Episodic Events"
                  value={formatNumber(snapshot.memory.episodic_events)}
                  color="#8b5cf6"
                />
                <MetricCard
                  label="Semantic Nodes"
                  value={formatNumber(snapshot.memory.semantic_nodes)}
                  color="#06b6d4"
                />
                <MetricCard
                  label="Semantic Edges"
                  value={formatNumber(snapshot.memory.semantic_edges)}
                  color="#10b981"
                />
                <MetricCard
                  label="Procedural Skills"
                  value={formatNumber(snapshot.memory.procedural_skills)}
                  color="#f59e0b"
                />
              </>
            )}
            {snapshot.goals && (
              <>
                <MetricCard
                  label="Open Goals"
                  value={snapshot.goals.open}
                  sub={`${snapshot.goals.total} total`}
                  color="#6366f1"
                />
              </>
            )}
          </div>
        </>
      )}

      {/* ── Quick links ───────────────────────────────────────────────── */}
      <div className="flex flex-wrap gap-3 mt-4 pb-8">
        <Link href="/admin" className="pill-btn">
          ← Admin Panel
        </Link>
        <Link href="/os/observability" className="pill-btn">
          Workspace Observability
        </Link>
        <Link href="/os/monitoring" className="pill-btn">
          Monitoring
        </Link>
        <Link href="/os/governance" className="pill-btn">
          Governance
        </Link>
      </div>
    </div>
  );
}
