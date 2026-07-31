"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

type DailyCount = {
  date: string;
  runs: number;
  completed: number;
  failed: number;
};

type TopRule = {
  rule_id: string;
  runs: number;
};

type MetricsResponse = {
  ok: boolean;
  workspace_id?: string;
  rule_id?: string;
  days: number;
  total_runs: number;
  completed_count: number;
  failed_count: number;
  throttled_count: number;
  pending_count: number;
  success_rate: number;
  failure_rate: number;
  average_runtime_ms: number;
  daily_counts: DailyCount[];
  top_rules?: TopRule[];
  error?: string;
};

function useFetch<T>(url: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!url) {
      setData(null);
      return;
    }
    let mounted = true;
    setLoading(true);
    setError(null);
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

function MiniBar({ data }: { data: { label: string; value: number; color?: string }[] }) {
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 8, height: 160, paddingTop: 10 }}>
      {data.map((d, i) => (
        <div
          key={i}
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 4,
            height: "100%",
            justifyContent: "flex-end",
          }}
        >
          <div
            style={{
              width: "100%",
              height: `${(d.value / max) * 100}%`,
              background: d.color || "var(--accent)",
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

export default function AutomationMetricsPage() {
  const [days, setDays] = useState(7);
  const [ruleId, setRuleId] = useState<string>("");
  const [topRules, setTopRules] = useState<TopRule[]>([]);

  const workspaceUrl = `/api/automations/metrics?days=${days}`;
  const ruleUrl = ruleId ? `/api/automations/${ruleId}/metrics?days=${days}` : null;

  const {
    data: workspaceMetrics,
    loading: workspaceLoading,
    error: workspaceError,
  } = useFetch<MetricsResponse>(workspaceUrl);
  const {
    data: ruleMetrics,
    loading: ruleLoading,
    error: ruleError,
  } = useFetch<MetricsResponse>(ruleUrl);

  const metrics = ruleId ? ruleMetrics : workspaceMetrics;
  const loading = workspaceLoading || (ruleId ? ruleLoading : false);
  const error = workspaceError || ruleError;

  useEffect(() => {
    if (workspaceMetrics?.top_rules) {
      setTopRules(workspaceMetrics.top_rules);
    }
  }, [workspaceMetrics]);

  const kpi = useMemo(() => {
    if (!metrics) return null;
    return [
      { label: "Total Runs", value: metrics.total_runs ?? 0, color: "#6366f1" },
      { label: "Completed", value: metrics.completed_count ?? 0, color: "#22c55e" },
      { label: "Failed", value: metrics.failed_count ?? 0, color: "#ef4444" },
      { label: "Throttled", value: metrics.throttled_count ?? 0, color: "#f59e0b" },
      { label: "Pending", value: metrics.pending_count ?? 0, color: "#94a3b8" },
    ];
  }, [metrics]);

  const dailyData = useMemo(() => {
    if (!metrics?.daily_counts) return [];
    return metrics.daily_counts.map((d) => ({
      label: d.date.slice(5),
      value: d.runs,
      color: "#6366f1",
    }));
  }, [metrics]);

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
            🤖 Automation Metrics
          </h1>
          <p className="dashboard-subtitle">
            Execution health, success rates, and daily trends for automation rules
          </p>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <Link href="/os" className="btn btn-sm">
            ← OS Launcher
          </Link>
        </div>
      </header>

      {/* Controls */}
      <section
        style={{
          display: "flex",
          gap: 16,
          alignItems: "flex-end",
          flexWrap: "wrap",
          marginBottom: 24,
        }}
      >
        <div>
          <label
            style={{
              display: "block",
              fontSize: "0.75rem",
              color: "var(--fg-mute)",
              marginBottom: 4,
            }}
          >
            Lookback Period
          </label>
          <select
            className="os-input"
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
          >
            <option value={1}>Last 24 hours</option>
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
        </div>
        <div>
          <label
            style={{
              display: "block",
              fontSize: "0.75rem",
              color: "var(--fg-mute)",
              marginBottom: 4,
            }}
          >
            Rule Filter (optional)
          </label>
          <input
            className="os-input"
            type="text"
            value={ruleId}
            onChange={(e) => setRuleId(e.target.value)}
            placeholder="Enter rule ID"
            style={{ minWidth: 240 }}
          />
        </div>
        {ruleId && (
          <button className="btn btn-sm" onClick={() => setRuleId("")}>
            Clear filter
          </button>
        )}
      </section>

      {error && <div className="module-alert danger">{error}</div>}

      {loading && !metrics && (
        <div style={{ color: "var(--fg-mute)", padding: 40, textAlign: "center" }}>
          Loading automation metrics…
        </div>
      )}

      {metrics && !metrics.ok && (
        <div className="module-alert danger">{metrics.error || "Failed to load metrics"}</div>
      )}

      {metrics?.ok && (
        <>
          {/* KPI Cards */}
          <section
            className="os-grid"
            style={{ gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}
          >
            {kpi?.map((item) => (
              <Card key={item.label} title={item.label}>
                <div style={{ fontSize: "2rem", fontWeight: 700, color: item.color }}>
                  {item.value.toLocaleString()}
                </div>
              </Card>
            ))}
            <Card title="Success Rate">
              <div style={{ fontSize: "2rem", fontWeight: 700, color: "#22c55e" }}>
                {(metrics.success_rate ?? 0).toFixed(1)}%
              </div>
            </Card>
            <Card title="Failure Rate">
              <div style={{ fontSize: "2rem", fontWeight: 700, color: "#ef4444" }}>
                {(metrics.failure_rate ?? 0).toFixed(1)}%
              </div>
            </Card>
            <Card title="Avg Runtime">
              <div style={{ fontSize: "2rem", fontWeight: 700, color: "#6366f1" }}>
                {(metrics.average_runtime_ms ?? 0).toFixed(0)} ms
              </div>
            </Card>
          </section>

          {/* Charts & Top Rules */}
          <section
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
              gap: 24,
              marginTop: 24,
            }}
          >
            <Card title="Daily Runs" className="chart-card">
              {dailyData.length > 0 ? (
                <MiniBar data={dailyData} />
              ) : (
                <div style={{ color: "var(--fg-mute)", padding: 20, textAlign: "center" }}>
                  No daily data yet
                </div>
              )}
            </Card>

            <Card title="Status Breakdown" className="chart-card">
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                <div>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      fontSize: "0.85rem",
                      marginBottom: 4,
                    }}
                  >
                    <span>Completed</span>
                    <span>{metrics.completed_count}</span>
                  </div>
                  <div
                    style={{
                      height: 8,
                      background: "var(--bg-elevated)",
                      borderRadius: 4,
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        width: `${metrics.total_runs ? (metrics.completed_count / metrics.total_runs) * 100 : 0}%`,
                        height: "100%",
                        background: "#22c55e",
                        borderRadius: 4,
                      }}
                    />
                  </div>
                </div>
                <div>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      fontSize: "0.85rem",
                      marginBottom: 4,
                    }}
                  >
                    <span>Failed</span>
                    <span>{metrics.failed_count}</span>
                  </div>
                  <div
                    style={{
                      height: 8,
                      background: "var(--bg-elevated)",
                      borderRadius: 4,
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        width: `${metrics.total_runs ? (metrics.failed_count / metrics.total_runs) * 100 : 0}%`,
                        height: "100%",
                        background: "#ef4444",
                        borderRadius: 4,
                      }}
                    />
                  </div>
                </div>
                <div>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      fontSize: "0.85rem",
                      marginBottom: 4,
                    }}
                  >
                    <span>Throttled</span>
                    <span>{metrics.throttled_count}</span>
                  </div>
                  <div
                    style={{
                      height: 8,
                      background: "var(--bg-elevated)",
                      borderRadius: 4,
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        width: `${metrics.total_runs ? (metrics.throttled_count / metrics.total_runs) * 100 : 0}%`,
                        height: "100%",
                        background: "#f59e0b",
                        borderRadius: 4,
                      }}
                    />
                  </div>
                </div>
                <div>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      fontSize: "0.85rem",
                      marginBottom: 4,
                    }}
                  >
                    <span>Pending Approval</span>
                    <span>{metrics.pending_count}</span>
                  </div>
                  <div
                    style={{
                      height: 8,
                      background: "var(--bg-elevated)",
                      borderRadius: 4,
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        width: `${metrics.total_runs ? (metrics.pending_count / metrics.total_runs) * 100 : 0}%`,
                        height: "100%",
                        background: "#94a3b8",
                        borderRadius: 4,
                      }}
                    />
                  </div>
                </div>
              </div>
            </Card>

            <Card title="Top Rules" className="chart-card">
              {topRules.length > 0 ? (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {topRules.map((rule) => (
                    <div
                      key={rule.rule_id}
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        padding: "10px 12px",
                        background: "var(--bg-elevated)",
                        borderRadius: 8,
                        cursor: "pointer",
                      }}
                      onClick={() => setRuleId(rule.rule_id)}
                    >
                      <span style={{ fontSize: "0.85rem", fontFamily: "monospace" }}>
                        {rule.rule_id}
                      </span>
                      <span style={{ fontSize: "0.85rem", color: "var(--fg-mute)" }}>
                        {rule.runs} runs
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ color: "var(--fg-mute)", padding: 20, textAlign: "center" }}>
                  No rule data yet
                </div>
              )}
            </Card>
          </section>
        </>
      )}
    </div>
  );
}
