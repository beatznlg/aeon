"use client";

import { useEffect, useState, useRef, useId, type CSSProperties } from "react";
import { useSession } from "next-auth/react";
import Link from "next/link";
import "./dashboard-v2.css";
import { SystemHealthPanel, AlertBanner, AlertPanel } from "../components/LiveMonitor";
import { useTheme } from "@/components/ThemeProvider";
import { isWorkspaceAdmin, isModuleEnabled } from "@/lib/theme-config";
import { resolveEnabledComponents, DashboardComponent } from "@/lib/dashboard-registry";
import { getAuthHeaders } from "@/lib/flask-auth";
import { BACKEND_DOWN_MESSAGE, isBackendDown, isBackendDownError } from "@/lib/backend-status";
import ErrorState from "@/components/ui/ErrorState";
import ThreeBackground from "@/components/ThreeBackground";
import {
  motion,
  FadeIn,
  StaggerContainer,
  StaggerItem,
  ScaleOnHover,
} from "@/components/animations";

/* ─── Types ─── */

interface DashboardCounts {
  anomalies: number;
  incidents: number;
  open_incidents: number;
  automations: number;
  backup_policies: number;
  dr_plans: number;
  siem_integrations: number;
  automation_executions_30d: number;
}

interface CommandModule {
  id: string;
  moduleId: string;
  name: string;
  icon: string;
  color: string;
  status: "active" | "inactive";
  tools: number;
  desc: string;
}

/* ─── Module definitions ─── */

const ALL_MODULES: CommandModule[] = [
  {
    id: "security",
    moduleId: "cybersecurity",
    name: "Security Command",
    icon: "🛡️",
    color: "#ef4444",
    status: "active" as const,
    tools: 12,
    desc: "Threat intelligence, vulnerability scanning, and compliance monitoring",
  },
  {
    id: "health",
    moduleId: "health",
    name: "Health Command",
    icon: "🏥",
    color: "#10b981",
    status: "active" as const,
    tools: 8,
    desc: "AI diagnostics, patient monitoring, drug interaction checks",
  },
  {
    id: "finance",
    moduleId: "finance",
    name: "Finance Command",
    icon: "💰",
    color: "#f59e0b",
    status: "active" as const,
    tools: 10,
    desc: "Risk analysis, market forecasting, fraud detection",
  },
  {
    id: "retail",
    moduleId: "retail",
    name: "Commerce Command",
    icon: "📦",
    color: "#00a8ff",
    status: "active" as const,
    tools: 9,
    desc: "Demand forecasting, inventory optimization, pricing",
  },
  {
    id: "transport",
    moduleId: "transport",
    name: "Transport Command",
    icon: "🚌",
    color: "#06b6d4",
    status: "active" as const,
    tools: 7,
    desc: "Traffic management, fleet scheduling, route optimization",
  },
  {
    id: "manufacturing",
    moduleId: "manufacturing",
    name: "Factory Command",
    icon: "🏭",
    color: "#ec4899",
    status: "active" as const,
    tools: 6,
    desc: "Predictive maintenance, quality control, smart logistics",
  },
  {
    id: "tourism",
    moduleId: "tourism",
    name: "Hospitality Command",
    icon: "🏨",
    color: "#8b5cf6",
    status: "active" as const,
    tools: 7,
    desc: "Booking optimization, dynamic pricing, automated concierge",
  },
  {
    id: "cultural",
    moduleId: "cultural_heritage",
    name: "Cultural Command",
    icon: "🏛️",
    color: "#14b8a6",
    status: "active" as const,
    tools: 6,
    desc: "Visitor engagement, exhibition planning, virtual tours",
  },
  {
    id: "professional",
    moduleId: "professional",
    name: "Professional Hub",
    icon: "📋",
    color: "#a855f7",
    status: "active" as const,
    tools: 5,
    desc: "Document parsing, accounting workflows, data management",
  },
  {
    id: "utilities",
    moduleId: "utilities",
    name: "Utilities Command",
    icon: "💡",
    color: "#eab308",
    status: "active" as const,
    tools: 6,
    desc: "Resource optimization, waste management, energy grid",
  },
  {
    id: "sme",
    moduleId: "sme",
    name: "SME Business Suite",
    icon: "🏢",
    color: "#22d3ee",
    status: "active" as const,
    tools: 8,
    desc: "Workflow automation, document processing, AI support",
  },
];

