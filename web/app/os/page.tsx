"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

type AppDefinition = {
  id: string;
  name: string;
  category: string;
  description: string;
  icon: string;
  color: string;
  status: string;
  allowed_tools: string[];
  default_goals: { title: string; priority: number }[];
};

export default function OSPage() {
  const [apps, setApps] = useState<AppDefinition[]>([]);
  const [installed, setInstalled] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/os/apps", { cache: "no-store" })
      .then((r) => r.json())
      .then((data) => {
        if (data.ok) {
          setApps(data.apps || []);
          setInstalled(data.installed || []);
        } else {
          setError(data.error || "failed to load apps");
        }
        setLoading(false);
      })
      .catch((e) => {
        setError(String(e));
        setLoading(false);
      });
  }, []);

  const install = async (appId: string) => {
    try {
      const res = await fetch("/api/os/apps", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ appId }),
      });
      const data = await res.json();
      if (data.ok) {
        setInstalled((prev) => (prev.includes(appId) ? prev : [...prev, appId]));
      }
    } catch (e) {
      setError(String(e));
    }
  };

  return (
    <div className="os-page">
      <header className="os-header">
        <div>
          <h1 style={{ background: "var(--grad)", WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent" }}>
            ⊞ OS Module Launcher
          </h1>
          <p className="dashboard-subtitle">
            Deploy autonomous AI command centers across your enterprise
          </p>
        </div>
        <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
          <Link href="/os/integrations" className="btn btn-primary">
            🔗 API Gateway
          </Link>
          <Link href="/os/workflows" className="btn btn-primary">
            🕸️ Workflow Builder
          </Link>
          <Link href="/os/observability" className="btn btn-primary">
            📊 Observability
          </Link>
          <Link href="/os/ai-studio" className="btn btn-primary">
            🤖 AI Studio
          </Link>
          <Link href="/os/knowledge" className="btn btn-primary">
            📚 Knowledge Bases
          </Link>
          <Link href="/os/governance" className="btn btn-primary">
            🛡️ Governance
          </Link>
          <Link href="/os/notifications" className="btn btn-primary">
            🔔 Notifications
          </Link>
          <Link href="/admin" className="btn btn-primary" style={{ borderColor: "#6366f1", color: "#6366f1" }}>
            ⚙️ Admin
          </Link>
        </div>
      </header>

      {error && <div className="module-alert danger">{error}</div>}

      {loading ? (
        <div style={{ color: "var(--fg-mute)", padding: 40, textAlign: "center" }}>Loading modules…</div>
      ) : (
        <section className="os-grid">
          {apps.map((app) => {
            const isInstalled = installed.includes(app.id);
            return (
              <div
                key={app.id}
                className={`os-card ${app.status} ${isInstalled ? "installed" : ""}`}
                style={{ borderTopColor: app.color || "var(--accent)" }}
              >
                <div className="os-card-header">
                  <span className="os-icon" style={{ background: app.color ? `${app.color}20` : "var(--bg-elevated)" }}>
                    {app.icon}
                  </span>
                  <span className={`os-status-pill ${app.status}`}>
                    {app.status}
                  </span>
                </div>
                <h3>{app.name}</h3>
                <p className="os-category">{app.category}</p>
                <p className="os-desc">{app.description}</p>
                <div className="os-card-actions">
                  <Link href={`/os/${app.id}`} className="btn btn-sm btn-primary">
                    Open
                  </Link>
                  <button
                    className={`btn btn-sm ${isInstalled ? "btn-success" : ""}`}
                    onClick={() => install(app.id)}
                    disabled={app.status !== "active"}
                  >
                    {isInstalled ? "✓ Installed" : app.status === "active" ? "Install" : "Planned"}
                  </button>
                </div>
              </div>
            );
          })}
        </section>
      )}
    </div>
  );
}
