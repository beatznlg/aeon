"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
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
  LiveMonitorBar,
  LiveMonitorWidget,
  AlertBanner,
} from "../../../components/LiveMonitor";
import { ModuleChat } from "../../../components/ModuleChat";

export default function AppPage() {
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

  const renderDashboard = () => {
    if (dashboardLoading) return <div style={{ color: "var(--fg-mute)", padding: 40, textAlign: "center" }}>Loading module intelligence…</div>;
    if (!dashboardData) return null;
    switch (appId) {
      case "cybersecurity": return <CyberSecurityDashboard data={dashboardData} />;
      case "retail": return <RetailDashboard data={dashboardData} />;
      case "manufacturing": return <ManufacturingDashboard data={dashboardData} />;
      case "professional": return <ProfessionalDashboard data={dashboardData} />;
      case "tourism": return <TourismDashboard data={dashboardData} />;
      case "health": return <HealthDashboard data={dashboardData} />;
      case "transport": return <TransportDashboard data={dashboardData} />;
      case "finance": return <FinanceDashboard data={dashboardData} />;
      case "cultural_heritage": return <CulturalHeritageDashboard data={dashboardData} />;
      case "utilities": return <UtilitiesDashboard data={dashboardData} />;
      case "sme": return <SMEDashboard data={dashboardData} />;
      default: return null;
    }
  };

  return (
    <div className="os-app-page">
      <header className="os-app-header">
        <div>
          <Link href="/os" className="os-back">← OS Launcher</Link>
          <h1>{app?.icon} {app?.name}</h1>
          <p>{app?.description}</p>
        </div>
        <div className="os-app-meta">
          {vitals && (
            <>
              <span>Balance: {vitals.ledger_balance?.toFixed?.(4) ?? vitals.ledger_balance} ETH</span>
              <span>Goals: {vitals.open_goals?.length ?? 0}</span>
              <span>Uptime: {vitals?.vitals?.uptime_s}s</span>
            </>
          )}
        </div>
      </header>

      {/* ── Alerts ──────────────────────────────────── */}
      <AlertBanner />

      {/* ── Live Monitoring Bar ──────────────────────── */}
      <LiveMonitorBar appId={appId} />

      {renderDashboard()}

      {/* ── Live Metrics Widget ──────────────────────── */}
      <LiveMonitorWidget appId={appId} title="Real-Time Module Metrics" />

      <section className="os-app-workspace">
        <ModuleChat appId={appId} appName={app?.name} />

        <aside className="os-app-sidebar">
          <h4>Allowed Tools</h4>
          <ul className="os-tool-list">
            {app?.allowed_tools?.map((t: string) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
          <h4>Default Goals</h4>
          <ul className="os-goal-list">
            {app?.default_goals?.map((g: any, i: number) => (
              <li key={i}>{g.title}</li>
            ))}
          </ul>
        </aside>
      </section>
    </div>
  );
}
