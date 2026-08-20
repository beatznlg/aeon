"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getAuthHeaders } from "@/lib/flask-auth";
import type { DashboardData } from "../../../components/AeonOSDashboard";
import {
  CyberSecurityDashboard,
  RetailDashboard,
  ManufacturingDashboard,
  ProfessionalDashboard,
  TourismDashboard,
  HealthDashboard,
  TransportDashboard,
  FinanceDashboard,
  CulturalHeritageDashboard,
  UtilitiesDashboard,
  SMEDashboard,
  useDashboard,
} from "../../../components/AeonOSDashboard";
import {
  SectorDashboardProvider,
  useSectorDataContext,
} from "../../../components/SectorDashboardProvider";
import { LiveMonitorBar, LiveMonitorWidget, AlertBanner } from "../../../components/LiveMonitor";
import { ModuleChat } from "../../../components/ModuleChat";
import SectorDashboardEditor from "../../../components/SectorDashboardEditor";
import { LiveIndicator } from "../../../components/LiveIndicator";
import { AnimatedWidget, AnimatedKPICard } from "../../../components/RefreshAnimations";
import {
  motion,
  FadeIn,
  StaggerContainer,
  StaggerItem,
  ScaleOnHover,
} from "@/components/animations";

interface SectorPack {
  id: string;
  version: string;
  sector: string;
  jurisdictions: string[];
  risk_level: string;
  inference_policy: {
    require_grounding: boolean;
    min_retrieval_score: number;
    min_groundedness_score: number;
    min_citation_coverage: number;
    require_citations: boolean;
    require_human_review: boolean;
    risk_level: string;
  };
  allowed_task_types: string[];
  blocked_task_types: string[];
  approved_model_tags: string[];
  notes: string[];
}

const RISK_COLORS: Record<string, string> = {
  low: "#22c55e",
  medium: "#eab308",
  high: "#f97316",
  critical: "#dc2626",
};

const SECTOR_APP_IDS = [
  "cybersecurity",
  "health",
  "finance",
  "retail",
  "transport",
  "manufacturing",
  "tourism",
  "utilities",
  "cultural_heritage",
  "sme",
  "telecom",
  "agriculture",
  "education",
  "public_safety",
  "real_estate",
];

function label(value: string) {
  return value.replaceAll("_", " ").replaceAll("-", " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

/**
 * Inner component that reads assembled sector data from SectorDashboardProvider
 * context and renders the appropriate dashboard component.
 */
function SectorDashboardInner({ sectorId }: { sectorId: string | undefined }) {
  const { data, loading, error, refreshKey } = useSectorDataContext();

  if (loading && !data) {
    return (
      <div className="skeleton-page" role="status" aria-label="Loading sector intelligence">
        <span className="sr-only">Loading sector data…</span>
        <div className="dashboard-grid mb-6">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="skeleton-stat">
              <div
                className="skeleton-shimmer"
                style={{ height: "1.75rem", width: "40%", borderRadius: "var(--aeon-radius)" }}
              />
              <div className="skeleton-shimmer" style={{ height: "0.7rem", width: "50%" }} />
            </div>
          ))}
        </div>
        <div className="skeleton-grid" style={{ "--skeleton-cols": 2 } as React.CSSProperties}>
          {[1, 2].map((i) => (
            <div
              key={i}
              className="skeleton-card"
              style={{ flexDirection: "column", padding: "1rem" }}
            >
              <div
                className="skeleton-shimmer"
                style={{ height: "0.9rem", width: "40%", marginBottom: "0.75rem" }}
              />
              {[1, 2, 3].map((j) => (
                <div
                  key={j}
                  className="skeleton-shimmer"
                  style={{ height: "0.7rem", width: "100%", marginBottom: "0.5rem" }}
                />
              ))}
            </div>
          ))}
        </div>
      </div>
    );
  }
  if (error) {
    console.warn("Sector tool fetch warning:", error);
  }
  if (!data) return null;

  // Wrap the dashboard with a layout animation container that animates on data refreshes
  const dashboardContent = (() => {
    switch (sectorId) {
      case "cybersecurity":
        return <CyberSecurityDashboard data={data} />;
      case "health":
        return <HealthDashboard data={data} />;
      case "finance":
        return <FinanceDashboard data={data} />;
      case "retail":
        return <RetailDashboard data={data} />;
      case "transport":
        return <TransportDashboard data={data} />;
      case "manufacturing":
        return <ManufacturingDashboard data={data} />;
      case "tourism":
        return <TourismDashboard data={data} />;
      case "utilities":
        return <UtilitiesDashboard data={data} />;
      case "cultural_heritage":
        return <CulturalHeritageDashboard data={data} />;
      case "sme":
        return <SMEDashboard data={data} />;
      default:
        return null;
    }
  })();

  return (
    <motion.div
      key={refreshKey}
      initial={{ opacity: 0.85 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.5, ease: "easeOut" }}
    >
      {dashboardContent}
    </motion.div>
  );
}

