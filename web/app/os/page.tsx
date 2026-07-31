"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import Link from "next/link";
import { useTheme } from "@/components/ThemeProvider";
import { isModuleEnabled, isWorkspaceAdmin } from "@/lib/theme-config";
import { FadeIn, StaggerContainer, StaggerItem, ScaleOnHover } from "@/components/animations";
import CrossSectorSearch from "@/components/CrossSectorSearch";

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

interface HeaderLink {
  href: string;
  label: string;
  moduleId: string;
}

const HEADER_LINKS: HeaderLink[] = [
  { href: "/os/integrations", label: "🔗 API Gateway", moduleId: "integrations" },
  { href: "/os/workflows", label: "️ Workflow Builder", moduleId: "automations" },
  { href: "/os/observability", label: "📊 Observability", moduleId: "observability" },
  { href: "/anomalies", label: "⚠️ Anomalies", moduleId: "security" },
  { href: "/incidents", label: "🚨 Incidents", moduleId: "security" },
  { href: "/dr", label: "🛡️ DR", moduleId: "security" },
  { href: "/os/siem", label: "🔍 SIEM", moduleId: "security" },
  { href: "/os/ai-studio", label: "🤖 AI Studio", moduleId: "aiStudio" },
  { href: "/os/knowledge", label: "📚 Knowledge Bases", moduleId: "knowledge" },
  { href: "/os/governance", label: "🛡️ Governance", moduleId: "governance" },
  { href: "/os/notifications", label: "🔔 Notifications", moduleId: "notifications" },
];

export default function OSPage() {
  const [apps, setApps] = useState<AppDefinition[]>([]);
  const [installed, setInstalled] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { config } = useTheme();
  const { data: session } = useSession();
  const admin = isWorkspaceAdmin((session?.user as any)?.role);

  const isVisible = (moduleId: string) => isModuleEnabled(config, moduleId, true) || admin;

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

  const visibleApps = apps.filter((app) => isVisible(app.id));

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
            ⊞ OS Module Launcher
          </h1>
          <p className="dashboard-subtitle">
            Deploy autonomous AI command centers across your enterprise
          </p>
        </div>
        <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
          {HEADER_LINKS.filter((link) => isVisible(link.moduleId)).map((link) => (
            <Link key={link.href} href={link.href} className="btn btn-primary">
              {link.label}
            </Link>
          ))}
          <Link
            href="/admin"
            className="btn btn-primary"
            style={{ borderColor: "#6366f1", color: "#6366f1" }}
          >
            ⚙️ Admin
          </Link>
        </div>
      </header>

      {/* ── Cross-Sector Search ── */}
      <FadeIn key="search" delay={0.05}>
        <div className="mb-6 flex justify-center">
          <CrossSectorSearch autoFocus={false} />
        </div>
      </FadeIn>

      {error && <div className="module-alert danger">{error}</div>}

      <FadeIn key="content" delay={0.1}>
        {loading ? (
          <div className="skeleton-page" role="status" aria-label="Loading modules">
            <span className="sr-only">Loading available modules…</span>
            <div className="skeleton-grid" style={{ "--skeleton-cols": 3 } as React.CSSProperties}>
              {[1, 2, 3, 4, 5, 6].map((i) => (
                <div
                  key={i}
                  className="skeleton-card"
                  style={{ flexDirection: "column", padding: "1.25rem" }}
                >
                  <div className="flex items-center gap-3 mb-3">
                    <div
                      className="skeleton-shimmer"
                      style={{
                        width: "2.5rem",
                        height: "2.5rem",
                        borderRadius: "var(--aeon-radius-sm)",
                        flexShrink: 0,
                      }}
                    />
                    <div className="flex-1 space-y-1.5">
                      <div
                        className="skeleton-shimmer"
                        style={{ height: "0.9rem", width: "60%" }}
                      />
                      <div
                        className="skeleton-shimmer"
                        style={{ height: "0.7rem", width: "40%" }}
                      />
                    </div>
                  </div>
                  <div className="skeleton-shimmer" style={{ height: "0.7rem", width: "90%" }} />
                  <div
                    className="skeleton-shimmer"
                    style={{ height: "0.7rem", width: "70%", marginTop: "0.4rem" }}
                  />
                </div>
              ))}
            </div>
          </div>
        ) : (
          <section className="os-grid">
            {visibleApps.map((app) => {
              const isInstalled = installed.includes(app.id);
              const enabled = isModuleEnabled(config, app.id, true);
              return (
                <div
                  key={app.id}
                  className={`os-card ${app.status} ${isInstalled ? "installed" : ""} ${!enabled && admin ? "opacity-60" : ""}`}
                  style={{ borderTopColor: app.color || "var(--accent)" }}
                >
                  <div className="os-card-header">
                    <span
                      className="os-icon"
                      style={{ background: app.color ? `${app.color}20` : "var(--bg-elevated)" }}
                    >
                      {app.icon}
                    </span>
                    <span className={`os-status-pill ${app.status}`}>{app.status}</span>
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
                      {isInstalled
                        ? "✓ Installed"
                        : app.status === "active"
                          ? "Install"
                          : "Planned"}
                    </button>
                  </div>
                  {!enabled && admin && (
                    <div className="text-xs text-aeon-fg-mute mt-2">Disabled</div>
                  )}
                </div>
              );
            })}

            {isVisible("automations") && (
              <div className="os-card active" style={{ borderTopColor: "#6366f1" }}>
                <div className="os-card-header">
                  <span className="os-icon" style={{ background: "#6366f120" }}>
                    📊
                  </span>
                  <span className="os-status-pill active">active</span>
                </div>
                <h3>Automation Metrics</h3>
                <p className="os-category">Observability</p>
                <p className="os-desc">
                  Execution health, success rates, and daily trends for automation rules.
                </p>
                <div className="os-card-actions">
                  <Link href="/os/automations/metrics" className="btn btn-sm btn-primary">
                    Open
                  </Link>
                </div>
              </div>
            )}
          </section>
        )}
      </FadeIn>
    </div>
  );
}
