"use client";

import { useEffect, useState } from "react";

interface Health {
  ok: boolean;
  backend?: string;
}

export default function HealthStatus({ initial }: { initial?: Health | null }) {
  const [health, setHealth] = useState<Health | null>(initial ?? null);

  useEffect(() => {
    let alive = true;
    async function probe() {
      try {
        const r = await fetch("/api/health", { cache: "no-store" });
        const data = (await r.json()) as Health;
        if (!alive) return;
        setHealth(data);
      } catch {
        if (!alive) return;
        setHealth({ ok: false });
      }
    }
    probe();
    const t = setInterval(probe, 30000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  const label =
    health === null
      ? "Connecting..."
      : health.ok
      ? `System Online · ${health.backend || "stub"}`
      : "Connecting...";

  return (
    <div className="sidebar-status">
      <span className="sidebar-status-dot" />
      <span>{label}</span>
    </div>
  );
}
