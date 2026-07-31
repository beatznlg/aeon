"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
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
  const { data: dashboardData, loading: dashboardLoading } = useDashboard(appId || "");

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

    const sectorAppIds = [
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
    ];

    if (!sectorAppIds.includes(appId || "")) {
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
        {appId &&
          [
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
          ].includes(appId) && <SectorDashboardEditor sectorId={appId} />}

        {/* ── Live Metrics Widget ──────────────────────── */}
        <FadeIn y={10} delay={0.15}>
          <LiveMonitorWidget appId={appId} title="Real-Time Module Metrics" />
        </FadeIn>

        <FadeIn y={10} delay={0.2}>
          <section className="os-app-workspace">
            <ModuleChat appId={appId} appName={app?.name} />

            <aside className="os-app-sidebar">
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
