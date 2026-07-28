"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";

type AppDefinition = {
  id: string;
  name: string;
  category: string;
  icon: string;
  color: string;
};

type Integration = {
  id: string;
  name: string;
  type: string;
  enabled: boolean;
};

type WorkflowNode = {
  id: string;
  app_id: string;
  prompt: string;
  x: number;
  y: number;
  type?: "agent" | "integration";
  integration_id?: string;
  endpoint?: string;
  method?: string;
  payload?: string;
  provider?: string;
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
  provider?: string;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  created_at: number;
  updated_at: number;
};

type WorkflowState = {
  name: string;
  description: string;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
};

const generateId = () => Math.random().toString(36).slice(2, 9);

const cloneState = (s: WorkflowState): WorkflowState => ({
  ...s,
  nodes: s.nodes.map((n) => ({ ...n })),
  edges: s.edges.map((e) => ({ ...e })),
});

export default function WorkflowBuilderPage() {
  const [apps, setApps] = useState<AppDefinition[]>([]);
  const [integrations, setIntegrations] = useState<Integration[]>([]);
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
  const [workflowProvider, setWorkflowProvider] = useState("");
  const [nodeTrace, setNodeTrace] = useState<Record<string, "ok" | "fail" | "running" | null>>({});

  const [draggingId, setDraggingId] = useState<string | null>(null);
  const dragOffset = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const canvasRef = useRef<HTMLDivElement | null>(null);

  const [edgeDraggingSource, setEdgeDraggingSource] = useState<string | null>(null);
  const [mousePos, setMousePos] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const lastPanMouse = useRef<{ x: number; y: number }>({ x: 0, y: 0 });

  // Undo/redo history
  const [past, setPast] = useState<WorkflowState[]>([]);
  const [future, setFuture] = useState<WorkflowState[]>([]);
  const currentStateRef = useRef<WorkflowState>({
    name,
    description,
    nodes,
    edges,
  });
  const dragStartSnapshot = useRef<WorkflowState | null>(null);
  const focusStartState = useRef<WorkflowState | null>(null);

  useEffect(() => {
    currentStateRef.current = { name, description, nodes, edges };
  }, [name, description, nodes, edges]);

  const restoreState = (state: WorkflowState) => {
    setName(state.name);
    setDescription(state.description);
    setNodes(state.nodes.map((n) => ({ ...n })));
    setEdges(state.edges.map((e) => ({ ...e })));
  };

  const saveSnapshot = () => {
    setPast((prev) => [...prev, cloneState(currentStateRef.current)].slice(-50));
    setFuture([]);
  };

  const undo = () => {
    setPast((prev) => {
      if (prev.length === 0) return prev;
      const previous = prev[prev.length - 1];
      setFuture((f) => [cloneState(currentStateRef.current), ...f]);
      restoreState(previous);
      return prev.slice(0, prev.length - 1);
    });
  };

  const redo = () => {
    setFuture((prev) => {
      if (prev.length === 0) return prev;
      const next = prev[0];
      setPast((p) => [...p, cloneState(currentStateRef.current)].slice(-50));
      restoreState(next);
      return prev.slice(1);
    });
  };

  const clearDraft = () => {
    if (!confirm("Are you sure you want to clear your current draft?")) return;
    setName("New Workflow");
    setDescription("");
    setNodes([]);
    setEdges([]);
    setPast([]);
    setFuture([]);
    localStorage.removeItem("aeon_workflow_draft");
  };

  const handleFocus = () => {
    focusStartState.current = cloneState(currentStateRef.current);
  };

  const handleBlur = () => {
    if (!focusStartState.current) return;
    if (
      JSON.stringify(focusStartState.current) !== JSON.stringify(currentStateRef.current)
    ) {
      setPast((prev) => [...prev, focusStartState.current!].slice(-50));
      setFuture([]);
    }
    focusStartState.current = null;
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/exhaustive-deps
    const onKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      const tag = target?.tagName?.toLowerCase();
      const isTyping = tag === "input" || tag === "textarea" || tag === "select" || target?.isContentEditable;

      if (isTyping) {
        if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") {
          e.preventDefault();
          saveWorkflow();
        }
        return;
      }

      switch (e.key) {
        case "+":
        case "=":
          e.preventDefault();
          setZoom((z) => Math.min(3, z + 0.2));
          break;
        case "-":
        case "_":
          e.preventDefault();
          setZoom((z) => Math.max(0.2, z - 0.2));
          break;
        case "0":
          e.preventDefault();
          setZoom(1);
          setPan({ x: 0, y: 0 });
          break;
        case "ArrowUp":
          e.preventDefault();
          setPan((p) => ({ ...p, y: p.y + 50 }));
          break;
        case "ArrowDown":
          e.preventDefault();
          setPan((p) => ({ ...p, y: p.y - 50 }));
          break;
        case "ArrowLeft":
          e.preventDefault();
          setPan((p) => ({ ...p, x: p.x + 50 }));
          break;
        case "ArrowRight":
          e.preventDefault();
          setPan((p) => ({ ...p, x: p.x - 50 }));
          break;
        case "Delete":
        case "Backspace":
          if (selectedNode) {
            e.preventDefault();
            removeNode(selectedNode);
          }
          break;
        case "Escape":
          setSelectedNode(null);
          setDraggingId(null);
          setEdgeDraggingSource(null);
          break;
        case "s":
        case "S":
          if (e.metaKey || e.ctrlKey) {
            e.preventDefault();
            saveWorkflow();
          }
          break;
        case "z":
        case "Z":
          if (e.metaKey || e.ctrlKey) {
            e.preventDefault();
            if (e.shiftKey) {
              redo();
            } else {
              undo();
            }
          }
          break;
        case "y":
        case "Y":
          if (e.metaKey || e.ctrlKey) {
            e.preventDefault();
            redo();
          }
          break;
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [selectedNode]);

  useEffect(() => {
    Promise.all([
      fetch("/api/os/apps", { cache: "no-store" }).then((r) => r.json()),
      fetch("/api/os/workflows", { cache: "no-store" }).then((r) => r.json()),
      fetch("/api/os/integrations", { cache: "no-store" }).then((r) => r.json()),
    ])
      .then(([appsData, workflowsData, intData]) => {
        if (appsData.ok) setApps(appsData.apps || []);
        if (workflowsData.ok) setWorkflows(workflowsData.workflows || []);
        else setError(workflowsData.error || "failed to load workflows");
        if (intData.ok) setIntegrations(intData.integrations || []);

        const draft = localStorage.getItem("aeon_workflow_draft");
        if (draft) {
          try {
            const parsed = JSON.parse(draft);
            if (parsed.name) setName(parsed.name);
            if (parsed.description) setDescription(parsed.description);
            if (parsed.nodes) setNodes(parsed.nodes);
            if (parsed.edges) setEdges(parsed.edges);
            if (parsed.past) setPast(parsed.past.slice(-50));
            if (parsed.future) setFuture(parsed.future.slice(0, 50));
          } catch (e) {
            console.error("Failed to parse draft", e);
          }
        }

        setLoading(false);
      })
      .catch((e) => {
        setError(String(e));
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    if (loading) return;
    const stateToSave = {
      name,
      description,
      nodes,
      edges,
      past: past.slice(-50),
      future: future.slice(0, 50),
    };
    localStorage.setItem("aeon_workflow_draft", JSON.stringify(stateToSave));
  }, [name, description, nodes, edges, past, future, loading]);

  const PROVIDERS = [
    { id: "", name: "Workflow default" },
    { id: "stub", name: "Stub" },
    { id: "openai", name: "OpenAI" },
    { id: "anthropic", name: "Claude" },
    { id: "ollama", name: "Ollama" },
    { id: "hf", name: "Hugging Face" },
    { id: "qwen", name: "Qwen Local" },
  ];

  const addNode = (id: string, type: "agent" | "integration") => {
    saveSnapshot();
    const count = nodes.length;
    const app = type === "agent" ? apps.find((a) => a.id === id) : undefined;
    const integration = type === "integration" ? integrations.find((i) => i.id === id) : undefined;
    const newNode: WorkflowNode = {
      id: generateId(),
      app_id: type === "agent" ? id : "",
      integration_id: type === "integration" ? id : "",
      type,
      prompt: app ? `Run ${app.name} analysis` : "",
      endpoint: type === "integration" ? "" : undefined,
      method: type === "integration" ? "GET" : undefined,
      payload: type === "integration" ? "" : undefined,
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
    saveSnapshot();
    setNodes((prev) => prev.filter((n) => n.id !== id));
    setEdges((prev) => prev.filter((e) => e.source !== id && e.target !== id));
    setSelectedNode(null);
  };

  const addEdge = () => {
    if (nodes.length < 2) return;
    saveSnapshot();
    setEdges((prev) => [
      ...prev,
      { source: nodes[0].id, target: nodes[1].id, condition: "always" },
    ]);
  };

  const updateEdge = (idx: number, patch: Partial<WorkflowEdge>) => {
    setEdges((prev) => prev.map((e, i) => (i === idx ? { ...e, ...patch } : e)));
  };

  const removeEdge = (idx: number) => {
    saveSnapshot();
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
      setPast([]);
      setFuture([]);
      setRunResult(null);
    } else {
      setError(data.error || "failed to save workflow");
    }
  };

  const runWorkflow = async (workflowId: string) => {
    setRunning(true);
    setRunResult(null);

    // Set all nodes to "running" state
    const runningTrace: Record<string, "running"> = {};
    nodes.forEach((n) => { runningTrace[n.id] = "running"; });
    setNodeTrace(runningTrace);

    const res = await fetch(`/api/os/workflows/${workflowId}/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ initial_input: "", provider: workflowProvider || undefined }),
    });
    const data = await res.json();
    setRunResult(data);

    // Update trace with execution results
    const trace: Record<string, "ok" | "fail" | null> = {};
    if (data.ok && data.results) {
      data.results.forEach((r: any) => {
        trace[r.node_id] = r.ok ? "ok" : "fail";
      });
    }
    setNodeTrace(trace);
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
            onFocus={handleFocus}
            onBlur={handleBlur}
            placeholder="Workflow name"
          />
          <input
            className="os-input"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            onFocus={handleFocus}
            onBlur={handleBlur}
            placeholder="Short description"
            style={{ marginTop: 8 }}
          />
          <label className="os-label" style={{ marginTop: 8 }}>
            Default LLM Provider
          </label>
          <select
            className="os-input"
            value={workflowProvider}
            onChange={(e) => setWorkflowProvider(e.target.value)}
          >
            {PROVIDERS.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
          <button className="btn btn-primary" onClick={saveWorkflow} style={{ marginTop: 12 }}>
            💾 Save Workflow
          </button>
        </div>

        <div className="module-widget">
          <h3>Add Node</h3>
          <select
            className="os-input"
            onChange={(e) => {
              if (e.target.value) {
                addNode(e.target.value, "agent");
                e.target.value = "";
              }
            }}
            defaultValue=""
          >
            <option value="">+ Agent node…</option>
            {apps.map((app) => (
              <option key={app.id} value={app.id}>
                {app.icon} {app.name}
              </option>
            ))}
          </select>
          <select
            className="os-input"
            style={{ marginTop: 8 }}
            onChange={(e) => {
              if (e.target.value) {
                addNode(e.target.value, "integration");
                e.target.value = "";
              }
            }}
            defaultValue=""
          >
            <option value="">+ Integration node…</option>
            {integrations.map((i) => (
              <option key={i.id} value={i.id}>
                🔌 {i.name}
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
          <div
            className="workflow-canvas"
            ref={canvasRef}
            style={{ cursor: isPanning ? "grabbing" : "grab" }}
            onWheel={(e) => {
              const zoomFactor = e.deltaY * -0.001;
              const newZoom = Math.min(Math.max(0.2, zoom + zoomFactor), 3);
              if (!canvasRef.current) return;
              const rect = canvasRef.current.getBoundingClientRect();
              const mx = e.clientX - rect.left;
              const my = e.clientY - rect.top;
              const wx = (mx - pan.x) / zoom;
              const wy = (my - pan.y) / zoom;
              setPan({ x: mx - wx * newZoom, y: my - wy * newZoom });
              setZoom(newZoom);
            }}
            onMouseDown={(e) => {
              setIsPanning(true);
              lastPanMouse.current = { x: e.clientX, y: e.clientY };
            }}
            onMouseMove={(e) => {
              if (isPanning) {
                const dx = e.clientX - lastPanMouse.current.x;
                const dy = e.clientY - lastPanMouse.current.y;
                setPan((p) => ({ x: p.x + dx, y: p.y + dy }));
                lastPanMouse.current = { x: e.clientX, y: e.clientY };
                return;
              }
              if (!canvasRef.current) return;
              const rect = canvasRef.current.getBoundingClientRect();
              const mx = e.clientX - rect.left;
              const my = e.clientY - rect.top;
              const wx = (mx - pan.x) / zoom;
              const wy = (my - pan.y) / zoom;
              if (draggingId) {
                setNodes((prev) =>
                  prev.map((n) =>
                    n.id === draggingId
                      ? { ...n, x: wx - dragOffset.current.x, y: wy - dragOffset.current.y }
                      : n
                  )
                );
              } else if (edgeDraggingSource) {
                setMousePos({ x: wx, y: wy });
              }
            }}
            onMouseUp={() => {
              if (draggingId && dragStartSnapshot.current) {
                const oldNodes = dragStartSnapshot.current.nodes;
                const nodeOld = oldNodes.find((n) => n.id === draggingId);
                const nodeNew = nodes.find((n) => n.id === draggingId);
                if (
                  nodeOld &&
                  nodeNew &&
                  (nodeOld.x !== nodeNew.x || nodeOld.y !== nodeNew.y)
                ) {
                  setPast((prev) => [...prev, dragStartSnapshot.current!].slice(-50));
                  setFuture([]);
                }
                dragStartSnapshot.current = null;
              }
              setIsPanning(false);
              setDraggingId(null);
              setEdgeDraggingSource(null);
            }}
            onMouseLeave={() => {
              setIsPanning(false);
              setDraggingId(null);
              setEdgeDraggingSource(null);
            }}
          >
            <div
              className="workflow-world"
              style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }}
            >
            {nodes.map((node) => {
              const app = apps.find((a) => a.id === node.app_id);
              const integration = integrations.find((i) => i.id === node.integration_id);
              const isIntegration = node.type === "integration";
              const traceStatus = nodeTrace[node.id];
              let traceBorderColor = app?.color || "var(--accent, #6366f1)";
              if (traceStatus === "ok") traceBorderColor = "#22c55e";
              else if (traceStatus === "fail") traceBorderColor = "#ef4444";
              else if (traceStatus === "running") traceBorderColor = "#f59e0b";
              return (
                <div
                  key={node.id}
                  className={`workflow-node ${selectedNode === node.id ? "selected" : ""} ${isIntegration ? "integration" : ""} ${traceStatus ? "traced" : ""}`}
                  style={{
                    left: node.x,
                    top: node.y,
                    borderColor: traceBorderColor,
                    boxShadow: traceStatus === "running" ? "0 0 16px rgba(245, 158, 11, 0.5)" : traceStatus === "ok" ? "0 0 12px rgba(34, 197, 94, 0.3)" : undefined,
                  }}
                  onClick={() => setSelectedNode(node.id)}
                  onMouseDown={(e) => {
                    e.stopPropagation();
                    dragStartSnapshot.current = cloneState(currentStateRef.current);
                    setDraggingId(node.id);
                    if (!canvasRef.current) return;
                    const rect = canvasRef.current.getBoundingClientRect();
                    const mx = e.clientX - rect.left;
                    const my = e.clientY - rect.top;
                    const wx = (mx - pan.x) / zoom;
                    const wy = (my - pan.y) / zoom;
                    dragOffset.current = { x: wx - node.x, y: wy - node.y };
                  }}
                  onMouseUp={(e) => {
                    if (edgeDraggingSource && edgeDraggingSource !== node.id) {
                      const exists = edges.some((edge) => edge.source === edgeDraggingSource && edge.target === node.id);
                      if (!exists) {
                        saveSnapshot();
                        setEdges((prev) => [...prev, { source: edgeDraggingSource, target: node.id, condition: "always" }]);
                      }
                    }
                    setEdgeDraggingSource(null);
                    e.stopPropagation();
                  }}
                >
                  <button
                    className="workflow-node-delete"
                    title="Remove node"
                    onClick={(e) => {
                      e.stopPropagation();
                      removeNode(node.id);
                    }}
                  >
                    ×
                  </button>                    <div
                      className="workflow-node-handle"
                      title="Drag to connect"
                      onMouseDown={(e) => {
                        e.stopPropagation();
                        if (!canvasRef.current) return;
                        const rect = canvasRef.current.getBoundingClientRect();
                        const mx = e.clientX - rect.left;
                        const my = e.clientY - rect.top;
                        const wx = (mx - pan.x) / zoom;
                        const wy = (my - pan.y) / zoom;
                        setEdgeDraggingSource(node.id);
                        setMousePos({ x: wx, y: wy });
                      }}
                    />
                  <div className="workflow-node-title">
                    {isIntegration ? `🔌 ${integration?.name || node.integration_id}` : `${app?.icon || ""} ${app?.name || node.app_id}`}
                  </div>
                  <div className="workflow-node-id">{node.id.slice(0, 6)}</div>
                  {traceStatus && (
                    <div className="workflow-node-trace" title={`Status: ${traceStatus}`}>
                      {traceStatus === "ok" ? "✓" : traceStatus === "fail" ? "✗" : "⟳"}
                    </div>
                  )}
                </div>
              );
            })}
            <svg className="workflow-edges">
              {edges.map((edge, i) => {
                const source = nodes.find((n) => n.id === edge.source);
                const target = nodes.find((n) => n.id === edge.target);
                if (!source || !target) return null;
                const x1 = source.x + 90;
                const y1 = source.y + 35;
                const x2 = target.x + 90;
                const y2 = target.y + 35;
                const mx = (x1 + x2) / 2;
                const my = (y1 + y2) / 2;
                const edgeColor =
                  edge.condition === "success"
                    ? "#22c55e"
                    : edge.condition === "failure"
                    ? "#ef4444"
                    : "var(--accent, #6366f1)";
                const markerId = `arrow-${edge.condition || "always"}`;
                return (
                  <g key={i}>
                    <line
                      x1={x1}
                      y1={y1}
                      x2={x2}
                      y2={y2}
                      stroke="transparent"
                      strokeWidth={12}
                      pointerEvents="all"
                      className="workflow-edge-hit"
                    />
                    <line
                      x1={x1}
                      y1={y1}
                      x2={x2}
                      y2={y2}
                      stroke={edgeColor}
                      strokeWidth={2}
                      markerEnd={`url(#${markerId})`}
                      pointerEvents="none"
                    />
                    <g
                      className="workflow-edge-label"
                      transform={`translate(${mx}, ${my - 14})`}
                      pointerEvents="all"
                      onClick={(e) => {
                        e.stopPropagation();
                        saveSnapshot();
                        const nextCond =
                          edge.condition === "always" ? "success" : edge.condition === "success" ? "failure" : "always";
                        updateEdge(i, { condition: nextCond });
                      }}
                    >
                      <rect x="-25" y="-10" width="50" height="20" rx="10" fill={edgeColor} />
                      <text x={0} y={3} textAnchor="middle" fontSize={10} fill="white" fontWeight="bold" pointerEvents="none">
                        {edge.condition}
                      </text>
                    </g>
                    <g
                      className="workflow-edge-delete"
                      transform={`translate(${mx}, ${my + 14})`}
                      pointerEvents="all"
                      onClick={(e) => {
                        e.stopPropagation();
                        removeEdge(i);
                      }}
                    >
                      <circle r={8} fill="var(--danger, #ef4444)" />
                      <text x={0} y={3} textAnchor="middle" fontSize={10} fill="white" pointerEvents="none">
                        ×
                      </text>
                    </g>
                  </g>
                );
              })}
              {(() => {
                if (!edgeDraggingSource) return null;
                const source = nodes.find((n) => n.id === edgeDraggingSource);
                if (!source) return null;
                return (
                  <line
                    x1={source.x + 90}
                    y1={source.y + 35}
                    x2={mousePos.x}
                    y2={mousePos.y}
                    stroke="var(--accent)"
                    strokeWidth={2}
                    strokeDasharray="5,5"
                    markerEnd="url(#arrow)"
                  />
                );
              })()}
              <defs>
                <marker id="arrow-always" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto" markerUnits="strokeWidth">
                  <path d="M0,0 L0,6 L9,3 z" fill="var(--accent, #6366f1)" />
                </marker>
                <marker id="arrow-success" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto" markerUnits="strokeWidth">
                  <path d="M0,0 L0,6 L9,3 z" fill="#22c55e" />
                </marker>
                <marker id="arrow-failure" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto" markerUnits="strokeWidth">
                  <path d="M0,0 L0,6 L9,3 z" fill="#ef4444" />
                </marker>
                <marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto" markerUnits="strokeWidth">
                  <path d="M0,0 L0,6 L9,3 z" fill="var(--accent, #6366f1)" />
                </marker>
              </defs>
            </svg>
            </div>            <div className="workflow-shortcuts">
              <strong>Shortcuts</strong>
              <div>Undo: ⌘Z / Ctrl+Z</div>
              <div>Redo: ⌘⇧Z / Ctrl+Shift+Z</div>
              <div>Zoom: + / −</div>
              <div>Pan: arrows</div>
              <div>Delete: del</div>
              <div>Save: ⌘S / Ctrl+S</div>
              <div>Reset: 0</div>
            </div>
            <div style={{
                position: "absolute",
                bottom: 16,
                right: 16,
                display: "flex",
                gap: 8,
                zIndex: 100,
                userSelect: "none",
                alignItems: "center",
              }}
            >
              <button className="btn btn-sm" onClick={undo} disabled={past.length === 0} title="Undo (⌘Z / Ctrl+Z)">
                ⟲ Undo
              </button>
              <button className="btn btn-sm" onClick={redo} disabled={future.length === 0} title="Redo (⌘⇧Z / Ctrl+Shift+Z)">
                ⟳ Redo
              </button>
              <button className="btn btn-sm" onClick={clearDraft} title="Clear draft">
                🗑️ Clear
              </button>
              <div style={{ width: 1, height: 16, background: "var(--border)", margin: "0 4px" }} />
              <button className="btn btn-sm" onClick={() => setZoom((z) => Math.max(0.2, z - 0.2))}>
                −
              </button>
              <button className="btn btn-sm" onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }}>
                Reset
              </button>
              <button className="btn btn-sm" onClick={() => setZoom((z) => Math.min(3, z + 0.2))}>
                +
              </button>
              <div style={{ fontSize: 12, width: 40, color: "var(--fg-mute)" }}>
                {Math.round(zoom * 100)}%
              </div>
            </div>
            {(() => {
              const padding = 8;
              const mapW = 200;
              const mapH = 150;
              if (nodes.length === 0) {
                return (
                  <div className="workflow-minimap">
                    <span>No nodes</span>
                  </div>
                );
              }
              const xs = nodes.map((n) => n.x);
              const ys = nodes.map((n) => n.y);
              const minX = Math.min(...xs);
              const maxX = Math.max(...xs);
              const minY = Math.min(...ys);
              const maxY = Math.max(...ys);
              const contentW = Math.max(mapW, maxX - minX + 180);
              const contentH = Math.max(mapH, maxY - minY + 70);
              const scale = Math.min((mapW - padding * 2) / contentW, (mapH - padding * 2) / contentH);
              const offsetX = (mapW - (maxX - minX + 180) * scale) / 2;
              const offsetY = (mapH - (maxY - minY + 70) * scale) / 2;
              const toMiniX = (x: number) => (x - minX + 90) * scale + offsetX;
              const toMiniY = (y: number) => (y - minY + 35) * scale + offsetY;
              const canvasW = canvasRef.current?.clientWidth || mapW;
              const canvasH = canvasRef.current?.clientHeight || mapH;
              const viewX = toMiniX(-pan.x / zoom);
              const viewY = toMiniY(-pan.y / zoom);
              const viewW = (canvasW / zoom) * scale;
              const viewH = (canvasH / zoom) * scale;
              return (
                <div
                  className="workflow-minimap"
                  onClick={(e) => {
                    const rect = (e.target as HTMLElement).getBoundingClientRect();
                    const mx = e.clientX - rect.left;
                    const my = e.clientY - rect.top;
                    const wx = (mx - offsetX) / scale + minX - 90;
                    const wy = (my - offsetY) / scale + minY - 35;
                    setPan({ x: -wx * zoom, y: -wy * zoom });
                  }}
                >
                  <svg width={mapW} height={mapH}>
                    <rect x={0} y={0} width={mapW} height={mapH} fill="var(--bg, #1e293b)" opacity={0.8} rx={8} />
                    {edges.map((edge, i) => {
                      const source = nodes.find((n) => n.id === edge.source);
                      const target = nodes.find((n) => n.id === edge.target);
                      if (!source || !target) return null;
                      return (
                        <line
                          key={i}
                          x1={toMiniX(source.x + 90)}
                          y1={toMiniY(source.y + 35)}
                          x2={toMiniX(target.x + 90)}
                          y2={toMiniY(target.y + 35)}
                          stroke="var(--accent, #6366f1)"
                          strokeWidth={1}
                        />
                      );
                    })}
                    {nodes.map((node) => (
                      <rect
                        key={node.id}
                        x={toMiniX(node.x + 90) - 4}
                        y={toMiniY(node.y + 35) - 4}
                        width={8}
                        height={8}
                        rx={2}
                        fill={node.type === "integration" ? "#f59e0b" : "#22c55e"}
                      />
                    ))}
                    <rect
                      x={viewX}
                      y={viewY}
                      width={viewW}
                      height={viewH}
                      fill="none"
                      stroke="white"
                      strokeWidth={1}
                      strokeDasharray="3,3"
                    />
                  </svg>
                </div>
              );
            })()}
          </div>
        </div>

        <div className="module-widget">
          <h3>Node Inspector</h3>
          {selected ? (
            <>
              <div style={{ marginBottom: 8 }}>
                <strong>
                  {selected.type === "integration"
                    ? `🔌 ${integrations.find((i) => i.id === selected.integration_id)?.name || selected.integration_id}`
                    : apps.find((a) => a.id === selected.app_id)?.name || selected.app_id}
                </strong>
                <span className="os-status-pill active" style={{ marginLeft: 8 }}>
                  {selected.type === "integration" ? "integration" : "agent"}
                </span>
              </div>
              {selected.type === "integration" ? (
                <>
                  <label className="os-label">Endpoint</label>
                  <input
                    className="os-input"
                    value={selected.endpoint || ""}
                    onChange={(e) => updateNode(selected.id, { endpoint: e.target.value })}
                    onFocus={handleFocus}
                    onBlur={handleBlur}
                    placeholder="/path or full URL"
                  />
                  <label className="os-label" style={{ marginTop: 8 }}>
                    Method
                  </label>
                  <select
                    className="os-input"
                    value={selected.method || "GET"}
                    onChange={(e) => {
                      saveSnapshot();
                      updateNode(selected.id, { method: e.target.value });
                    }}
                  >
                    <option>GET</option>
                    <option>POST</option>
                    <option>PUT</option>
                    <option>DELETE</option>
                  </select>
                  <label className="os-label" style={{ marginTop: 8 }}>
                    JSON Payload (use {'{input}'} for previous output)
                  </label>
                  <textarea
                    className="os-input"
                    rows={3}
                    value={selected.payload || ""}
                    onChange={(e) => updateNode(selected.id, { payload: e.target.value })}
                    onFocus={handleFocus}
                    onBlur={handleBlur}
                  />
                </>
              ) : (
                <>
                  <label className="os-label">Prompt</label>
                  <textarea
                    className="os-input"
                    rows={4}
                    value={selected.prompt}
                    onChange={(e) => updateNode(selected.id, { prompt: e.target.value })}
                    onFocus={handleFocus}
                    onBlur={handleBlur}
                  />
                  <label className="os-label" style={{ marginTop: 8 }}>
                    LLM Provider Override
                  </label>
                  <select
                    className="os-input"
                    value={selected.provider || ""}
                    onChange={(e) => {
                      saveSnapshot();
                      updateNode(selected.id, { provider: e.target.value || undefined });
                    }}
                  >
                    {PROVIDERS.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                </>
              )}
              <label className="os-label" style={{ marginTop: 8 }}>
                Position X
              </label>
              <input
                type="number"
                className="os-input"
                value={selected.x}
                onChange={(e) => updateNode(selected.id, { x: Number(e.target.value) })}
                onFocus={handleFocus}
                onBlur={handleBlur}
              />
              <label className="os-label" style={{ marginTop: 8 }}>
                Position Y
              </label>
              <input
                type="number"
                className="os-input"
                value={selected.y}
                onChange={(e) => updateNode(selected.id, { y: Number(e.target.value) })}
                onFocus={handleFocus}
                onBlur={handleBlur}
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
                </small>                  <select
                  className="os-input"
                  value={edge.condition}
                  onChange={(e) => {
                    saveSnapshot();
                    updateEdge(i, { condition: e.target.value });
                  }}
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
          {runResult.summary ? (
            <div className="run-summary">
              <div className="run-summary-bar">
                <span className="run-summary-ok">✓ {runResult.summary.ok_nodes} succeeded</span>
                {runResult.summary.failed_nodes > 0 && (
                  <span className="run-summary-fail">✗ {runResult.summary.failed_nodes} failed</span>
                )}
                <span className="run-summary-total">{runResult.summary.total_nodes} nodes</span>
                <span className="run-summary-latency">
                  {runResult.summary.total_latency_s.toFixed(2)}s total
                </span>
                {runResult.provider && (
                  <span className="run-summary-provider">Provider: {runResult.provider}</span>
                )}
                {runResult.workspace_id && (
                  <span className="run-summary-workspace">Workspace: {runResult.workspace_id.slice(0, 8)}</span>
                )}
              </div>
              {runResult.results && (
                <div className="run-results-list">
                  {runResult.results.map((r: any, i: number) => (
                    <div key={i} className={`run-result-item ${r.ok ? "ok" : "fail"}`}>
                      <div className="run-result-header">
                        <span className={`run-result-status ${r.ok ? "ok" : "fail"}`}>
                          {r.ok ? "✓" : "✗"}
                        </span>
                        <span className="run-result-app">{r.app_id}</span>
                        {r.provider && <span className="run-result-provider">{r.provider}</span>}
                        {r.latency_s !== undefined && (
                          <span className="run-result-latency">{r.latency_s.toFixed(2)}s</span>
                        )}
                      </div>
                      {!r.ok && r.error && (
                        <div className="run-result-error">{r.error}</div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <pre className="os-pre">{JSON.stringify(runResult, null, 2)}</pre>
          )}
        </section>
      )}
    </div>
  );
}