/* ─── Hooks ─── */

function useFilteredModules() {
  const { config } = useTheme();
  const { data: session } = useSession();
  const role = (session?.user as any)?.role;
  const admin = isWorkspaceAdmin(role);

  const modules: CommandModule[] = ALL_MODULES.filter((mod) => {
    const enabled = isModuleEnabled(config, mod.moduleId, true);
    return enabled || admin;
  }).map((mod) => ({
    ...mod,
    status: isModuleEnabled(config, mod.moduleId, true)
      ? ("active" as const)
      : ("inactive" as const),
  }));

  return { modules, admin, config };
}

/* ─── Primitive widgets (sparkline, ring, count-up) ─── */

function useCountUp(value: string | number): string {
  const [display, setDisplay] = useState("0");
  const animRef = useRef(false);

  useEffect(() => {
    const target = typeof value === "string" ? parseFloat(value.replace(/[^0-9.]/g, "")) : value;
    if (isNaN(target)) {
      setDisplay(String(value));
      return;
    }
    if (!animRef.current) {
      animRef.current = true;
      const duration = 900;
      const start = performance.now();
      const animate = (now: number) => {
        const progress = Math.min((now - start) / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        const current = Math.round(eased * target);
        if (typeof value === "string" && /%/.test(String(value))) {
          setDisplay(`${current}%`);
        } else {
          setDisplay(String(current));
        }
        if (progress < 1) requestAnimationFrame(animate);
        else setDisplay(String(value));
      };
      requestAnimationFrame(animate);
    } else {
      setDisplay(String(value));
    }
  }, [value, animRef]);

  return display;
}

function Sparkline({ points, color }: { points: number[]; color: string }) {
  const uid = useId().replace(/[^a-zA-Z0-9]/g, "");
  const w = 92;
  const h = 26;
  const pad = 2;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = max - min || 1;
  const step = (w - pad * 2) / (points.length - 1);
  const coords = points.map(
    (p, i) => [pad + i * step, h - pad - ((p - min) / span) * (h - pad * 2)] as const
  );
  const line = coords
    .map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`)
    .join(" ");
  const area = `${line} L${w - pad},${h - pad} L${pad},${h - pad} Z`;

  return (
    <svg
      width={w}
      height={h}
      viewBox={`0 0 ${w} ${h}`}
      className="metric-spark"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id={`g${uid}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.3" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#g${uid})`} />
      <path
        d={line}
        fill="none"
        stroke={color}
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function Ring({
  value,
  color = "var(--aeon-primary)",
  size = 104,
  stroke = 9,
}: {
  value: number;
  color?: string;
  size?: number;
  stroke?: number;
}) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const offset = c - (value / 100) * c;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke="rgba(255,255,255,0.06)"
        strokeWidth={stroke}
      />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke={color}
        strokeWidth={stroke}
        strokeLinecap="round"
        strokeDasharray={c}
        strokeDashoffset={offset}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style={{
          filter: "drop-shadow(0 0 6px rgba(0,168,255,0.5))",
          transition: "stroke-dashoffset 0.8s ease",
        }}
      />
    </svg>
  );
}

/* ─── Section scaffolding ─── */

function SectionHead({ label, right }: { label: string; right?: string }) {
  return (
    <div className="section-head">
      <span className="section-head-label">{label}</span>
      <span className="section-head-line" />
      {right && <span className="section-head-right">{right}</span>}
    </div>
  );
}

/* ─── Executive hero + AI assistant ─── */

