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
          <h1>AEON OS</h1>
          <p>Autonomous operating system for business and government.</p>
        </div>
        <Link href="/" className="btn-secondary">
          ← Chat
        </Link>
      </header>

      {error && <div className="os-error">{error}</div>}

      {loading ? (
        <div className="os-loading">Loading modules…</div>
      ) : (
        <section className="os-grid">
          {apps.map((app) => {
            const isInstalled = installed.includes(app.id);
            return (
              <div
                key={app.id}
                className={`os-card ${app.status} ${isInstalled ? "installed" : ""}`}
                style={{ borderTopColor: app.color }}
              >
                <div className="os-card-header">
                  <span className="os-icon" style={{ background: app.color }}>
                    {app.icon}
                  </span>
                  <span
                    className="os-status"
                    style={{ color: app.status === "active" ? "var(--success)" : "var(--fg-mute)" }}
                  >
                    {app.status}
                  </span>
                </div>
                <h3>{app.name}</h3>
                <p className="os-category">{app.category}</p>
                <p className="os-desc">{app.description}</p>
                <div className="os-card-actions">
                  {isInstalled ? (
                    <Link href={`/os/${app.id}`} className="btn-primary">
                      Open
                    </Link>
                  ) : (
                    <button
                      className="btn-secondary"
                      onClick={() => install(app.id)}
                      disabled={app.status !== "active"}
                    >
                      {app.status === "active" ? "Install" : "Planned"}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </section>
      )}
    </div>
  );
}
