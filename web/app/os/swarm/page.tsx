"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

type Agent = {
  app_id: string;
  ticks: number;
  vitals: Record<string, unknown>;
  open_goals: string[];
};

export default function SwarmPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedAgents, setSelectedAgents] = useState<Set<string>>(new Set());
  const [prompt, setPrompt] = useState("");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    fetchAgents();
  }, []);

  const fetchAgents = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/agents", { cache: "no-store" });
      const data = await res.json();
      if (data.ok) {
        setAgents(data.agents || []);
      } else {
        setError(data.error || "Failed to load agents.");
      }
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setLoading(false);
    }
  };

  const toggleAgent = (appId: string) => {
    setSelectedAgents((prev) => {
      const next = new Set(prev);
      if (next.has(appId)) {
        next.delete(appId);
      } else {
        next.add(appId);
      }
      return next;
    });
  };

  const runSwarm = async (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedAgents.size === 0) {
      setError("Please select at least one agent to form a swarm.");
      return;
    }
    if (!prompt.trim()) {
      setError("Please provide a prompt for the swarm.");
      return;
    }

    setRunning(true);
    setError(null);
    setResult(null);

    try {
      const res = await fetch("/api/os/swarm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          app_ids: Array.from(selectedAgents),
          prompt: prompt.trim(),
        }),
      });
      const data = await res.json();
      if (data.ok) {
        setResult(data);
      } else {
        setError(data.error || "Failed to run swarm orchestration.");
      }
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="os-page">
      <header className="os-header">
        <div>
          <h1 style={{ background: "var(--grad)", WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent" }}>
            🕸️ Swarm Orchestration
          </h1>
          <p className="dashboard-subtitle">Coordinate multiple autonomous agents in a unified workflow</p>
        </div>
        <Link href="/os" className="btn btn-secondary">
          ← OS Launcher
        </Link>
      </header>

      {error && <div className="module-alert danger">{error}</div>}

      <section style={{ marginBottom: 24 }}>
        <h3>Available Agents ({agents.length})</h3>
        {loading ? (
          <p style={{ color: "var(--fg-mute)" }}>Loading loaded agents...</p>
        ) : agents.length === 0 ? (
          <p style={{ color: "var(--fg-mute)" }}>
            No agents active. Run a module first to initialize agent instances.
          </p>
        ) : (
          <div className="os-grid">
            {agents.map((agent) => {
              const isSelected = selectedAgents.has(agent.app_id);
              return (
                <div
                  key={agent.app_id}
                  className={`os-card ${isSelected ? "installed" : ""}`}
                  onClick={() => toggleAgent(agent.app_id)}
                  style={{
                    cursor: "pointer",
                    border: isSelected ? "1px solid var(--accent)" : undefined,
                  }}
                >
                  <div className="os-card-header">
                    <h4>{agent.app_id}</h4>
                    <input
                      type="checkbox"
                      checked={isSelected}
                      readOnly
                      style={{ cursor: "pointer" }}
                    />
                  </div>
                  <p className="os-desc">Ticks: {agent.ticks}</p>
                  <p className="os-desc">Open Goals: {agent.open_goals.length}</p>
                  {agent.vitals && Object.keys(agent.vitals).length > 0 && (
                    <div
                      style={{
                        marginTop: 8,
                        display: "flex",
                        gap: 4,
                        flexWrap: "wrap",
                      }}
                    >
                      {Object.entries(agent.vitals)
                        .slice(0, 3)
                        .map(([k, v]) => (
                          <span
                            key={k}
                            className="os-status-pill"
                            style={{ fontSize: "0.65rem", padding: "2px 6px" }}
                          >
                            {k}: {String(v).substring(0, 10)}
                          </span>
                        ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </section>

      <section className="os-card" style={{ marginBottom: 24 }}>
        <h3>Orchestrate</h3>
        <form onSubmit={runSwarm} className="form-grid">
          <label className="span-2">
            Swarm Directives / Prompt
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              rows={4}
              placeholder="e.g. Discuss the latest metrics and have the research agent summarize them for the writer agent."
              disabled={running}
            />
          </label>
          <div
            className="span-2"
            style={{ display: "flex", justifyContent: "flex-end" }}
          >
            <button
              type="submit"
              className="btn btn-primary"
              disabled={running || selectedAgents.size === 0}
            >
              {running ? "Orchestrating..." : "Run Swarm"}
            </button>
          </div>
        </form>
      </section>

      {result && (
        <section className="os-card">
          <h3>Swarm Output</h3>
          <div
            style={{
              background: "var(--bg-elevated)",
              padding: 12,
              borderRadius: 6,
              overflowX: "auto",
            }}
          >
            <pre style={{ fontSize: "0.8rem", color: "var(--fg)" }}>
              {JSON.stringify(result, null, 2)}
            </pre>
          </div>
        </section>
      )}
    </div>
  );
}