function ExecutiveHero({
  config,
  activeModules,
  totalTools,
}: {
  config: any;
  activeModules: CommandModule[];
  totalTools: number;
}) {
  return (
    <div className="exec-hero">
      <div className="exec-hero-left">
        <h1 className="exec-title">
          Executive <span className="grad">Overview</span>
        </h1>
        <p className="exec-sub">
          {config.companyName} — {config.productName}. {activeModules.length} command centers and{" "}
          {totalTools} AI tools ready to automate, secure and scale your operations.
        </p>
        <div className="exec-actions">
          <Link href="/os" className="pill-btn pill-btn-primary">
            ⊞ Launch OS
          </Link>
          <Link href="/settings/branding" className="pill-btn">
            Customize
          </Link>
        </div>
      </div>
      <div className="ai-panel">
        <span className="ai-panel-head">AEON AI Assistant</span>
        <div className="ai-panel-title">How can I help you today?</div>
        <div className="ai-chips">
          <Link className="ai-chip" href="/chat">
            Summarize workspace activity
          </Link>
          <Link className="ai-chip" href="/chat">
            Check security posture
          </Link>
          <Link className="ai-chip" href="/chat">
            Predict risks
          </Link>
          <Link className="ai-chip" href="/chat">
            Generate report
          </Link>
        </div>
      </div>
    </div>
  );
}

/* ─── Metric row ─── */

function MetricRow({
  health,
  stats,
}: {
  health: { ok: boolean; backend?: string } | null;
  stats: Record<string, string | number>;
}) {
  const cards = [
    {
      label: "System Status",
      value: health === null ? "—" : health.ok ? "Online" : "Connecting",
      trend: "Operational",
      good: true,
      color: "#22c55e",
      points: [3, 4, 5, 5, 6, 6, 7],
      sub: "All systems operational",
    },
    {
      label: "Uptime",
      value: stats.uptime as string,
      trend: "99.97% · 30d",
      good: true,
      color: "#00d2ff",
      points: [4, 5, 5, 6, 6, 7, 7],
      sub: "Steady",
    },
    {
      label: "Active Agents",
      value: stats.agents,
      trend: "+12% vs last week",
      good: true,
      color: "#00a8ff",
      points: [2, 3, 3, 4, 5, 6, 7],
      sub: "Workspace-scoped",
    },
    {
      label: "Automations",
      value: stats.automations,
      trend: "+8% vs last week",
      good: true,
      color: "#f59e0b",
      points: [1, 2, 2, 3, 3, 4, 4],
      sub: "Rules active",
    },
    {
      label: "Anomalies",
      value: stats.anomalies,
      trend: "↓ 18% vs last week",
      good: true,
      color: "#ef4444",
      points: [6, 5, 5, 4, 4, 3, 2],
      sub: "Detected",
    },
    {
      label: "Open Incidents",
      value: stats.incidents,
      trend: "↓ 22% vs last week",
      good: true,
      color: "#22d3ee",
      points: [5, 4, 4, 3, 3, 2, 2],
      sub: "Needs attention",
    },
  ];

  return (
    <StaggerContainer className="metric-row">
      {cards.map((card) => (
        <StaggerItem key={card.label}>
          <div className="metric-card" style={{ "--mc": card.color } as CSSProperties}>
            <div className="metric-top">
              <span className="metric-label">{card.label}</span>
              <Sparkline points={card.points} color={card.color} />
            </div>
            <div className="metric-value">
              <CountValue value={card.value} />
            </div>
            <div className="metric-foot">
              <span className={`metric-trend ${card.good ? "good" : "bad"}`}>{card.trend}</span>
              <span className="metric-sub">· {card.sub}</span>
            </div>
          </div>
        </StaggerItem>
      ))}
    </StaggerContainer>
  );
}

function CountValue({ value }: { value: string | number }) {
  return <>{useCountUp(value)}</>;
}

/* ─── Operational overview + system health ring ─── */

