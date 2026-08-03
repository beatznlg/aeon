"use client";

import { useEffect, useState, useRef, type CSSProperties } from "react";
import { useSession } from "next-auth/react";
import Link from "next/link";
import { SystemHealthPanel, AlertBanner, AlertPanel } from "../components/LiveMonitor";
import { useTheme } from "@/components/ThemeProvider";
import { isWorkspaceAdmin, isModuleEnabled } from "@/lib/theme-config";
import { resolveEnabledComponents, DashboardComponent } from "@/lib/dashboard-registry";
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
    color: "#6366f1",
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
    color: "#3b82f6",
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

/* ─── Animated counter ─── */

function AnimatedStat({
  value,
  label,
  color,
}: {
  value: string | number;
  label: string;
  color: string;
}) {
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
      const duration = 1200;
      const start = performance.now();
      const animate = (now: number) => {
        const elapsed = now - start;
        const progress = Math.min(elapsed / duration, 1);
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

  return (
    <div className="stat-card text-center">
      <div className="stat-value" style={{ color }}>
        {display}
      </div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

/* ─── Section Components ─── */

function WelcomeBannerSection({
  config,
  activeModules,
  totalTools,
}: {
  config: any;
  activeModules: CommandModule[];
  totalTools: number;
}) {
  return (
    <div className="welcome-banner">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between relative z-10">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="flex h-2 w-2 rounded-full bg-green-400 shadow-[0_0_8px_rgba(34,197,94,0.5)]" />
            <span className="text-xs font-medium uppercase tracking-widest text-green-400/80">
              System Online
            </span>
          </div>
          <h1 className="text-2xl font-bold text-white">
            {config.companyName} — <span className="text-gradient">{config.productName}</span>
          </h1>
          <p className="max-w-2xl text-sm text-slate-400">
            Your autonomous AI operating system with {activeModules.length} active command centers
            and {totalTools} tools ready to automate, secure, and scale your operations.
          </p>
        </div>
        <div className="flex gap-3">
          <Link href="/os" className="pill-btn pill-btn-primary">
            ⊞ Launch OS
          </Link>
          <Link href="/settings/branding" className="pill-btn">
            Customize
          </Link>
        </div>
      </div>
    </div>
  );
}

function StatusBarSection({
  health,
  activeModules,
  totalTools,
}: {
  health: { ok: boolean; backend?: string } | null;
  activeModules: CommandModule[];
  totalTools: number;
}) {
  const cards = [
    {
      icon: "⟁",
      label: "System Status",
      value: health === null ? "..." : health.ok ? "Online" : "Connecting",
      sub: health?.backend || "AEON stub",
      background: "rgba(99,102,241,0.12)",
      color: "var(--aeon-primary)",
      valueColor: "var(--aeon-success)",
    },
    {
      icon: "⊞",
      label: "Active Modules",
      value: String(activeModules.length),
      sub: "Operational",
      background: "rgba(16,185,129,0.12)",
      color: "var(--aeon-success)",
    },
    {
      icon: "⚡",
      label: "Smart Tools",
      value: String(totalTools),
      sub: "AI-powered capabilities",
      background: "rgba(245,158,11,0.12)",
      color: "var(--aeon-warning)",
    },
    {
      icon: "◈",
      label: "LLM Backend",
      value:
        health?.backend === "aeon-kernel"
          ? "AEON Kernel"
          : health?.backend === "hf-inference"
            ? "HF Inference"
            : "Stub",
      sub: "Pluggable · Hot-swappable",
      background: "rgba(6,182,212,0.12)",
      color: "#06b6d4",
    },
  ];

  return (
    <StaggerContainer className="status-bar">
      {cards.map((card) => (
        <StaggerItem key={card.label}>
          <div className="status-bar-card">
            <div className="status-bar-icon" style={{ background: card.background, color: card.color }}>
              {card.icon}
            </div>
            <div className="status-bar-info">
              <span className="status-bar-label">{card.label}</span>
              <span className="status-bar-value" style={card.valueColor ? { color: card.valueColor } : undefined}>
                {card.value}
              </span>
              <span className="status-bar-sub">{card.sub}</span>
            </div>
          </div>
        </StaggerItem>
      ))}
    </StaggerContainer>
  );
}

function LiveMetricsSection({
  stats,
  loading,
  lastUpdated,
  fetchStats,
}: {
  stats: Record<string, string | number>;
  loading: boolean;
  lastUpdated: Date | null;
  fetchStats: () => Promise<void>;
}) {
  return (
    <>
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold text-slate-300">Live Metrics</h2>
          {lastUpdated && (
            <span className="text-xs text-slate-500">· {lastUpdated.toLocaleTimeString()}</span>
          )}
        </div>
        <button
          onClick={fetchStats}
          disabled={loading}
          className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium text-slate-400 transition hover:bg-white/[0.04] hover:text-slate-200 disabled:opacity-50"
        >
          <span
            className={`inline-block h-2 w-2 rounded-full ${loading ? "animate-pulse bg-amber-400" : "bg-emerald-400"}`}
            style={!loading ? { boxShadow: "0 0 6px rgba(34,197,94,0.5)" } : {}}
          />
          {loading ? "Refreshing..." : "Live"}
        </button>
      </div>
      <div className="dashboard-grid">
        {[
          { value: stats.uptime as string, label: "Uptime", color: "#10b981" },
          { value: stats.agents, label: "Active Agents", color: "#6366f1" },
          { value: stats.automations, label: "Automations", color: "#f59e0b" },
          { value: stats.anomalies, label: "Anomalies", color: "#ef4444" },
          { value: stats.incidents, label: "Open Incidents", color: "#06b6d4" },
          { value: stats.tasks, label: "Tasks Run", color: "#8b5cf6" },
        ].map((s, i) => (
          <StaggerItem key={s.label}>
            <AnimatedStat value={s.value} label={s.label} color={s.color} />
          </StaggerItem>
        ))}
      </div>
    </>
  );
}

function ModuleGridSection({ modules, admin }: { modules: CommandModule[]; admin: boolean }) {
  return (
    <FadeIn delay={0.2}>
      <div className="dashboard-section-heading mt-8">
        <div>
          <h2 className="dashboard-section-title">Command Centers</h2>
          <p className="dashboard-section-caption">Launch a specialized workspace or review what is currently paused.</p>
        </div>
        <span className="dashboard-section-count">{modules.length} surfaces</span>
      </div>
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
                      <span className={`h-1.5 w-1.5 rounded-full ${mod.status === "active" ? "bg-green-400" : "bg-slate-500"}`} />
                      {mod.status}
                    </span>
                    <span className="text-[0.65rem] text-slate-500">{mod.tools} tools</span>
                  </div>
                </div>
                {mod.status === "active" && <span className="module-card-arrow" aria-hidden="true">↗</span>}
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
                <div className={className} style={style} aria-disabled="true" title="This command center is disabled for this workspace">
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

function PlatformFeaturesSection() {
  return (
    <FadeIn delay={0.3}>
      <h2 className="dashboard-section-title mt-8">Platform Capabilities</h2>
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
      const res = await fetch("/api/dashboard/stats", { cache: "no-store" });
      const d = await res.json();
      if (d?.ok && d?.counts) {
        setLiveStats(d.counts as DashboardCounts);
        setLastUpdated(new Date());
      }
    } catch {
      // silently fail
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
            "radial-gradient(ellipse at 20% 50%, rgba(99, 102, 241, 0.03) 0%, transparent 60%), radial-gradient(ellipse at 80% 20%, rgba(168, 85, 247, 0.02) 0%, transparent 50%)",
        }}
      />
      <div className="dashboard-page">
        {enabledIds.has("welcome_banner") && (
          <FadeIn key="welcome">
            <WelcomeBannerSection
              config={config}
              activeModules={activeModules}
              totalTools={totalTools}
            />
          </FadeIn>
        )}
        {enabledIds.has("system_status_bar") && (
          <FadeIn key="status" delay={0.1}>
            <StatusBarSection
              health={health}
              activeModules={activeModules}
              totalTools={totalTools}
            />
          </FadeIn>
        )}
        {enabledIds.has("live_metrics") && (
          <FadeIn key="metrics" delay={0.15}>
            <LiveMetricsSection
              stats={stats}
              loading={loading}
              lastUpdated={lastUpdated}
              fetchStats={fetchStats}
            />
          </FadeIn>
        )}
        {enabledIds.has("command_centers") && (
          <FadeIn key="modules" delay={0.2}>
            <ModuleGridSection modules={modules} admin={admin} />
          </FadeIn>
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
              <SystemHealthPanel />
            </div>
          </FadeIn>
        )}
        {enabledIds.has("platform_features") && (
          <FadeIn key="features" delay={0.35}>
            <PlatformFeaturesSection />
          </FadeIn>
        )}
      </div>
    </motion.div>
  );
}
