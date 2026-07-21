"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

type AppDefinition = {
  id: string;
  name: string;
  category: string;
  icon: string;
  color: string;
};

type WorkflowNode = {
  id: string;
  app_id: string;
  prompt: string;
  x: number;
  y: number;
};

type WorkflowEdge = {
  source: string;
  target: string;
  condition: string;
};

type Workflow = {
  id: string;
  name: string;
  description: string;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  created_at: number;
  updated_at: number;
};

const generateId = () => Math.random().toString(36).slice(2, 9);

export default function WorkflowBuilderPage() {
  const [apps, setApps] = useState<AppDefinition[]>([]);
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("New Workflow");
  const [description, setDescription] = useState("");
  const [nodes, setNodes] = useState<WorkflowNode[]>([]);
  const [edges, setEdges] = useState<WorkflowEdge[]>([]);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState<any>(null);

  useEffect(() => {
    Promise.all([
      fetch("/api/os/apps", { cache: "no-store" }).then((r) => r.json()),
      fetch("/api/os/workflows", { cache: "no-store" }).then((r) => r.json()),
    ])
      .then(([appsData, workflowsData]) => {
        if (appsData.ok) setApps(appsData.apps || []);
        if (workflowsData.ok) setWorkflows(workflowsData.workflows || []);
        else setError(workflowsData.error || "failed to load workflows");
        setLoading(false);
      })
      .catch((e) => {
        setError(String(e));
        setLoading(false);
      });
  }, []);

  const addNode = (appId: string) => {
    const count = nodes.length;
    const app = apps.find((a) => a.id === appId);
    const newNode: WorkflowNode = {
      id: generateId(),
      app_id: appId,
      prompt: app ? `Run ${app.name} analysis` : "",
      x: 120 + (count % 4) * 220,
      y: 120 + Math.floor(count / 4) * 160,
    };
    setNodes((prev) => [...prev, newNode]);
    setSelectedNode(newNode.id);
  };

  const updateNode = (id: string, patch: Partial<WorkflowNode>) => {
    setNodes((prev) => prev.map((n) => (n.id === id ? { ...n, ...patch } : n)));
  };

  const removeNode = (id: string) => {
    setNodes((prev) => prev.filter((n) => n.id !== id));
    setEdges((prev) => prev.filter((e) => e.source !== id && e.target !== id));
    setSelectedNode(null);
  };

  const addEdge = () => {
    if (nodes.length < 2) return;
    setEdges((prev) => [
      ...prev,
      { source: nodes[0].id, target: nodes[1].id, condition: "always" },
    ]);
  };

  const updateEdge = (idx: number, patch: Partial<WorkflowEdge>) => {
    setEdges((prev) => prev.map((e, i) => (i === idx ? { ...e, ...patch } : e)));
  };

  const removeEdge = (idx: number) => {
    setEdges((prev) => prev.filter((_, i) => i !== idx));
  };

  const saveWorkflow = async () => {
    setError(null);
    const body = { name, description, nodes, edges };
    const res = await fetch("/api/os/workflows", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (data.ok) {
      setWorkflows((prev) => {
        const existing = prev.find((w) => w.id === data.workflow.id);
        if (existing) {
          return prev.map((w) => (w.id === data.workflow.id ? data.workflow : w));
        }
        return [...prev, data.workflow];
      });
      setRunResult(null);
    } else {
      setError(data.error || "failed to save workflow");
    }
  };

  const runWorkflow = async (workflowId: string) => {
    setRunning(true);
    setRunResult(null);
    const res = await fetch(`/api/os/workflows/${workflowId}/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ initial_input: "" }),
    });
    const data = await res.json();
    setRunResult(data);
    setRunning(false);
  };

  const selected = useMemo(
    () => nodes.find((n) => n.id === selectedNode),
    [nodes, selectedNode]
  );

  if (loading) {
    return (
      <div className="os-page">
        <div style={{ padding: 40, textAlign: "center", color: "var(--fg-mute)" }}>
          Loading workflow studio…
        </div>
      </div>
    );
  }

  return (
    <div className="os-page">
      <header className="os-header">
        <div>
          <Link href="/os" className="os-back">
            ← OS Launcher
          </Link>
          <h1>🕸️ Workflow Builder</h1>
          <p className="dashboard-subtitle">
            Chain AEON modules into cross-module automations and multi-agent swarms
          </p>
        </div>
      </header>

      {error && <div className="module-alert danger">{error}</div>}

      <section className="module-widgets-grid" style={{ marginBottom: 24 }}>
        <div className="module-widget">
          <h3>Workflow Details</h3>
          <input
            className="os-input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Workflow name"
          />
          <input
            className="os-input"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Short description"
            style={{ marginTop: 8 }}
          />
          <button className="btn btn-primary" onClick={saveWorkflow} style={{ marginTop: 12 }}>
            💾 Save Workflow
          </button>
        </div>

        <div className="module-widget">
          <h3>Add Module Node</h3>
          <select
            className="os-input"
            onChange={(e) => {
              if (e.target.value) {
                addNode(e.target.value);
                e.target.value = "";
              }
            }}
            defaultValue=""
          >
            <option value="">Select a module…</option>
            {apps.map((app) => (
              <option key={app.id} value={app.id}>
                {app.icon} {app.name}
              </option>
            ))}
          </select>
          <button className="btn btn-sm" onClick={addEdge} disabled={nodes.length < 2} style={{ marginTop: 8 }}>
            Connect first two nodes
          </button>
        </div>

        <div className="module-widget">
          <h3>Saved Workflows</h3>
          {workflows.length === 0 ? (
            <p className="module-empty">No saved workflows yet.</p>
          ) : (
            <ul className="os-goal-list">
              {workflows.map((w) => (
                <li key={w.id} style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <span style={{ flex: 1 }}>{w.name}</span>
                  <button className="btn btn-sm" onClick={() => runWorkflow(w.id)} disabled={running}>
                    {running ? "Running…" : "Run"}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      <section className="module-widgets-grid" style={{ gridTemplateColumns: "2fr 1fr" }}>
        <div className="module-widget" style={{ minHeight: 400, position: "relative" }}>
          <h3>Canvas</h3>
          <div className="workflow-canvas">
            {nodes.map((node) => {
              const app = apps.find((a) => a.id === node.app_id);
              return (
                <div
                  key={node.id}
                  className={`workflow-node ${selectedNode === node.id ? "selected" : ""}`}
                  style={{ left: node.x, top: node.y, borderColor: app?.color || "var(--accent)" }}
                  onClick={() => setSelectedNode(node.id)}
                >
                  <div className="workflow-node-title">
                    {app?.icon} {app?.name || node.app_id}
                  </div>
                  <div className="workflow-node-id">{node.id.slice(0, 6)}</div>
                </div>
              );
            })}
            <svg className="workflow-edges">
              {edges.map((edge, i) => {
                const source = nodes.find((n) => n.id === edge.source);
                const target = nodes.find((n) => n.id === edge.target);
                if (!source || !target) return null;
                return (
                  <line
                    key={i}
                    x1={source.x + 90}
                    y1={source.y + 35}
                    x2={target.x + 90}
                    y2={target.y + 35}
                    stroke="var(--accent)"
                    strokeWidth={2}
                    markerEnd="url(#arrow)"
                  />
                );
              })}
              <defs>
                <marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto" markerUnits="strokeWidth">
                  <path d="M0,0 L0,6 L9,3 z" fill="var(--accent)" />
                </marker>
              </defs>
            </svg>
          </div>
        </div>

        <div className="module-widget">
          <h3>Node Inspector</h3>
          {selected ? (
            <>
              <div style={{ marginBottom: 8 }}>
                <strong>{apps.find((a) => a.id === selected.app_id)?.name || selected.app_id}</strong>
              </div>
              <label className="os-label">Prompt</label>
              <textarea
                className="os-input"
                rows={4}
                value={selected.prompt}
                onChange={(e) => updateNode(selected.id, { prompt: e.target.value })}
              />
              <label className="os-label" style={{ marginTop: 8 }}>
                Position X
              </label>
              <input
                type="number"
                className="os-input"
                value={selected.x}
                onChange={(e) => updateNode(selected.id, { x: Number(e.target.value) })}
              />
              <label className="os-label" style={{ marginTop: 8 }}>
                Position Y
              </label>
              <input
                type="number"
                className="os-input"
                value={selected.y}
                onChange={(e) => updateNode(selected.id, { y: Number(e.target.value) })}
              />
              <button className="btn btn-danger" onClick={() => removeNode(selected.id)} style={{ marginTop: 12 }}>
                Remove Node
              </button>
            </>
          ) : (
            <p className="module-empty">Select a node on the canvas to edit it.</p>
          )}

          <h4 style={{ marginTop: 24 }}>Edges</h4>
          {edges.length === 0 ? (
            <p className="module-empty">No edges yet.</p>
          ) : (
            edges.map((edge, i) => (
              <div key={i} className="module-alert" style={{ marginBottom: 8 }}>
                <small>
                  {edge.source.slice(0, 6)} → {edge.target.slice(0, 6)}
                </small>
                <select
                  className="os-input"
                  value={edge.condition}
                  onChange={(e) => updateEdge(i, { condition: e.target.value })}
                  style={{ marginTop: 4 }}
                >
                  <option value="always">always</option>
                  <option value="success">success</option>
                  <option value="failure">failure</option>
                </select>
                <button className="btn btn-sm" onClick={() => removeEdge(i)} style={{ marginTop: 4 }}>
                  Remove
                </button>
              </div>
            ))
          )}
        </div>
      </section>

      {runResult && (
        <section className="module-widget" style={{ marginTop: 24 }}>
          <h3>Last Run Result</h3>
          <pre className="os-pre">{JSON.stringify(runResult, null, 2)}</pre>
        </section>
      )}
    </div>
  );
}