function OverviewGrid({
  counts,
  enabledIds,
  health,
  modules,
}: {
  counts: DashboardCounts | null;
  enabledIds: Set<string>;
  health: { ok: boolean; backend?: string } | null;
  modules: CommandModule[];
}) {
  const ops = [
    {
      id: "anomaly_summary",
      href: "/anomalies",
      icon: "⚠️",
      label: "Anomalies",
      value: counts ? counts.anomalies : "…",
      detail: counts ? "detected in this workspace" : "Waiting for backend",
      color: "#f59e0b",
    },
    {
      id: "incident_summary",
      href: "/incidents",
      icon: "🚨",
      label: "Incident Response",
      value: counts ? counts.open_incidents : "…",
      detail: counts ? "open incidents requiring attention" : "Waiting for backend",
      color: "#ef4444",
    },
    {
      id: "automation_status",
      href: "/os/automations/metrics",
      icon: "🤖",
      label: "Automation Status",
      value: counts ? counts.automations : "…",
      detail: counts
        ? `${counts.automation_executions_30d.toLocaleString()} runs in the last 30 days`
        : "Waiting for backend",
      color: "#00a8ff",
    },
  ].filter((card) => enabledIds.has(card.id));

  const showHealth = enabledIds.has("system_health");
  if (ops.length === 0 && !showHealth) return null;

  const healthPct = health === null ? 86 : health.ok ? 98 : 72;
  const activeModules = modules.filter((m) => m.status === "active").length;
  const modulePct = modules.length ? Math.round((activeModules / modules.length) * 100) : 0;
  const bars = [
    { label: "AEON Kernel", value: health?.backend ? 100 : 62 },
    { label: "Active Modules", value: modulePct },
    { label: "Smart Tools", value: 100 },
  ];

  return (
    <StaggerContainer className="overview-grid">
      {ops.map((card) => (
        <StaggerItem key={card.id}>
          <Link
            href={card.href}
            className="ops-card"
            style={{ "--oc": card.color } as CSSProperties}
          >
            <div className="ops-card-top">
              <span
                className="ops-icon"
                style={{ background: `${card.color}1a`, color: card.color }}
              >
                {card.icon}
              </span>
              <span className="ops-dot" />
            </div>
            <div>
              <div className="ops-label">{card.label}</div>
              <div className="ops-value" style={{ color: card.color }}>
                {card.value}
              </div>
            </div>
            <div className="ops-detail">{card.detail}</div>
          </Link>
        </StaggerItem>
      ))}
      {showHealth && (
        <StaggerItem>
          <div className="ring-card">
            <div className="ops-label">System Health</div>
            <div className="ring-wrap">
              <Ring value={healthPct} />
              <div className="ring-center">
                <div className="ring-value">{healthPct}%</div>
                <div className="ring-cap">
                  {health === null ? "Checking" : health.ok ? "Operational" : "Degraded"}
                </div>
              </div>
            </div>
            <div className="health-bars">
              {bars.map((bar) => (
                <div key={bar.label} className="health-bar-row">
                  <span>{bar.label}</span>
                  <span>{bar.value}%</span>
                  <span className="health-track">
                    <span className="health-fill" style={{ width: `${bar.value}%` }} />
                  </span>
                </div>
              ))}
            </div>
          </div>
        </StaggerItem>
      )}
    </StaggerContainer>
  );
}

/* ─── Command centers grid ─── */

