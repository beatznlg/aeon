"use client";

import { useEffect, useState } from "react";

type SetupKeys = {
  huggingface_token?: { present: boolean; length: number };
  supabase_url?: { present: boolean; host: string | null };
  next_public_supabase_url?: { present: boolean; host: string | null };
  aeon_hf_space_url?: { present: boolean; host: string | null };
  gh_token?: { present: boolean; length: number };
};
type SetupResponse = {
  ok: boolean;
  backend: "aeon-kernel" | "hf-inference";
  keys: SetupKeys;
  notes: string[];
};
type Health = "checking" | "ok" | "warn" | "down";

function dotFor(health: Health, h: { ok?: boolean; backend?: string } | null) {
  if (health === "checking") return { color: "#71717a", label: "checking…" };
  if (health === "down")    return { color: "#dc2626", label: "down" };
  if (health === "ok")      return { color: "#16a34a", label: "live · " + (h?.backend || "stub") };
  return { color: "#eab308", label: "live · partial env" };
}

export default function Sidebar({
  onNewChat,
  onOpenMemory,
  onOpenSettings,
  onOpenDeploy,
  mobileOpen = false,
  onCloseMobile,
}: {
  onNewChat: () => void;
  onOpenMemory: () => void;
  onOpenSettings: () => void;
  onOpenDeploy: () => void;
  mobileOpen?: boolean;
  onCloseMobile?: () => void;
}) {
  const [setup, setSetup] = useState<SetupResponse | null>(null);
  const [health, setHealth] = useState<Health>("checking");

  useEffect(() => {
    let alive = true;
    async function probe() {
      try {
        const r = await fetch("/api/health", { cache: "no-store" });
        const h = await r.json();
        if (!alive) return;
        setHealth(h?.ok ? "ok" : "down");
      } catch {
        if (!alive) return;
        setHealth("down");
      }
      try {
        const r = await fetch("/api/setup_check", { cache: "no-store" });
        const j = (await r.json()) as SetupResponse;
        if (!alive) return;
        setSetup(j);
        const k = j?.keys || {};
        const nothingWired =
          !k.huggingface_token?.present &&
          !k.aeon_hf_space_url?.present &&
          !k.next_public_supabase_url?.present;
        if (nothingWired) setHealth("warn");
      } catch {
        // setup_check failure is non-fatal — health already reflects it.
      }
    }
    probe();
    const t = setInterval(probe, 30_000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  const dot = dotFor(health, setup);
  const missing = setup?.notes?.filter((n) => /missing/i.test(n)) || [];

  return (
    <aside
      className={"sidebar" + (mobileOpen ? " show-mobile" : "")}
      aria-hidden={!mobileOpen ? undefined : false}
    >
      <div className="sidebar-header">
        <div className="brand">
          <span className="logo">⟁</span>
          <span>AEON</span>
        </div>
        <button className="btn-primary" onClick={() => { onNewChat(); onCloseMobile?.(); }}>
          + New chat
        </button>
        {mobileOpen && (
          <button className="sidebar-close" onClick={onCloseMobile} title="Close menu">×</button>
        )}
      </div>

      <nav className="sidebar-section">
        <h3>Workspace</h3>
        <a href="#" onClick={(e) => { e.preventDefault(); onOpenDeploy(); onCloseMobile?.(); }}>
          Deploy guide
          <span className={"deploy-badge " + (health === "ok" ? "ok" : health === "warn" ? "warn" : "down")}>
            {health === "ok" ? "live" : health === "warn" ? "incomplete" : health === "down" ? "down" : "…"}
          </span>
        </a>
        <a href="#" onClick={(e) => { e.preventDefault(); onOpenMemory(); onCloseMobile?.(); }}>
          Memory browser
        </a>
        <a href="#" onClick={(e) => { e.preventDefault(); onOpenSettings(); onCloseMobile?.(); }}>
          Settings & keys
        </a>
        <a href="https://huggingface.co/settings/tokens" target="_blank" rel="noopener noreferrer">
          HF token ↗
        </a>
        <a href="https://supabase.com/dashboard" target="_blank" rel="noopener noreferrer">
          Supabase ↗
        </a>
        <a href="https://huggingface.co/new-space" target="_blank" rel="noopener noreferrer">
          HF Space (kernel) ↗
        </a>
        <a href="https://github.com/beatznlg/aeon/settings/security_analysis" target="_blank" rel="noopener noreferrer">
          GHAS settings ↗
        </a>
      </nav>

      <div className="sidebar-footer">
        <span
          className="status-dot"
          style={{ background: dot.color, boxShadow: `0 0 8px ${dot.color}` }}
          title={setup ? `${dot.label}\n\nmissing: ${missing.join(" | ") || "none"}` : dot.label}
        ></span>
        <span style={{ display: "flex", flexDirection: "column", gap: "0.1rem" }}>
          <span><span style={{ color: dot.color, fontWeight: 600 }}>{dot.label}</span></span>
          <span style={{ fontSize: "0.72rem", opacity: 0.6 }}>
            kernel <code style={{ fontSize: "0.72rem" }}>v2.1</code>
            {setup?.backend ? " · " + setup.backend : ""}
          </span>
        </span>
      </div>
    </aside>
  );
}
