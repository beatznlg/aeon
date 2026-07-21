"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { SystemHealthPanel, AlertBanner, AlertPanel } from "../components/LiveMonitor";

const MODULES = [
  { id: "cybersecurity", name: "Security Command", icon: "🛡️", color: "#ef4444", status: "active", tools: 12, desc: "Threat intelligence, vulnerability scanning, and compliance monitoring" },
  { id: "health", name: "Health Command", icon: "🏥", color: "#10b981", status: "active", tools: 8, desc: "AI diagnostics, patient monitoring, drug interaction checks" },
  { id: "finance", name: "Finance Command", icon: "💰", color: "#f59e0b", status: "active", tools: 10, desc: "Risk analysis, market forecasting, fraud detection" },
  { id: "retail", name: "Commerce Command", icon: "📦", color: "#6366f1", status: "active", tools: 9, desc: "Demand forecasting, inventory optimization, pricing" },
  { id: "transport", name: "Transport Command", icon: "🚚", color: "#06b6d4", status: "active", tools: 7, desc: "Traffic management, fleet scheduling, route optimization" },
  { id: "manufacturing", name: "Factory Command", icon: "🏭", color: "#ec4899", status: "active", tools: 6, desc: "Predictive maintenance, quality control, smart logistics" },
  { id: "tourism", name: "Hospitality Command", icon: "🏨", color: "#8b5cf6", status: "active", tools: 7, desc: "Booking optimization, dynamic pricing, automated concierge" },
  { id: "cultural_heritage", name: "Cultural Command", icon: "🎭", color: "#14b8a6", status: "active", tools: 6, desc: "Visitor engagement, exhibition planning, virtual tours" },
  { id: "professional", name: "Professional Hub", icon: "📋", color: "#a855f7", status: "active", tools: 5, desc: "Document parsing, accounting workflows, data management" },
  { id: "utilities", name: "Utilities Command", icon: "⚡", color: "#eab308", status: "active", tools: 6, desc: "Resource optimization, waste management, energy grid" },
  { id: "sme", name: "SME Business Suite", icon: "🏢", color: "#3b82f6", status: "active", tools: 8, desc: "Workflow automation, document processing, AI support" },
];