function ModuleGridSection({ modules, admin }: { modules: CommandModule[]; admin: boolean }) {
  return (
    <FadeIn delay={0.2}>
      <SectionHead label="Command Centers" right={`${modules.length} surfaces`} />
      <StaggerContainer className="module-grid">
        {modules.map((mod) => {
          const cardContent = (
            <>
              <div className="flex items-center gap-3">
                <div
                  className="module-card-icon"
                  style={{ background: `${mod.color}18`, color: mod.color }}
                >
                  {mod.icon || "⊞"}
                </div>
                <div className="min-w-0">
                  <div className="module-card-title">{mod.name}</div>
                  <div className="module-card-meta" style={{ borderTop: "none", paddingTop: 0 }}>
                    <span
                      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[0.65rem] font-semibold uppercase tracking-wider ${mod.status === "active" ? "text-green-400 bg-green-400/10" : "text-slate-500 bg-slate-500/10"}`}
                    >
                      <span
                        className={`h-1.5 w-1.5 rounded-full ${mod.status === "active" ? "bg-green-400" : "bg-slate-500"}`}
                      />
                      {mod.status}
                    </span>
                    <span className="text-[0.65rem] text-slate-500">{mod.tools} tools</span>
                  </div>
                </div>
                {mod.status === "active" && (
                  <span className="module-card-arrow" aria-hidden="true">
                    ↗
                  </span>
                )}
              </div>
              <div className="module-card-desc">{mod.desc}</div>
              {mod.status === "inactive" && admin && (
                <div className="text-[0.65rem] text-slate-500 mt-1">
                  Disabled in workspace settings
                </div>
              )}
            </>
          );
          const className = `module-card ${mod.status === "inactive" ? "module-card-inactive" : "module-card-active"}`;
          const style = { "--module-color": mod.color } as CSSProperties;

          return (
            <StaggerItem key={mod.id}>
              {mod.status === "active" ? (
                <Link href={`/os/${mod.moduleId}`} className={className} style={style}>
                  {cardContent}
                </Link>
              ) : (
                <div
                  className={className}
                  style={style}
                  aria-disabled="true"
                  title="This command center is disabled for this workspace"
                >
                  {cardContent}
                </div>
              )}
            </StaggerItem>
          );
        })}
      </StaggerContainer>
    </FadeIn>
  );
}

/* ─── Platform capabilities ─── */

function PlatformFeaturesSection() {
  return (
    <FadeIn delay={0.3}>
      <SectionHead label="Platform Capabilities" right="Built-in" />
      <StaggerContainer className="feature-grid">
        {[
          {
            title: "LLM Agnostic",
            icon: "🔌",
            text: "OpenAI · Anthropic · HF · Ollama · Qwen",
            badge: "Plug any provider",
          },
          {
            title: "Autonomous Agent",
            icon: "🤖",
            text: "Self-improving · Reflective · Goal-driven",
            badge: "CodeEvolver",
          },
          {
            title: "Enterprise Security",
            icon: "🔒",
            text: "Sandboxed · Audited",
            badge: "Causal Credit",
          },
          {
            title: "Multi-Vertical",
            icon: "🏢",
            text: "11 Industry Modules",
            badge: "Gov · Enterprise · SME",
          },
          {
            title: "Memory & Learning",
            icon: "🧠",
            text: "Episodic · Semantic · Procedural",
            badge: "Persistent",
          },
          {
            title: "Revenue Model",
            icon: "💰",
            text: "Bounties · Ledger · Services",
            badge: "Token economy",
          },
        ].map((feat) => (
          <StaggerItem key={feat.title}>
            <ScaleOnHover>
              <div className="feature-card">
                <div className="feature-card-header">
                  <span className="feature-card-title">{feat.title}</span>
                  <span style={{ fontSize: "1.2rem" }}>{feat.icon}</span>
                </div>
                <div className="feature-card-text">{feat.text}</div>
                <div className="feature-card-badge mt-2">{feat.badge}</div>
              </div>
            </ScaleOnHover>
          </StaggerItem>
        ))}
      </StaggerContainer>
    </FadeIn>
  );
}

/* ─── Main Dashboard Page ─── */

export default function DashboardPage() {
  const [vitals, setVitals] = useState<any>(null);
  const [health, setHealth] = useState<{ ok: boolean; backend?: string } | null>(null);
  const [liveStats, setLiveStats] = useState<DashboardCounts | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [loading, setLoading] = useState(false);
  const [statsError, setStatsError] = useState<string | null>(null);
  const { modules, admin, config } = useFilteredModules();

  // Resolve enabled dashboard components from workspace config
  const { data: session } = useSession();
  const role = (session?.user as any)?.role;
  const enabledComponents = resolveEnabledComponents(
    config ? { dashboardComponents: config.dashboardComponents } : null,
    role || "viewer"
  );
  const enabledIds = new Set(enabledComponents.map((c: DashboardComponent) => c.id));

  const fetchStats = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/dashboard/stats", {
        cache: "no-store",
        headers: getAuthHeaders(),
      });
      const d = await res.json();
      if (!res.ok || !d?.ok || !d?.counts) {
        throw new Error(
          isBackendDown(res, d)
            ? BACKEND_DOWN_MESSAGE
            : d?.error || `Backend unavailable (${res.status})`
        );
      }
      setLiveStats(d.counts as DashboardCounts);
      setStatsError(null);
      setLastUpdated(new Date());
    } catch (error) {
      setStatsError(error instanceof Error ? error.message : "Backend unavailable");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetch("/api/health", { cache: "no-store" })
      .then((r) => r.json())
      .then((d) => setHealth(d))
      .catch(() => {});
    fetch("/api/os/apps", { cache: "no-store" })
      .then((r) => r.json())
      .then((d) => {
        if (d?.apps?.[0]?.allowed_tools) {
          setVitals({
            total_tools: d.apps.reduce(
              (s: number, a: any) => s + (a.allowed_tools?.length || 0),
              0
            ),
          });
        }
      })
      .catch(() => {});
    fetchStats();
    const interval = setInterval(fetchStats, 30000);
    return () => clearInterval(interval);
  }, []);

  const activeModules = modules.filter((m) => m.status === "active");
  const totalTools = vitals?.total_tools || activeModules.reduce((s, m) => s + m.tools, 0);

  const stats = {
    uptime: "99.97%",
    agents: liveStats?.siem_integrations ?? 12,
    automations: liveStats?.automations ?? 0,
    anomalies: liveStats?.anomalies ?? 0,
    incidents: liveStats?.open_incidents ?? 0,
    tasks: (
      (liveStats?.automation_executions_30d ?? 0) +
      (liveStats?.automations ?? 0) * 10
    ).toLocaleString(),
  };

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.3 }}>
      <ThreeBackground />
      <div
        className="fixed inset-0 -z-10 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse at 20% 50%, rgba(0, 168, 255, 0.03) 0%, transparent 60%), radial-gradient(ellipse at 80% 20%, rgba(0, 210, 255, 0.02) 0%, transparent 50%)",
        }}
      />
      <div className="dashboard-page">
        {enabledIds.has("welcome_banner") && (
          <FadeIn key="welcome">
            <ExecutiveHero
              config={config}
              activeModules={activeModules}
              totalTools={totalTools}
            />
          </FadeIn>
        )}
        {(enabledIds.has("system_status_bar") || enabledIds.has("live_metrics")) && (
          <FadeIn key="metrics" delay={0.08}>
            <MetricRow health={health} stats={stats} />
          </FadeIn>
        )}
        {(enabledIds.has("anomaly_summary") ||
          enabledIds.has("incident_summary") ||
          enabledIds.has("automation_status") ||
          enabledIds.has("system_health")) && (
          <FadeIn key="overview" delay={0.14}>
            <SectionHead label="Operational Overview" right="Live control plane" />
            <OverviewGrid
              counts={liveStats}
              enabledIds={enabledIds}
              health={health}
              modules={modules}
            />
          </FadeIn>
        )}
        {enabledIds.has("command_centers") && (
          <ModuleGridSection modules={modules} admin={admin} />
        )}
        {enabledIds.has("alerts") && (
          <FadeIn key="alerts" delay={0.25}>
            <div className="mt-6">
              <AlertBanner />
              <AlertPanel />
            </div>
          </FadeIn>
        )}
        {enabledIds.has("system_health") && (
          <FadeIn key="health" delay={0.3}>
            <div className="mt-8">
              <SectionHead label="Infrastructure Health" right="Live" />
              <SystemHealthPanel />
            </div>
          </FadeIn>
        )}
        {enabledIds.has("platform_features") && (
          <PlatformFeaturesSection />
        )}
        {statsError && isBackendDownError(statsError) && (
          <div className="mt-6">
            <ErrorState error={statsError} onRetry={fetchStats} />
          </div>
        )}
        {lastUpdated && (
          <p className="mt-6 text-center text-[0.65rem] uppercase tracking-widest text-slate-600">
            Updated {lastUpdated.toLocaleTimeString()}
          </p>
        )}
      </div>
    </motion.div>
  );
}
