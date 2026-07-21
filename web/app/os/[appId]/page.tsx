"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  RetailDashboard,
  ManufacturingDashboard,
  ProfessionalDashboard,
  TourismDashboard,
  useDashboard,
  KPICard,
} from "../../../components/AeonOSDashboard";

 type TickResult = {
  ok: boolean;
  app_id: string;
  result: {
    answer: string;
    backend: string;
    wall_s: number;
    tool_calls: number;
  };
};

const MODULE_NAMES: Record<string, string> = {
  cybersecurity: "Security Command Center",
  retail: "Commerce Command Center",
  manufacturing: "Factory Command Center",
  professional: "Professional Services Hub",
  tourism: "Hospitality Command Center",
};

export default function AppPage() {
  const { appId } = useParams<{ appId: string }>();
  const [app, setApp] = useState<any>(null);
  const [query, setQuery] = useState("");
  const [running, setRunning] = useState(false);
  const [logs, setLogs] = useState<TickResult[]>([]);
  const [error, setError] = useState<string | null>(null);
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

  const sendTick = async () => {
    if (!query.trim() || running) return;
    setRunning(true);
    try {
      const res = await fetch(`/api/os/apps/${appId}/tick`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: query.trim() }),
      });
      const data: TickResult = await res.json();
      if (data.ok) {
        setLogs((prev) => [...prev, data]);
      } else {
        setError(data.result?.answer || "tick failed");
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setRunning(false);
    }
  };

  const loadVitals = async () => {
    try {
      const res = await fetch(`/api/os/apps/${appId}/vitals`, { cache: "no-store" });
      const data = await res.json();
      if (data.ok) setVitals(data);
    } catch (e) {
      // non-fatal
    }
  };

  useEffect(() => {
    if (!appId) return;
    loadVitals();
    const t = setInterval(loadVitals, 5000);
    return () => clearInterval(t);
  }, [appId]);

  const renderDashboard = () => {
    if (dashboardLoading) return <div className="os-loading">Loading module intelligence…</div>;
    if (!dashboardData) return null;
    switch (appId) {
      case "retail":
        return <RetailDashboard data={dashboardData} />;
      case "manufacturing":
        return <ManufacturingDashboard data={dashboardData} />;
      case "professional":
        return <ProfessionalDashboard data={dashboardData} />;
      case "tourism":
        return <TourismDashboard data={dashboardData} />;
      default:
        return null;
    }
  };

  return (
    <div className="os-app-page">
      <header className="os-app-header">
        <div>
          <Link href="/os" className="os-back">
            ← OS Launcher
          </Link>
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

      {renderDashboard()}

      <section className="os-app-workspace">
        <div className="os-chat">
          <div className="os-chat-input">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={`Ask ${app?.name} to do something autonomously...`}
              onKeyDown={(e) => e.key === "Enter" && sendTick()}
            />
            <button onClick={sendTick} disabled={running}>
              {running ? "Running…" : "Run"}
            </button>
          </div>
          {error && <div className="os-error">{error}</div>}
          <div className="os-logs">
            {logs.map((log, i) => (
              <div key={i} className="os-log">
                <div className="os-log-meta">
                  {log.app_id} · {log.result.backend} · {log.result.wall_s}s · {log.result.tool_calls} tools
                </div>
                <div className="os-log-body">{log.result.answer}</div>
              </div>
            ))}
            {logs.length === 0 && !running && (
              <div className="os-empty">Send a command to see the autonomous agent at work.</div>
            )}
            {running && <div className="os-empty">Agent is thinking…</div>}
          </div>
        </div>

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