export default function DashboardPage() {
  const [vitals, setVitals] = useState<any>(null);
  const [health, setHealth] = useState<{ ok: boolean; backend?: string } | null>(null);

  useEffect(() => {
    fetch("/api/health", { cache: "no-store" })
      .then((r) => r.json())
      .then((d) => setHealth(d))
      .catch(() => {});

    fetch("/api/os/apps", { cache: "no-store" })
      .then((r) => r.json())
      .then((d) => {
        if (d?.apps?.[0]?.allowed_tools) {
          setVitals({ total_tools: d.apps.reduce((s: number, a: any) => s + (a.allowed_tools?.length || 0), 0) });
        }
      })
      .catch(() => {});
  }, []);

  const activeModules = MODULES.filter((m) => m.status === "active");
  const totalTools = vitals?.total_tools || activeModules.reduce((s, m) => s + m.tools, 0);

  return (
    <div className="dashboard">
      {/* Header */}
      <div className="dashboard-header">
        <div>
          <h1 className="dashboard-title">AEON Operating System</h1>
          <p className="dashboard-subtitle">
            Autonomous AI platform for enterprise and government — {activeModules.length} modules · {totalTools} tools
          </p>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <Link href="/os" className="btn btn-primary">
            ⊞ Launch OS
          </Link>
          <Link href="/llm" className="btn">
            ⚡ Connect LLM
          </Link>
        </div>
      </div>

      {/* ═══ Alerts ═══ */}
      <AlertBanner />
      <AlertPanel />

      {/* System Status Bar */}
      <div className="system-bar">
        <div className="system-bar-card">
          <div className="system-bar-icon" style={{ background: "rgba(99,102,241,0.12)", color: "var(--accent)" }}>⟁</div>
          <div className="system-bar-info">
            <div className="system-bar-label">System Status</div>
            <div className="system-bar-value" style={{ color: "var(--success)" }}>
              {health === null ? "..." : health.ok ? "Online" : "Connecting"}
            </div>
            <div className="system-bar-sub">{health?.backend || "AEON stub"} backend</div>
          </div>
        </div>

        <div className="system-bar-card">
          <div className="system-bar-icon" style={{ background: "rgba(16,185,129,0.12)", color: "var(--success)" }}>⊞</div>
          <div className="system-bar-info">
            <div className="system-bar-label">Active Modules</div>
            <div className="system-bar-value">{activeModules.length}</div>
            <div className="system-bar-sub">Operational</div>
          </div>
        </div>

        <div className="system-bar-card">
          <div className="system-bar-icon" style={{ background: "rgba(245,158,11,0.12)", color: "var(--warning)" }}>⚡</div>
          <div className="system-bar-info">
            <div className="system-bar-label">Smart Tools</div>
            <div className="system-bar-value">{totalTools}</div>
            <div className="system-bar-sub">AI-powered capabilities</div>
          </div>
        </div>

        <div className="system-bar-card">
          <div className="system-bar-icon" style={{ background: "rgba(6,182,212,0.12)", color: "var(--accent-3)" }}>◈</div>
          <div className="system-bar-info">
            <div className="system-bar-label">LLM Backend</div>
            <div className="system-bar-value">{health?.backend === "aeon-kernel" ? "AEON Kernel" : health?.backend === "hf-inference" ? "HF Inference" : "Stub"}</div>
            <div className="system-bar-sub">Pluggable · Hot-swappable</div>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <h2 style={{ fontSize: "1.1rem", fontWeight: 600, marginBottom: 16 }}>Command Centers</h2>
      <div className="quick-actions">
        {MODULES.map((mod) => (
          <Link key={mod.id} href={`/os/${mod.id}`} className="quick-action-card">
            <div className="qac-icon" style={{ background: `${mod.color}15`, color: mod.color }}>
              {mod.icon}
            </div>
            <div className="qac-title">{mod.name}</div>
            <div className="qac-desc">{mod.desc}</div>
            <div className="qac-meta">
              <span className={`qac-status ${mod.status}`}>{mod.status}</span>
              <span className="qac-tools">{mod.tools} tools</span>
            </div>
          </Link>
        ))}
      </div>

      {/* ═══ Real-Time System Health ═══ */}
      <SystemHealthPanel />

      {/* Enterprise Features */}
      <h2 style={{ fontSize: "1.1rem", fontWeight: 600, marginBottom: 16 }}>Platform Capabilities</h2>
      <div className="metrics-grid">
        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-title">LLM Agnostic</span>
            <span style={{ fontSize: "1.2rem" }}>🔌</span>
          </div>
          <div className="metric-value" style={{ fontSize: "1rem" }}>OpenAI · Anthropic · HF · Ollama · Qwen</div>
          <div className="metric-change up">Plug any provider via API key</div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-title">Autonomous Agent</span>
            <span style={{ fontSize: "1.2rem" }}>🤖</span>
          </div>
          <div className="metric-value" style={{ fontSize: "1rem" }}>Self-improving · Reflective</div>
          <div className="metric-change up">Goal-driven with CodeEvolver</div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-title">Enterprise Security</span>
            <span style={{ fontSize: "1.2rem" }}>🔒</span>
          </div>
          <div className="metric-value" style={{ fontSize: "1rem" }}>Sandboxed · Audited</div>
          <div className="metric-change up">CodeSandbox · Causal Credit</div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-title">Multi-Vertical</span>
            <span style={{ fontSize: "1.2rem" }}>🏢</span>
          </div>
          <div className="metric-value" style={{ fontSize: "1rem" }}>11 Industry Modules</div>
          <div className="metric-change up">Government · Enterprise · SME</div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-title">Memory & Learning</span>
            <span style={{ fontSize: "1.2rem" }}>🧠</span>
          </div>
          <div className="metric-value" style={{ fontSize: "1rem" }}>Episodic · Semantic · Procedural</div>
          <div className="metric-change up">Persistent across sessions</div>
        </div>

        <div className="metric-card">
          <div className="metric-header">
            <span className="metric-title">Revenue Model</span>
            <span style={{ fontSize: "1.2rem" }}>💰</span>
          </div>
          <div className="metric-value" style={{ fontSize: "1rem" }}>Bounties · Ledger · Services</div>
          <div className="metric-change up">Built-in token economy</div>
        </div>
      </div>
    </div>
  );
}