export default function AppPageClient() {
  const { appId } = useParams<{ appId: string }>();
  const [app, setApp] = useState<any>(null);
  const [vitals, setVitals] = useState<any>(null);
  const [pack, setPack] = useState<SectorPack | null>(null);
  const [packError, setPackError] = useState<string | null>(null);
  const { data: dashboardData, loading: dashboardLoading } = useDashboard(appId || "");

  // Load the sector pack policy that governs this module's sector (read-only).
  useEffect(() => {
    if (!appId) return;
    let cancelled = false;
    setPackError(null);
    (async () => {
      try {
        const res = await fetch("/api/os/sector-packs", {
          headers: getAuthHeaders(),
          cache: "no-store",
        });
        const body = await res.json();
        if (!res.ok || !body.ok) {
          if (!cancelled) setPackError(body.backend_down ? "offline" : body.error || "Unable to load sector policy");
          return;
        }
        const packs: SectorPack[] = body.packs || [];
        const match = packs.find((p) => p.sector === appId) || packs.find((p) => p.sector === "general");
        if (!cancelled) setPack(match || null);
      } catch {
        if (!cancelled) setPackError("offline");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [appId]);

  useEffect(() => {
    if (!appId) return;
    fetch("/api/os/apps", { cache: "no-store" })
      .then((r) => r.json())
      .then((data) => {
        const found = (data.apps || []).find((a: any) => a.id === appId);
        if (found) setApp(found);
      });
  }, [appId]);

  useEffect(() => {
    if (!appId) return;
    const loadVitals = async () => {
      try {
        const res = await fetch(`/api/os/apps/${appId}/vitals`, { cache: "no-store" });
        const data = await res.json();
        if (data.ok) setVitals(data);
      } catch {}
    };
    loadVitals();
    const t = setInterval(loadVitals, 5000);
    return () => clearInterval(t);
  }, [appId]);

  /**
   * Render a sector dashboard wrapped in SectorDashboardProvider that
   * fetches from individual /api/sector/[sector]/[tool] endpoints.
   * Falls back to the unified dashboard endpoint data for non-sector apps.
   */
  const renderDashboard = () => {
    if (dashboardLoading && !dashboardData) {
      return (
        <div className="skeleton-page" role="status" aria-label="Loading module">
          <span className="sr-only">Loading module data…</span>
          <div className="skeleton-grid" style={{ "--skeleton-cols": 3 } as React.CSSProperties}>
            {[1, 2, 3].map((i) => (
              <div key={i} className="skeleton-card" style={{ flexDirection: "column" }}>
                <div
                  className="skeleton-shimmer"
                  style={{ height: "1.2rem", width: "50%", marginBottom: "0.75rem" }}
                />
                <div className="skeleton-shimmer" style={{ height: "0.7rem", width: "80%" }} />
                <div className="skeleton-shimmer" style={{ height: "0.7rem", width: "60%" }} />
              </div>
            ))}
          </div>
        </div>
      );
    }

    if (!SECTOR_APP_IDS.includes(appId || "")) {
      // Non-sector app — just use the unified dashboard data
      if (!dashboardData) return null;
      return renderSectorDashboard(appId, dashboardData);
    }

    // Sector app — wrap in provider that fetches individual tool endpoints
    return (
      <SectorDashboardProvider sectorId={appId || ""} fallbackData={dashboardData}>
        <div className="flex items-center justify-between mb-3">
          <div />
          <LiveIndicator />
        </div>
        <SectorDashboardInner sectorId={appId} />
      </SectorDashboardProvider>
    );
  };

  function renderSectorDashboard(id: string | undefined, data: DashboardData) {
    switch (id) {
      case "cybersecurity":
        return <CyberSecurityDashboard data={data} />;
      case "retail":
        return <RetailDashboard data={data} />;
      case "manufacturing":
        return <ManufacturingDashboard data={data} />;
      case "professional":
        return <ProfessionalDashboard data={data} />;
      case "tourism":
        return <TourismDashboard data={data} />;
      case "health":
        return <HealthDashboard data={data} />;
      case "transport":
        return <TransportDashboard data={data} />;
      case "finance":
        return <FinanceDashboard data={data} />;
      case "cultural_heritage":
        return <CulturalHeritageDashboard data={data} />;
      case "utilities":
        return <UtilitiesDashboard data={data} />;
      case "sme":
        return <SMEDashboard data={data} />;
      default:
        return null;
    }
  }

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.3 }}>
      <div className="os-app-page">
        <FadeIn y={10} delay={0}>
          <header className="os-app-header">
            <div>
              <Link href="/os" className="os-back">
                ← OS Launcher
              </Link>
              <h1>
                {app?.icon} {app?.name}
              </h1>
              <p>{app?.description}</p>
            </div>
            <div className="os-app-meta">
              {vitals && (
                <>
                  <span>
                    Balance: {vitals.ledger_balance?.toFixed?.(4) ?? vitals.ledger_balance} ETH
                  </span>
                  <span>Goals: {vitals.open_goals?.length ?? 0}</span>
                  <span>Uptime: {vitals?.vitals?.uptime_s}s</span>
                </>
              )}
            </div>
          </header>
        </FadeIn>

        {/* ── Alerts ──────────────────────────────────── */}
        <FadeIn y={10} delay={0.05}>
          <AlertBanner />
        </FadeIn>

        {/* ── Live Monitoring Bar ──────────────────────── */}
        <FadeIn y={10} delay={0.1}>
          <LiveMonitorBar appId={appId} />
        </FadeIn>

        {renderDashboard()}

        {/* ── Inline Editor for sector apps ────────────── */}
        {appId && SECTOR_APP_IDS.includes(appId) && <SectorDashboardEditor sectorId={appId} />}

        {/* ── Live Metrics Widget ──────────────────────── */}
        <FadeIn y={10} delay={0.15}>
          <LiveMonitorWidget appId={appId} title="Real-Time Module Metrics" />
        </FadeIn>

        <FadeIn y={10} delay={0.2}>
          <section className="os-app-workspace">
            <ModuleChat appId={appId} appName={app?.name} />

            <aside className="os-app-sidebar">
              {appId && SECTOR_APP_IDS.includes(appId) && packError && (
                <div className="sector-policy-card" style={{ marginBottom: 18 }}>
                  <div className="eyebrow">SECTOR POLICY</div>
                  <p className="text-muted" style={{ fontSize: 13, margin: "6px 0 0" }}>
                    {packError === "offline"
                      ? "Control plane offline — policy unavailable. Reconnect the backend and refresh."
                      : "Policy unavailable: " + packError}
                  </p>
                </div>
              )}
              {appId && SECTOR_APP_IDS.includes(appId) && pack && !packError && (
                <div className="sector-policy-card" style={{ marginBottom: 18 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
                    <span className="eyebrow" style={{ margin: 0 }}>SECTOR POLICY</span>
                    <span
                      className="badge"
                      style={{
                        color: RISK_COLORS[pack.risk_level] || "var(--aeon-primary)",
                        borderColor: RISK_COLORS[pack.risk_level] || "var(--aeon-primary)",
                      }}
                    >
                      {pack.risk_level.toUpperCase()} RISK
                    </span>
                  </div>
                  <h4 style={{ margin: "12px 0 2px" }}>{pack.id}</h4>
                  <div className="text-muted" style={{ fontSize: 12, marginBottom: 12 }}>
                    v{pack.version} · {pack.jurisdictions.join(", ")}
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px 12px", fontSize: 13 }}>
                    <div>
                      <span className="text-muted">Grounding</span>
                      <div style={{ marginTop: 2 }}>{pack.inference_policy.require_grounding ? "Required" : "Off"}</div>
                    </div>
                    <div>
                      <span className="text-muted">Citations</span>
                      <div style={{ marginTop: 2 }}>{pack.inference_policy.require_citations ? "Required" : "Off"}</div>
                    </div>
                    <div>
                      <span className="text-muted">Human review</span>
                      <div style={{ marginTop: 2 }}>{pack.inference_policy.require_human_review ? "Required" : "Advisory"}</div>
                    </div>
                    <div>
                      <span className="text-muted">Retrieval ≥</span>
                      <div style={{ marginTop: 2 }}>{pack.inference_policy.min_retrieval_score.toFixed(2)}</div>
                    </div>
                  </div>
                  <h4 style={{ margin: "14px 0 0" }}>Approved Model Tags</h4>
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
                    {pack.approved_model_tags.length > 0 ? (
                      pack.approved_model_tags.map((tag) => (
                        <span className="badge" key={tag}>
                          {tag}
                        </span>
                      ))
                    ) : (
                      <span className="text-muted" style={{ fontSize: 12 }}>
                        None
                      </span>
                    )}
                  </div>
                  {pack.blocked_task_types.length > 0 && (
                    <>
                      <h4 style={{ margin: "14px 0 0" }}>Blocked Tasks</h4>
                      <ul className="os-goal-list" style={{ marginTop: 6 }}>
                        {pack.blocked_task_types.map((task) => (
                          <li key={task}>{label(task)}</li>
                        ))}
                      </ul>
                    </>
                  )}
                  {pack.notes.length > 0 && (
                    <p className="text-muted" style={{ fontSize: 12, marginTop: 12 }}>
                      {pack.notes.join(" ")}
                    </p>
                  )}
                </div>
              )}
              <h4>Allowed Tools</h4>
              <StaggerContainer>
                <ul className="os-tool-list">
                  {app?.allowed_tools?.map((t: string) => (
                    <StaggerItem key={t}>
                      <li>{t}</li>
                    </StaggerItem>
                  ))}
                </ul>
              </StaggerContainer>
              <h4>Default Goals</h4>
              <ul className="os-goal-list">
                {app?.default_goals?.map((g: any, i: number) => (
                  <StaggerItem key={i}>
                    <li>{g.title}</li>
                  </StaggerItem>
                ))}
              </ul>
            </aside>
          </section>
        </FadeIn>
      </div>
    </motion.div>
  );
}
