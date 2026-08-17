"use client";

import React, { useState, useEffect, useCallback, useRef, forwardRef } from "react";
import ErrorState from "@/components/ui/ErrorState";
import { isBackendDownError } from "@/lib/backend-status";

// ── Types ────────────────────────────────────────────────────────────────

type SwarmRole = "planner" | "executor" | "reviewer" | "summarizer";
type SwarmPhase =
  "pending" | "planning" | "executing" | "reflecting" | "summarizing" | "done" | "failed";

interface SwarmTaskResult {
  id: string;
  description: string;
  status: string;
  assigned_to: string | null;
  output: string;
}

interface SwarmResult {
  ok: boolean;
  swarm_id: string;
  prompt: string;
  agents: string[];
  roles: Record<string, string>;
  tasks: SwarmTaskResult[];
  results: Record<string, { ok: boolean; output?: string; error?: string }>;
  reflection: { agent: string | null; answer: string; error?: string };
  summary: string;
  evolution_suggestions: string[];
  error?: string;
}

interface SwarmStatusResponse {
  ok: boolean;
  swarm_id: string;
  running: Record<string, unknown> | null;
  message_count: number;
  task_count: number;
}

interface SwarmMessageItem {
  sender: string;
  recipient: string;
  content: string;
  msg_type: string;
  timestamp: number;
}

interface SwarmWithPhase extends SwarmResult {
  phase: SwarmPhase;
  phaseStartedAt?: number;
  error?: string;
}

// ── Timeline Event Types ────────────────────────────────────────────────

interface SwarmTimelineEvent {
  id: string;
  timestamp: number;
  duration?: number; // ms from previous event
  label: string;
  description: string;
  icon: string;
  category:
    "lifecycle" | "phase" | "task" | "message" | "reflection" | "summary" | "evolution" | "error";
  status: "pending" | "active" | "done" | "error";
  meta?: Record<string, string>;
}

// ── Constants ────────────────────────────────────────────────────────────

const ROLE_OPTIONS: { id: SwarmRole; label: string; icon: string; color: string; desc: string }[] =
  [
    {
      id: "planner",
      label: "Planner",
      icon: "📋",
      color: "#6366f1",
      desc: "Breaks tasks into actionable plans",
    },
    {
      id: "executor",
      label: "Executor",
      icon: "⚡",
      color: "#22c55e",
      desc: "Carries out assigned tasks",
    },
    {
      id: "reviewer",
      label: "Reviewer",
      icon: "🔍",
      color: "#f59e0b",
      desc: "Reflects on outputs for quality",
    },
    {
      id: "summarizer",
      label: "Summarizer",
      icon: "📝",
      color: "#06b6d4",
      desc: "Synthesizes into final answer",
    },
  ];

const ROLE_ICONS: Record<string, string> = {
  planner: "📋",
  executor: "⚡",
  reviewer: "🔍",
  summarizer: "📝",
};

const ROLE_COLORS: Record<string, string> = {
  planner: "#6366f1",
  executor: "#22c55e",
  reviewer: "#f59e0b",
  summarizer: "#06b6d4",
};

const PHASE_CONFIG: Record<SwarmPhase, { label: string; icon: string; color: string }> = {
  pending: { label: "Pending", icon: "⏳", color: "#94a3b8" },
  planning: { label: "Planning", icon: "📋", color: "#6366f1" },
  executing: { label: "Executing", icon: "⚡", color: "#22c55e" },
  reflecting: { label: "Reflecting", icon: "🔍", color: "#f59e0b" },
  summarizing: { label: "Summarizing", icon: "📝", color: "#06b6d4" },
  done: { label: "Completed", icon: "✅", color: "#22c55e" },
  failed: { label: "Failed", icon: "❌", color: "#ef4444" },
};

const CATEGORY_ICONS: Record<string, string> = {
  lifecycle: "🔵",
  phase: "🔄",
  task: "📋",
  message: "💬",
  reflection: "🔍",
  summary: "📝",
  evolution: "🧬",
  error: "❌",
};

const CATEGORY_COLORS: Record<string, string> = {
  lifecycle: "#6366f1",
  phase: "#8b5cf6",
  task: "#22c55e",
  message: "#06b6d4",
  reflection: "#f59e0b",
  summary: "#06b6d4",
  evolution: "#a855f7",
  error: "#ef4444",
};

// ── Helpers ──────────────────────────────────────────────────────────────

function formatTime(ts: number): string {
  const diff = Date.now() - ts * 1000;
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  const secs = Math.floor(ms / 1000);
  if (secs < 60) return `${secs}.${Math.floor((ms % 1000) / 100)}s`;
  const mins = Math.floor(secs / 60);
  return `${mins}m ${secs % 60}s`;
}

function formatAbsoluteTime(ts: number): string {
  const d = new Date(ts * 1000);
  return (
    d.toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    }) + `.${String(d.getMilliseconds()).padStart(3, "0")}`
  );
}

function isRunning(phase: SwarmPhase): boolean {
  return !["done", "failed"].includes(phase);
}

// ── Spinner Component ────────────────────────────────────────────────────

function SwarmSpinner({ color = "#6366f1", size = 20 }: { color?: string; size?: number }) {
  return (
    <svg
      className="swarm-spinner"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      style={{ color }}
    >
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.2" />
      <path
        d="M12 2a10 10 0 0 1 10 10"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
        strokeDasharray="31.4 31.4"
      />
    </svg>
  );
}

// ── Phase Progress Bar ───────────────────────────────────────────────────

function PhaseProgressBar({ currentPhase }: { currentPhase: SwarmPhase }) {
  const phases: SwarmPhase[] = ["planning", "executing", "reflecting", "summarizing"];
  const currentIdx = phases.indexOf(currentPhase);

  return (
    <div className="swarm-phase-bar">
      {phases.map((phase, idx) => {
        const cfg = PHASE_CONFIG[phase];
        const completed = idx < currentIdx;
        const active = idx === currentIdx;
        return (
          <div key={phase} className="swarm-phase-step">
            <div
              className={`swarm-phase-dot ${completed ? "done" : active ? "active" : "pending"}`}
              style={{
                borderColor: cfg.color,
                background: completed || active ? cfg.color : undefined,
              }}
            >
              {active ? <SwarmSpinner color="#fff" size={14} /> : completed ? "✓" : idx + 1}
            </div>
            <div
              className="swarm-phase-label"
              style={{ color: active || completed ? cfg.color : undefined }}
            >
              {cfg.label}
            </div>
          </div>
        );
      })}
      <div
        className="swarm-phase-connector"
        style={{ background: currentIdx >= 0 ? "var(--accent)" : undefined }}
      />
    </div>
  );
}

// ── Live Timer ───────────────────────────────────────────────────────────

function LiveTimer({ startTs }: { startTs: number }) {
  const [elapsed, setElapsed] = useState("0s");
  useEffect(() => {
    const t = setInterval(() => setElapsed(formatDuration(Date.now() - startTs * 1000)), 1000);
    return () => clearInterval(t);
  }, [startTs]);
  return <span className="swarm-live-timer">{elapsed}</span>;
}

// ── Swarm Timeline Component ────────────────────────────────────────────

function SwarmTimeline({ events, running }: { events: SwarmTimelineEvent[]; running: boolean }) {
  const timelineRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to latest event
  useEffect(() => {
    if (timelineRef.current && running) {
      timelineRef.current.scrollTop = timelineRef.current.scrollHeight;
    }
  }, [events.length, running]);

  return (
    <div className="swarm-timeline-container" ref={timelineRef}>
      {events.length === 0 ? (
        <div className="swarm-timeline-empty">
          <SwarmSpinner color="#6366f1" size={16} />
          <span>Recording execution timeline...</span>
        </div>
      ) : (
        <div className="swarm-timeline">
          {/* Timeline vertical line */}
          <div className="swarm-timeline-line" />

          {/* Group events by second for compact display */}
          {(() => {
            const grouped: SwarmTimelineEvent[][] = [];
            let currentGroup: SwarmTimelineEvent[] = [];
            let lastTs = 0;
            for (const evt of events) {
              if (lastTs && evt.timestamp - lastTs > 1.5) {
                if (currentGroup.length > 0) {
                  grouped.push(currentGroup);
                  currentGroup = [];
                }
              }
              currentGroup.push(evt);
              lastTs = evt.timestamp;
            }
            if (currentGroup.length > 0) grouped.push(currentGroup);
            return grouped;
          })().map((group, gi) => (
            <div key={gi} className="swarm-timeline-group">
              {group.map((evt, ei) => {
                const catColor = CATEGORY_COLORS[evt.category] || "#6366f1";
                const isLatest =
                  running &&
                  ei === group.length - 1 &&
                  gi ===
                    (() => {
                      const g = ([] as SwarmTimelineEvent[][]).concat(...[]);
                      return 0;
                    })();
                return (
                  <div
                    key={evt.id}
                    className={`swarm-timeline-event ${evt.status}`}
                    style={{ "--event-color": catColor } as React.CSSProperties}
                  >
                    {/* Timeline dot */}
                    <div
                      className="swarm-timeline-dot"
                      style={{
                        borderColor: catColor,
                        background: evt.status === "done" ? catColor : undefined,
                      }}
                    >
                      {evt.status === "active" ? (
                        <SwarmSpinner color="#fff" size={10} />
                      ) : evt.status === "done" ? (
                        "✓"
                      ) : evt.status === "error" ? (
                        "✗"
                      ) : (
                        <span style={{ fontSize: 8 }}>{evt.icon}</span>
                      )}
                    </div>

                    {/* Event content */}
                    <div
                      className="swarm-timeline-content"
                      style={evt.status === "active" ? { borderColor: catColor } : {}}
                    >
                      <div className="swarm-timeline-header">
                        <span className="swarm-timeline-icon">{evt.icon}</span>
                        <span className="swarm-timeline-label">{evt.label}</span>
                        <span
                          className="swarm-timeline-badge"
                          style={{ background: `${catColor}18`, color: catColor }}
                        >
                          {evt.category}
                        </span>
                      </div>
                      <div className="swarm-timeline-desc">{evt.description}</div>
                      <div className="swarm-timeline-footer">
                        <span
                          className="swarm-timeline-time"
                          title={new Date(evt.timestamp * 1000).toISOString()}
                        >
                          ⏱ {formatAbsoluteTime(evt.timestamp)}
                        </span>
                        {evt.duration !== undefined && (
                          <span className="swarm-timeline-duration">
                            ─ {formatDuration(evt.duration)}
                          </span>
                        )}
                        {evt.meta &&
                          Object.entries(evt.meta).map(([k, v]) => (
                            <span key={k} className="swarm-timeline-meta">
                              {k}: {v}
                            </span>
                          ))}
                        {evt.status === "active" && (
                          <span
                            className="swarm-live-indicator"
                            style={{ marginLeft: "auto", fontSize: "0.65rem" }}
                          >
                            <SwarmSpinner color="#22c55e" size={8} />
                            In Progress
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Timeline event generation hook ──────────────────────────────────────

let _eventCounter = 0;
function nextEventId(): string {
  _eventCounter += 1;
  return `evt-${Date.now()}-${_eventCounter}`;
}

function generateTimelineEvents(
  swarm: SwarmWithPhase,
  messages: SwarmMessageItem[],
  previousEvents: SwarmTimelineEvent[],
  swarmCreationTime: number
): SwarmTimelineEvent[] {
  const events: SwarmTimelineEvent[] = [];
  const lastTs =
    previousEvents.length > 0
      ? previousEvents[previousEvents.length - 1].timestamp
      : swarmCreationTime;

  // Helper to add an event if it doesn't exist yet
  const addEvent = (opts: {
    label: string;
    description: string;
    icon: string;
    category: SwarmTimelineEvent["category"];
    status: SwarmTimelineEvent["status"];
    meta?: Record<string, string>;
    forceTs?: number;
  }) => {
    const exists = previousEvents.some(
      (e) => e.label === opts.label && e.category === opts.category
    );
    if (exists) return;
    const ts = opts.forceTs || Math.max(lastTs + 0.1, Date.now() / 1000);
    const duration =
      events.length > 0 ? Math.round((ts - events[events.length - 1].timestamp) * 1000) : undefined;
    events.push({
      id: nextEventId(),
      timestamp: ts,
      duration,
      ...opts,
    });
  };

  // 1. Swarm created event (always first)
  if (previousEvents.length === 0) {
    addEvent({
      label: "Swarm Created",
      description: `Swarm #${swarm.swarm_id} launched with ${swarm.agents.length} agents`,
      icon: "🐝",
      category: "lifecycle",
      status: "done",
      meta: {
        agents: String(swarm.agents.length),
        prompt: swarm.prompt.slice(0, 60) + (swarm.prompt.length > 60 ? "..." : ""),
      },
      forceTs: swarmCreationTime,
    });
  }

  // 2. Phase-based events
  if (
    swarm.phase === "planning" ||
    swarm.phase === "executing" ||
    swarm.phase === "reflecting" ||
    swarm.phase === "summarizing"
  ) {
    addEvent({
      label: `Phase: ${PHASE_CONFIG[swarm.phase].label}`,
      description: `Swarm entered the ${swarm.phase} phase`,
      icon: PHASE_CONFIG[swarm.phase].icon,
      category: "phase",
      status: "active",
    });
  }

  // 3. Task events from task results
  if (swarm.tasks.length > 0) {
    for (const task of swarm.tasks) {
      const cat = task.description.split(":")[0]?.trim()?.toLowerCase() || "task";
      addEvent({
        label: `Task: ${task.id}`,
        description: task.description,
        icon: ROLE_ICONS[cat] || "📋",
        category: "task",
        status: task.status === "done" ? "done" : task.status === "failed" ? "error" : "active",
        meta: task.assigned_to ? { assigned: task.assigned_to } : undefined,
      });
    }
  }

  // 4. Reflection event
  if (swarm.reflection?.answer) {
    addEvent({
      label: "Reflection Complete",
      description: `Reviewed by ${swarm.reflection.agent || "unknown"} — ${swarm.reflection.answer.slice(0, 100)}${swarm.reflection.answer.length > 100 ? "..." : ""}`,
      icon: "🔍",
      category: "reflection",
      status: "done",
      meta: swarm.reflection.agent ? { reviewer: swarm.reflection.agent } : undefined,
    });
  }

  // 5. Summary event
  if (swarm.summary) {
    addEvent({
      label: "Summary Generated",
      description: swarm.summary.slice(0, 120) + (swarm.summary.length > 120 ? "..." : ""),
      icon: "📝",
      category: "summary",
      status: "done",
    });
  }

  // 6. Evolution suggestions
  if (swarm.evolution_suggestions && swarm.evolution_suggestions.length > 0) {
    swarm.evolution_suggestions.forEach((_, i) => {
      addEvent({
        label: `Evolution Suggestion #${i + 1}`,
        description: `Tool improvement suggestion extracted from reviewer output`,
        icon: "🧬",
        category: "evolution",
        status: "done",
      });
    });
  }

  // 7. Message events (last N)
  if (messages.length > 0) {
    const recentMsgs = messages.slice(-5);
    for (const msg of recentMsgs) {
      addEvent({
        label: `Message: ${msg.sender} → ${msg.recipient}`,
        description: msg.content.slice(0, 120) + (msg.content.length > 120 ? "..." : ""),
        icon: "💬",
        category: "message",
        status: "done",
        meta: { type: msg.msg_type },
        forceTs: msg.timestamp,
      });
    }
  }

  // 8. Completion event
  if (swarm.phase === "done") {
    addEvent({
      label: "Swarm Completed",
      description: `All ${swarm.tasks.length} tasks finished successfully`,
      icon: "✅",
      category: "lifecycle",
      status: "done",
      meta: {
        tasks: String(swarm.tasks.length),
        results: String(Object.keys(swarm.results).length),
      },
    });
  }

  if (swarm.phase === "failed" || swarm.error) {
    addEvent({
      label: "Swarm Failed",
      description: swarm.error || "An error occurred during execution",
      icon: "❌",
      category: "error",
      status: "error",
    });
  }

  // Return events sorted by timestamp
  return events.sort((a, b) => a.timestamp - b.timestamp);
}

// ── Graph Ref for export access ──────────────────────────────────────────
const graphExportRef = { current: null as HTMLDivElement | null };

// ── Export Utilities ─────────────────────────────────────────────────────

async function exportGraphSVG(wrapper: HTMLDivElement): Promise<void> {
  const svg = wrapper.querySelector("svg");
  if (!svg) return;
  const clone = svg.cloneNode(true) as SVGElement;
  clone
    .querySelectorAll(
      ".swarm-graph-pulse-dot, .swarm-graph-node-active, .swarm-graph-edge-msg, .swarm-graph-edge-dep, .swarm-graph-edge-task, .swarm-graph-task-active"
    )
    .forEach((el) => {
      el.classList.remove(
        "swarm-graph-pulse-dot",
        "swarm-graph-node-active",
        "swarm-graph-edge-msg",
        "swarm-graph-edge-dep",
        "swarm-graph-edge-task",
        "swarm-graph-task-active"
      );
    });
  // Remove filter references that depend on document-level defs
  clone.querySelectorAll("[filter]").forEach((el) => el.removeAttribute("filter"));
  const serializer = new XMLSerializer();
  const svgStr = serializer.serializeToString(clone);
  const blob = new Blob([svgStr], { type: "image/svg+xml;charset=utf-8" });
  downloadBlob(blob, "swarm-graph.svg");
}

async function exportGraphPNG(wrapper: HTMLDivElement): Promise<void> {
  const svg = wrapper.querySelector("svg");
  if (!svg) return;
  const serializer = new XMLSerializer();
  const svgStr = serializer.serializeToString(svg);
  const canvas = document.createElement("canvas");
  const svgRect = svg.getBoundingClientRect();
  const scale = 2;
  canvas.width = (svgRect.width || 400) * scale;
  canvas.height = (svgRect.height || 200) * scale;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  ctx.scale(scale, scale);
  const img = new Image();
  const blob = new Blob([svgStr], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  await new Promise<void>((resolve, reject) => {
    img.onload = () => {
      ctx.drawImage(img, 0, 0);
      URL.revokeObjectURL(url);
      canvas.toBlob((b) => {
        if (b) downloadBlob(b, "swarm-graph.png");
        resolve();
      }, "image/png");
    };
    img.onerror = reject;
    img.src = url;
  });
}

function shareSwarmLink(swarmId: string): void {
  const url = new URL(window.location.href);
  url.searchParams.set("swarm", swarmId);
  navigator.clipboard.writeText(url.toString()).then(() => {
    // Brief flash feedback is handled by the toolbar state
  });
}

function downloadBlob(blob: Blob, filename: string): void {
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(link.href);
}

// ── Graph Visualization ───────────────────────────────────────────────────

const SwarmGraph = forwardRef<
  HTMLDivElement,
  {
    swarm: SwarmWithPhase;
    messages: SwarmMessageItem[];
    running: boolean;
  }
>(({ swarm, messages, running }, ref) => {
  const agents = swarm.agents;
  const roleMap = swarm.roles;
  const tasks = swarm.tasks;
  const phase = swarm.phase;

  // Layout constants
  const AGENT_W = 120;
  const AGENT_H = 56;
  const TASK_W = 100;
  const TASK_H = 34;
  const GX = 32;
  const GY_TOP = 20;
  const GY_AGENT = GY_TOP + AGENT_H + 10;
  const GY_TASK = GY_AGENT + 40;
  const PADDING = 24;

  const numAgents = agents.length;
  const totalTasks = tasks.length;
  const totalAgentWidth = numAgents * AGENT_W + (numAgents - 1) * GX;
  const svgW = Math.max(totalAgentWidth + PADDING * 2, 400);
  const svgH = GY_TASK + TASK_H + 60;

  // Agent positions
  const agentPositions = agents.map((_, i) => ({
    x: PADDING + i * (AGENT_W + GX) + AGENT_W / 2,
    y: GY_TOP + AGENT_H / 2,
  }));

  // Task positions: group under assigned agent
  const tasksByAgent: Record<string, { task: SwarmTaskResult; idx: number }[]> = {};
  tasks.forEach((t) => {
    const a = t.assigned_to || "unassigned";
    if (!tasksByAgent[a]) tasksByAgent[a] = [];
    tasksByAgent[a].push({ task: t, idx: tasksByAgent[a].length });
  });

  // Message pairs for edge drawing
  const msgPairs = new Map<string, number>();
  messages.forEach((m) => {
    const key = `${m.sender}→${m.recipient}`;
    msgPairs.set(key, (msgPairs.get(key) || 0) + 1);
  });

  // Role dependency order
  const roleOrder: string[] = ["planner", "executor", "reviewer", "summarizer"];
  const roleSequence = roleOrder
    .map((r) => agents.find((a) => roleMap[a] === r))
    .filter(Boolean) as string[];

  return (
    <div className="swarm-graph-wrapper" ref={ref}>
      <svg width={svgW} height={svgH} viewBox={`0 0 ${svgW} ${svgH}`} className="swarm-graph-svg">
        <defs>
          {/* Arrow marker for edges */}
          <marker id="arrow-msg" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
            <polygon points="0,0 8,3 0,6" fill="#06b6d4" />
          </marker>
          <marker id="arrow-dep" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
            <polygon points="0,0 8,3 0,6" fill="#6366f1" />
          </marker>
          <marker
            id="arrow-task"
            markerWidth="6"
            markerHeight="5"
            refX="6"
            refY="2.5"
            orient="auto"
          >
            <polygon points="0,0 6,2.5 0,5" fill="#475569" />
          </marker>
          {/* Glow filter for active nodes */}
          <filter id="glow">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* ── Background grid ── */}
        <rect width={svgW} height={svgH} fill="#0f172a" rx="10" />
        <line
          x1={PADDING}
          y1={GY_AGENT}
          x2={svgW - PADDING}
          y2={GY_AGENT}
          stroke="#1e293b"
          strokeWidth="1"
          strokeDasharray="4,4"
        />
        <text x={PADDING} y={GY_AGENT - 4} fill="#475569" fontSize="9" fontFamily="monospace">
          Agents
        </text>
        <text x={PADDING} y={GY_TASK - 4} fill="#475569" fontSize="9" fontFamily="monospace">
          Tasks
        </text>

        {/* ── Role dependency arrows (planner → executor → reviewer → summarizer) ── */}
        {roleSequence.length >= 2 &&
          roleSequence.map((a, i) => {
            if (i === roleSequence.length - 1) return null;
            const from = agentPositions[agents.indexOf(a)];
            const to = agentPositions[agents.indexOf(roleSequence[i + 1])];
            if (!from || !to) return null;
            const cx = (from.x + to.x) / 2;
            return (
              <g key={`dep-${i}`}>
                <path
                  d={`M ${from.x} ${from.y + AGENT_H / 2} Q ${from.x} ${GY_AGENT + 10} ${cx} ${GY_AGENT + 10} L ${to.x} ${to.y + AGENT_H / 2}`}
                  fill="none"
                  stroke="#6366f1"
                  strokeWidth="1.5"
                  strokeDasharray="4,3"
                  markerEnd="url(#arrow-dep)"
                  className={running ? "swarm-graph-edge-dep" : ""}
                  opacity={0.6}
                />
                <text
                  x={cx}
                  y={GY_AGENT + 6}
                  fill="#6366f1"
                  fontSize="8"
                  textAnchor="middle"
                  fontFamily="monospace"
                  opacity={0.7}
                >
                  {roleOrder[i]} →
                </text>
              </g>
            );
          })}

        {/* ── Message flow edges between agents ── */}
        {Array.from(msgPairs.entries()).map(([key, count], i) => {
          const [sender, recipient] = key.split("→");
          const si = agents.indexOf(sender);
          const ri = agents.indexOf(recipient);
          if (si === -1 || ri === -1 || si >= ri) return null;
          const from = agentPositions[si];
          const to = agentPositions[ri];
          if (!from || !to) return null;
          const midX = (from.x + to.x) / 2;
          const arcY = from.y - 22 - i * 16;
          const active = running && phase !== "done";
          return (
            <g key={`msg-${i}`}>
              <path
                d={`M ${from.x} ${from.y - AGENT_H / 2} Q ${from.x} ${arcY} ${midX} ${arcY} Q ${to.x} ${arcY} ${to.x} ${to.y - AGENT_H / 2}`}
                fill="none"
                stroke={active ? "#22c55e" : "#06b6d4"}
                strokeWidth={active ? 2 : 1.5}
                markerEnd="url(#arrow-msg)"
                className={active ? "swarm-graph-edge-msg" : ""}
                opacity={active ? 0.9 : 0.45}
              />
              <circle
                cx={midX}
                cy={arcY}
                r={3}
                fill={active ? "#22c55e" : "#06b6d4"}
                opacity={0.6}
              />
              <text
                x={midX}
                y={arcY - 6}
                fill="#06b6d4"
                fontSize="8"
                textAnchor="middle"
                fontFamily="monospace"
                opacity={0.8}
              >
                {count} msg
              </text>
            </g>
          );
        })}

        {/* ── Task assignment edges ── */}
        {tasks.map((task) => {
          const assignedTo = task.assigned_to || "unassigned";
          const ai = agents.indexOf(assignedTo);
          if (ai === -1) return null;
          const agentPos = agentPositions[ai];
          const agentTasks = tasksByAgent[assignedTo] || [];
          const taskIdx = agentTasks.findIndex((t) => t.task.id === task.id);
          const taskCount = agentTasks.length;
          const startX = agentPos.x - ((taskCount - 1) * (TASK_W + 8)) / 2 + taskIdx * (TASK_W + 8);
          const taskX = startX + TASK_W / 2;
          const isActive = running && task.status === "running";
          return (
            <line
              key={`assign-${task.id}`}
              x1={agentPos.x}
              y1={agentPos.y + AGENT_H / 2 + 2}
              x2={taskX}
              y2={GY_TASK - 2}
              stroke={isActive ? "#22c55e" : "#475569"}
              strokeWidth={isActive ? 1.5 : 1}
              strokeDasharray={isActive ? "none" : "4,3"}
              markerEnd="url(#arrow-task)"
              className={isActive ? "swarm-graph-edge-task" : ""}
              opacity={isActive ? 0.8 : 0.35}
            />
          );
        })}

        {/* ── Agent nodes ── */}
        {agents.map((agent, i) => {
          const role = roleMap[agent] || "executor";
          const color = ROLE_COLORS[role] || "#6366f1";
          const icon = ROLE_ICONS[role] || "🤖";
          const pos = agentPositions[i];
          const isActive = running && role === phase;
          return (
            <g
              key={`agent-${agent}`}
              className="swarm-graph-agent"
              transform={`translate(${pos.x - AGENT_W / 2}, ${pos.y - AGENT_H / 2})`}
            >
              {/* Node background */}
              <rect
                width={AGENT_W}
                height={AGENT_H}
                rx="10"
                fill={isActive ? `${color}18` : "#1e293b"}
                stroke={isActive ? color : "#334155"}
                strokeWidth={isActive ? 2 : 1}
                className={
                  (isActive ? "swarm-graph-node-active" : "") +
                  (running && phase === "done" ? " swarm-graph-node-done" : "")
                }
                filter={isActive ? "url(#glow)" : undefined}
              />
              {/* Role icon */}
              <text x={14} y={20} fontSize="18" textAnchor="middle" dominantBaseline="central">
                {isActive ? "⚡" : icon}
              </text>
              {/* Agent name */}
              <text
                x={30}
                y={20}
                fill="#f1f5f9"
                fontSize="11"
                fontWeight="600"
                fontFamily="sans-serif"
              >
                {agent.length > 12 ? agent.slice(0, 10) + "…" : agent}
              </text>
              {/* Role badge */}
              <rect x={12} y={32} width={AGENT_W - 24} height={16} rx="4" fill={`${color}18`} />
              <text
                x={AGENT_W / 2}
                y={40}
                fill={color}
                fontSize="9"
                fontWeight="600"
                textAnchor="middle"
                fontFamily="monospace"
                style={{ textTransform: "uppercase" }}
              >
                {role}
              </text>
              {/* Status dot */}
              {isActive && (
                <circle
                  cx={AGENT_W - 12}
                  cy={12}
                  r={4}
                  fill="#22c55e"
                  className="swarm-graph-pulse-dot"
                />
              )}
            </g>
          );
        })}

        {/* ── Task nodes ── */}
        {(() => {
          const rows: JSX.Element[] = [];
          const agentKeys = Object.keys(tasksByAgent);
          agentKeys.forEach((agent) => {
            const tlist = tasksByAgent[agent];
            const ai = agents.indexOf(agent);
            const agentPos = ai >= 0 ? agentPositions[ai] : null;
            tlist.forEach(({ task, idx }) => {
              const taskCount = tlist.length;
              let taskX: number;
              if (agentPos) {
                const startX = agentPos.x - ((taskCount - 1) * (TASK_W + 8)) / 2;
                taskX = startX + idx * (TASK_W + 8);
              } else {
                taskX = PADDING + idx * (TASK_W + 8);
              }
              const isActive = running && task.status === "running";
              const done = task.status === "done";
              rows.push(
                <g
                  key={`task-${task.id}`}
                  className="swarm-graph-task"
                  transform={`translate(${taskX}, ${GY_TASK})`}
                >
                  <rect
                    width={TASK_W}
                    height={TASK_H}
                    rx="6"
                    fill={done ? "#22c55e12" : isActive ? "#f59e0b12" : "#0f172a"}
                    stroke={done ? "#22c55e" : isActive ? "#f59e0b" : "#1e293b"}
                    strokeWidth={isActive ? 2 : 1}
                    className={
                      isActive ? "swarm-graph-task-active" : done ? "swarm-graph-task-done" : ""
                    }
                  />
                  {/* Task icon */}
                  <text
                    x={8}
                    y={TASK_H / 2 + 1}
                    fontSize="10"
                    textAnchor="middle"
                    dominantBaseline="central"
                  >
                    {done ? "✓" : isActive ? "⏳" : "○"}
                  </text>
                  {/* Task ID */}
                  <text
                    x={18}
                    y={TASK_H / 2 + 1}
                    fill={done ? "#22c55e" : isActive ? "#f59e0b" : "#94a3b8"}
                    fontSize="8"
                    fontFamily="monospace"
                    dominantBaseline="central"
                  >
                    {task.id.length > 8 ? task.id.slice(0, 6) + "…" : task.id}
                  </text>
                  {/* Status indicator */}
                  {isActive && (
                    <circle
                      cx={TASK_W - 8}
                      cy={TASK_H / 2}
                      r={3}
                      fill="#f59e0b"
                      className="swarm-graph-pulse-dot"
                    />
                  )}
                </g>
              );
            });
          });
          return rows;
        })()}

        {/* ── Legend ── */}
        <g transform={`translate(${PADDING}, ${svgH - 22})`}>
          <rect x={0} y={-2} width={200} height={16} rx="4" fill="#1e293b88" />
          <circle cx={10} cy={6} r={3} fill="#6366f1" className="swarm-graph-pulse-dot" />
          <text x={18} y={8} fill="#94a3b8" fontSize="8" fontFamily="monospace">
            Active
          </text>
          <line
            x1={58}
            y1={6}
            x2={78}
            y2={6}
            stroke="#6366f1"
            strokeWidth="1.5"
            strokeDasharray="4,3"
            opacity={0.5}
          />
          <text x={82} y={8} fill="#94a3b8" fontSize="8" fontFamily="monospace">
            Dependency
          </text>
          <line
            x1={160}
            y1={6}
            x2={180}
            y2={6}
            stroke="#06b6d4"
            strokeWidth="1.5"
            markerEnd="url(#arrow-msg)"
            opacity={0.5}
          />
          <text x={184} y={8} fill="#94a3b8" fontSize="8" fontFamily="monospace">
            Message
          </text>
        </g>
      </svg>
    </div>
  );
});

SwarmGraph.displayName = "SwarmGraph";

// ── Main Swarm Page ──────────────────────────────────────────────────────

export default function SwarmsPage() {
  const [swarms, setSwarms] = useState<SwarmWithPhase[]>([]);
  const [selectedSwarm, setSelectedSwarm] = useState<SwarmWithPhase | null>(null);
  const [swarmMessages, setSwarmMessages] = useState<SwarmMessageItem[]>([]);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [timelineEvents, setTimelineEvents] = useState<SwarmTimelineEvent[]>([]);
  const selectedRef = useRef<HTMLDivElement>(null);
  const newSwarmRef = useRef<string | null>(null);
  const swarmCreationTimes = useRef<Record<string, number>>({});
  const prevTimelineKey = useRef<string>("");
  const graphRef = useRef<HTMLDivElement>(null);
  const [exportMsg, setExportMsg] = useState<string | null>(null);

  // Create form state
  const [formOpen, setFormOpen] = useState(false);
  const [agentInput, setAgentInput] = useState("researcher, writer, reviewer, editor");
  const [prompt, setPrompt] = useState("");
  const [roles, setRoles] = useState<Record<string, SwarmRole>>({
    researcher: "planner",
    writer: "executor",
    reviewer: "reviewer",
    editor: "summarizer",
  });

  // ── Create swarm ─────────────────────────────────────────────────────
  const createSwarm = async () => {
    const appIds = agentInput
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    if (appIds.length === 0 || !prompt.trim()) return;

    setCreating(true);
    setError(null);
    try {
      const res = await fetch("/api/swarm/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ app_ids: appIds, prompt: prompt.trim(), roles }),
      });
      const data: SwarmResult = await res.json();
      if (data.ok) {
        const created = Date.now() / 1000;
        swarmCreationTimes.current[data.swarm_id] = created;
        const swarmWithPhase: SwarmWithPhase = {
          ...data,
          phase: "planning",
          phaseStartedAt: created,
        };
        newSwarmRef.current = swarmWithPhase.swarm_id;
        setSwarms((prev) => [swarmWithPhase, ...prev]);
        setSelectedSwarm(swarmWithPhase);
        setFormOpen(false);
        setPrompt("");
      } else {
        setError(data.error || "swarm failed");
      }
    } catch (e: any) {
      setError(e.message || "request failed");
    } finally {
      setCreating(false);
    }
  };

  // ── Fetch swarm status + messages ────────────────────────────────────
  const fetchSwarmDetail = useCallback(async (swarm: SwarmWithPhase) => {
    try {
      const [statusRes, messagesRes] = await Promise.all([
        fetch(`/api/swarm/${swarm.swarm_id}`),
        fetch(`/api/swarm/${swarm.swarm_id}/messages`),
      ]);
      const statusData: SwarmStatusResponse | null = statusRes.ok ? await statusRes.json() : null;
      const messagesData = messagesRes.ok ? await messagesRes.json() : null;

      if (messagesData?.ok && messagesData.messages) {
        setSwarmMessages(messagesData.messages);
      }

      if (statusData?.ok) {
        setSwarms((prev) =>
          prev.map((s) => {
            if (s.swarm_id !== swarm.swarm_id) return s;

            let phase: SwarmPhase = s.phase;
            if (!statusData.running) {
              phase = s.error ? "failed" : "done";
            } else if (phase === "pending") {
              phase = "planning";
            }

            // Cycle phases over time for visual effect
            const now = Date.now() / 1000;
            const elapsed = now - (s.phaseStartedAt || now);
            if (isRunning(phase)) {
              if (phase === "planning" && elapsed > 2) phase = "executing";
              else if (phase === "executing" && elapsed > 8) phase = "reflecting";
              else if (phase === "reflecting" && elapsed > 4) phase = "summarizing";
              else if (phase === "summarizing" && elapsed > 3) phase = "done";
            }

            return { ...s, phase };
          })
        );
      }
    } catch {
      // silently fail on poll
    }
  }, []);

  // ── Auto-poll all running swarms ─────────────────────────────────────
  useEffect(() => {
    const running = swarms.filter((s) => isRunning(s.phase));
    if (running.length === 0) return;
    const timer = setInterval(() => {
      running.forEach((s) => fetchSwarmDetail(s));
    }, 2000);
    return () => clearInterval(timer);
  }, [swarms, fetchSwarmDetail]);

  // ── Auto-poll selected swarm ─────────────────────────────────────────
  useEffect(() => {
    if (!selectedSwarm) return;
    const timer = setInterval(() => fetchSwarmDetail(selectedSwarm), 3000);
    return () => clearInterval(timer);
  }, [selectedSwarm, fetchSwarmDetail]);

  // ── Load messages when selecting a swarm ─────────────────────────────
  useEffect(() => {
    if (selectedSwarm) {
      fetchSwarmDetail(selectedSwarm);
    } else {
      setSwarmMessages([]);
    }
  }, [selectedSwarm, fetchSwarmDetail]);

  // ── Generate timeline events when swarm/messages change ──────────────
  useEffect(() => {
    if (!selectedSwarm) {
      setTimelineEvents([]);
      return;
    }

    const key = `${selectedSwarm.swarm_id}-${selectedSwarm.phase}-${swarmMessages.length}-${selectedSwarm.tasks.length}`;
    if (key === prevTimelineKey.current) return;
    prevTimelineKey.current = key;

    const created = swarmCreationTimes.current[selectedSwarm.swarm_id] || Date.now() / 1000;
    const newEvents = generateTimelineEvents(selectedSwarm, swarmMessages, timelineEvents, created);
    if (newEvents.length > 0) {
      setTimelineEvents((prev) => {
        const merged = [...prev];
        for (const evt of newEvents) {
          if (!merged.some((e) => e.id === evt.id)) {
            merged.push(evt);
          }
        }
        return merged.sort((a, b) => a.timestamp - b.timestamp);
      });
    }
  }, [selectedSwarm, swarmMessages, timelineEvents]);

  // ── Auto-scroll to new swarm ─────────────────────────────────────────
  useEffect(() => {
    if (newSwarmRef.current && selectedRef.current) {
      selectedRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
      newSwarmRef.current = null;
    }
  }, [selectedSwarm?.swarm_id]);

  // ── Clear new swarm highlight ────────────────────────────────────────
  useEffect(() => {
    if (newSwarmRef.current) {
      const timer = setTimeout(() => {
        newSwarmRef.current = null;
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [swarms.length]);

  const runningCount = swarms.filter((s) => isRunning(s.phase)).length;

  return (
    <div className="swarm-page">
      {/* ═══ Header ═══ */}
      <div className="swarm-header">
        <div>
          <h1 className="swarm-title">
            <span className="swarm-title-icon">🐝</span> Agent Swarms
            {runningCount > 0 && (
              <span className="swarm-live-badge">
                <SwarmSpinner color="#22c55e" size={12} />
                {runningCount} running
              </span>
            )}
          </h1>
          <p className="swarm-subtitle">
            Orchestrate multi-agent collaborations with role-based task allocation, reflection
            loops, and inter-agent messaging.
          </p>
        </div>
        <button
          className="btn btn-primary"
          onClick={() => setFormOpen(!formOpen)}
          style={{ whiteSpace: "nowrap", display: "flex", alignItems: "center", gap: 8 }}
        >
          {formOpen ? "✕ Close" : "+ New Swarm"}
        </button>
      </div>

      {error && isBackendDownError(error) ? (
        <ErrorState error={error} onRetry={() => setError(null)} />
      ) : error ? (
        <div className="swarm-alert danger">
          <span>⚠️</span> {error}
          <button
            className="btn-icon"
            onClick={() => setError(null)}
            style={{ marginLeft: "auto" }}
          >
            ✕
          </button>
        </div>
      ) : null}

      {/* ═══ Create Swarm Form ═══ */}
      {formOpen && (
        <div className="swarm-form-card">
          <h2 className="swarm-form-title">🐝 Create Agent Swarm</h2>
          <p className="swarm-form-desc">
            Define the agents, their roles, and the task prompt. The swarm manager will plan,
            execute, reflect, and summarize.
          </p>

          <div className="swarm-form-group">
            <label className="swarm-label">Agent IDs (comma-separated)</label>
            <input
              className="swarm-input"
              value={agentInput}
              onChange={(e) => setAgentInput(e.target.value)}
              placeholder="researcher, writer, reviewer, editor"
            />
          </div>

          <div className="swarm-form-group">
            <label className="swarm-label">Roles</label>
            <div className="swarm-roles-grid">
              {agentInput
                .split(",")
                .map((a) => a.trim())
                .filter(Boolean)
                .map((agent) => (
                  <div key={agent} className="swarm-role-row">
                    <span className="swarm-role-agent">{agent}</span>
                    <select
                      className="swarm-select"
                      value={roles[agent] || "executor"}
                      onChange={(e) =>
                        setRoles((prev) => ({ ...prev, [agent]: e.target.value as SwarmRole }))
                      }
                    >
                      {ROLE_OPTIONS.map((r) => (
                        <option key={r.id} value={r.id}>
                          {r.icon} {r.label}
                        </option>
                      ))}
                    </select>
                  </div>
                ))}
            </div>
          </div>

          <div className="swarm-form-group">
            <label className="swarm-label">Task Prompt</label>
            <textarea
              className="swarm-textarea"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Describe the task for the swarm..."
              rows={3}
            />
          </div>

          <div className="swarm-form-actions">
            <button className="btn" onClick={() => setFormOpen(false)}>
              Cancel
            </button>
            <button
              className="btn btn-primary"
              onClick={createSwarm}
              disabled={creating || !prompt.trim() || !agentInput.trim()}
            >
              {creating ? (
                <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <SwarmSpinner color="#fff" size={16} /> Starting Swarm...
                </span>
              ) : (
                "🚀 Launch Swarm"
              )}
            </button>
          </div>
        </div>
      )}

      {/* ═══ Roles Legend ═══ */}
      <div className="swarm-roles-legend">
        {ROLE_OPTIONS.map((r) => (
          <div key={r.id} className="swarm-role-pill" style={{ borderColor: r.color }}>
            <span>{r.icon}</span>
            <span className="swarm-role-name">{r.label}</span>
            <span className="swarm-role-desc">{r.desc}</span>
          </div>
        ))}
      </div>

      {/* ═══ Main Layout: Swarm List + Detail ═══ */}
      <div className="swarm-layout">
        {/* ── Swarm List ── */}
        <div className="swarm-list-column">
          <h2 className="swarm-section-title">
            Swarms {swarms.length > 0 && <span className="swarm-count">{swarms.length}</span>}
          </h2>

          {swarms.length === 0 && (
            <div className="swarm-empty">
              <div className="swarm-empty-icon">🐝</div>
              <div className="swarm-empty-title">No swarms yet</div>
              <div className="swarm-empty-sub">
                Create a swarm to orchestrate multi-agent collaboration
              </div>
            </div>
          )}

          <div className="swarm-list">
            {swarms.map((s) => {
              const isNew = s.swarm_id === newSwarmRef.current;
              const phaseCfg = PHASE_CONFIG[s.phase];
              const isSel = selectedSwarm?.swarm_id === s.swarm_id;
              return (
                <button
                  key={s.swarm_id}
                  className={`swarm-list-item ${isSel ? "active" : ""} ${isNew ? "new" : ""} ${isRunning(s.phase) ? "running" : ""}`}
                  onClick={() => setSelectedSwarm(s)}
                >
                  <div className="swarm-list-header">
                    <span className="swarm-list-id">#{s.swarm_id}</span>
                    <span
                      className={`swarm-list-badge ${isRunning(s.phase) ? "running" : "ok"}`}
                      style={
                        isRunning(s.phase)
                          ? { borderColor: phaseCfg.color, color: phaseCfg.color }
                          : {}
                      }
                    >
                      {isRunning(s.phase) ? (
                        <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                          <SwarmSpinner color={phaseCfg.color} size={10} />
                          {phaseCfg.label}
                        </span>
                      ) : (
                        phaseCfg.label
                      )}
                    </span>
                  </div>
                  <div className="swarm-list-prompt">
                    {s.prompt.slice(0, 80)}
                    {s.prompt.length > 80 ? "..." : ""}
                  </div>
                  <div className="swarm-list-meta">
                    <span>{s.agents.length} agents</span>
                    <span>{s.tasks.length} tasks</span>
                    {isRunning(s.phase) && s.phaseStartedAt && (
                      <span className="swarm-list-elapsed">
                        <LiveTimer startTs={s.phaseStartedAt} />
                      </span>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* ── Swarm Detail ── */}
        <div className="swarm-detail-column" ref={selectedRef}>
          {!selectedSwarm ? (
            <div className="swarm-detail-empty">
              <div className="swarm-detail-empty-icon">🐝</div>
              <div>Select a swarm to view its results</div>
            </div>
          ) : (
            <div className="swarm-detail">
              {/* Swarm Info Header */}
              <div
                className={`swarm-detail-header ${isRunning(selectedSwarm.phase) ? "running" : ""}`}
              >
                <div>
                  <h2 className="swarm-detail-title">
                    Swarm #{selectedSwarm.swarm_id}
                    {isRunning(selectedSwarm.phase) && (
                      <span className="swarm-detail-spinner">
                        <SwarmSpinner color="#6366f1" size={18} />
                      </span>
                    )}
                  </h2>
                  <p className="swarm-detail-prompt">{selectedSwarm.prompt}</p>
                </div>
                <span
                  className={`swarm-list-badge ${isRunning(selectedSwarm.phase) ? "running" : "ok"}`}
                  style={
                    isRunning(selectedSwarm.phase)
                      ? {
                          borderColor: PHASE_CONFIG[selectedSwarm.phase].color,
                          color: PHASE_CONFIG[selectedSwarm.phase].color,
                        }
                      : {}
                  }
                >
                  {isRunning(selectedSwarm.phase) ? (
                    <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <SwarmSpinner color={PHASE_CONFIG[selectedSwarm.phase].color} size={12} />
                      {PHASE_CONFIG[selectedSwarm.phase].label}
                    </span>
                  ) : (
                    PHASE_CONFIG[selectedSwarm.phase].label
                  )}
                </span>
                <a
                  href={`/swarms/report/${selectedSwarm.swarm_id}`}
                  className="swarm-report-btn"
                  target="_blank"
                >
                  <svg
                    width="14"
                    height="14"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <polyline points="14 2 14 8 20 8" />
                    <line x1="16" y1="13" x2="8" y2="13" />
                    <line x1="16" y1="17" x2="8" y2="17" />
                    <polyline points="10 9 9 9 8 9" />
                  </svg>
                  Report
                </a>
              </div>

              {/* ── Live Execution Timeline ── */}
              {isRunning(selectedSwarm.phase) && (
                <div className="swarm-detail-section">
                  <h3 className="swarm-detail-section-title">
                    🎯 Execution Progress
                    <span className="swarm-live-indicator">
                      <SwarmSpinner color="#22c55e" size={12} />
                      Live
                    </span>
                  </h3>
                  <PhaseProgressBar currentPhase={selectedSwarm.phase} />
                  <div className="swarm-live-status">
                    <div className="swarm-live-status-icon">
                      {selectedSwarm.phase === "planning" && "📋"}
                      {selectedSwarm.phase === "executing" && "⚡"}
                      {selectedSwarm.phase === "reflecting" && "🔍"}
                      {selectedSwarm.phase === "summarizing" && "📝"}
                    </div>
                    <div className="swarm-live-status-text">
                      <strong>{PHASE_CONFIG[selectedSwarm.phase].label}</strong>
                      {selectedSwarm.phase === "planning" &&
                        " — Breaking prompt into tasks and assigning roles..."}
                      {selectedSwarm.phase === "executing" &&
                        " — Running agent tasks and collecting outputs..."}
                      {selectedSwarm.phase === "reflecting" &&
                        " — Reviewing outputs and checking quality..."}
                      {selectedSwarm.phase === "summarizing" &&
                        " — Synthesizing results into final answer..."}
                    </div>
                  </div>
                </div>
              )}

              {/* ═══ Execution Timeline / Event Log ═══ */}
              <div className="swarm-detail-section">
                <h3 className="swarm-detail-section-title">
                  📜 Execution Timeline
                  <span className="swarm-count">{timelineEvents.length}</span>
                  {isRunning(selectedSwarm.phase) && (
                    <span className="swarm-live-indicator">
                      <SwarmSpinner color="#22c55e" size={10} />
                      Recording
                    </span>
                  )}
                </h3>
                <SwarmTimeline events={timelineEvents} running={isRunning(selectedSwarm.phase)} />
              </div>

              {/* ═══ Dependency Graph ═══ */}
              <div className="swarm-detail-section">
                <h3 className="swarm-detail-section-title">
                  🔗 Execution Graph
                  <span className="swarm-count">{selectedSwarm.agents.length} agents</span>
                  <div className="swarm-export-toolbar">
                    <button
                      className="swarm-export-btn"
                      title="Download as SVG"
                      onClick={() => {
                        if (graphRef.current) {
                          exportGraphSVG(graphRef.current);
                          setExportMsg("SVG downloaded!");
                          setTimeout(() => setExportMsg(null), 2000);
                        }
                      }}
                    >
                      <svg
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                        <polyline points="7 10 12 15 17 10" />
                        <line x1="12" y1="15" x2="12" y2="3" />
                      </svg>
                      SVG
                    </button>
                    <button
                      className="swarm-export-btn"
                      title="Download as PNG"
                      onClick={async () => {
                        if (graphRef.current) {
                          await exportGraphPNG(graphRef.current);
                          setExportMsg("PNG downloaded!");
                          setTimeout(() => setExportMsg(null), 2000);
                        }
                      }}
                    >
                      <svg
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                        <circle cx="8.5" cy="8.5" r="1.5" />
                        <polyline points="21 15 16 10 5 21" />
                      </svg>
                      PNG
                    </button>
                    <button
                      className="swarm-export-btn"
                      title="Copy share link"
                      onClick={() => {
                        shareSwarmLink(selectedSwarm.swarm_id);
                        setExportMsg("Link copied!");
                        setTimeout(() => setExportMsg(null), 2000);
                      }}
                    >
                      <svg
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
                        <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
                      </svg>
                      Share
                    </button>
                  </div>
                  {isRunning(selectedSwarm.phase) && (
                    <span className="swarm-live-indicator">
                      <SwarmSpinner color="#22c55e" size={10} />
                      Live
                    </span>
                  )}
                </h3>
                {exportMsg && <div className="swarm-export-toast">{exportMsg}</div>}
                <SwarmGraph
                  ref={graphRef}
                  swarm={selectedSwarm}
                  messages={swarmMessages}
                  running={isRunning(selectedSwarm.phase)}
                />
              </div>

              {/* Agent Roles */}
              <div className="swarm-detail-section">
                <h3 className="swarm-detail-section-title">🤖 Agents &amp; Roles</h3>
                <div className="swarm-agents-grid">
                  {selectedSwarm.agents.map((agent) => {
                    const role = selectedSwarm.roles[agent] || "executor";
                    const icon = ROLE_ICONS[role] || "🤖";
                    const color = ROLE_COLORS[role] || "#6366f1";
                    const busy = isRunning(selectedSwarm.phase) && role === selectedSwarm.phase;
                    return (
                      <div
                        key={agent}
                        className={`swarm-agent-card ${busy ? "busy" : ""}`}
                        style={{ borderTopColor: color }}
                      >
                        <div
                          className="swarm-agent-icon"
                          style={{ background: `${color}20`, color }}
                        >
                          {busy ? <SwarmSpinner color={color} size={18} /> : icon}
                        </div>
                        <div className="swarm-agent-info">
                          <div className="swarm-agent-name">{agent}</div>
                          <div className="swarm-agent-role" style={{ color }}>
                            {role}
                            {busy && <span className="swarm-agent-busy"> active</span>}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Tasks */}
              <div className="swarm-detail-section">
                <h3 className="swarm-detail-section-title">📋 Task Breakdown</h3>
                <div className="swarm-tasks-list">
                  {selectedSwarm.tasks.length === 0 && isRunning(selectedSwarm.phase) && (
                    <div className="swarm-task-pending">
                      <SwarmSpinner color="#6366f1" size={16} />
                      <span>Tasks being planned...</span>
                    </div>
                  )}
                  {selectedSwarm.tasks.map((task) => {
                    const isActive = isRunning(selectedSwarm.phase) && task.status === "running";
                    return (
                      <div
                        key={task.id}
                        className={`swarm-task-item ${task.status} ${isActive ? "pulsing" : ""}`}
                      >
                        <div className="swarm-task-header">
                          <span className="swarm-task-role">
                            {isActive ? (
                              <SwarmSpinner color="#f59e0b" size={14} />
                            ) : (
                              <span>
                                {ROLE_ICONS[
                                  task.description.split(":")[0]?.trim()?.toLowerCase()
                                ] || "📋"}
                              </span>
                            )}{" "}
                            {task.id}
                          </span>
                          <span className={`swarm-task-status ${task.status}`}>
                            {isActive ? "Running..." : task.status}
                          </span>
                        </div>
                        <div className="swarm-task-desc">{task.description}</div>
                        {task.assigned_to && (
                          <div className="swarm-task-assignee">
                            Assigned to: <strong>{task.assigned_to}</strong>
                          </div>
                        )}
                        {task.output ? (
                          <details className="swarm-task-output" open={isActive}>
                            <summary>{isActive ? "Live Output" : "View Output"}</summary>
                            <pre className={isActive ? "streaming" : ""}>
                              {task.output.slice(0, 500)}
                              {task.output.length > 500 ? "..." : ""}
                            </pre>
                          </details>
                        ) : isRunning(selectedSwarm.phase) ? (
                          <div className="swarm-task-waiting">
                            <SwarmSpinner color="#6366f1" size={12} />
                            Waiting for output...
                          </div>
                        ) : null}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Reflection */}
              {selectedSwarm.reflection?.answer && (
                <div className="swarm-detail-section">
                  <h3 className="swarm-detail-section-title">🔍 Reflection</h3>
                  <div className="swarm-reflection-card">
                    <div className="swarm-reflection-agent">
                      Reviewed by: <strong>{selectedSwarm.reflection.agent}</strong>
                    </div>
                    <p className="swarm-reflection-text">
                      {selectedSwarm.reflection.answer.slice(0, 600)}
                    </p>
                  </div>
                </div>
              )}

              {/* Summary */}
              {selectedSwarm.summary && (
                <div className="swarm-detail-section">
                  <h3 className="swarm-detail-section-title">📝 Summary</h3>
                  <div className="swarm-summary-card">
                    <p>{selectedSwarm.summary.slice(0, 800)}</p>
                  </div>
                </div>
              )}

              {/* Evolution Suggestions */}
              {selectedSwarm.evolution_suggestions &&
                selectedSwarm.evolution_suggestions.length > 0 && (
                  <div className="swarm-detail-section">
                    <h3 className="swarm-detail-section-title">🧬 Evolution Suggestions</h3>
                    <div className="swarm-evolution-list">
                      {selectedSwarm.evolution_suggestions.map((sug, i) => (
                        <div key={i} className="swarm-evolution-item">
                          <pre>{JSON.stringify(sug, null, 2)}</pre>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

              {/* Messages */}
              <div className="swarm-detail-section">
                <h3 className="swarm-detail-section-title">
                  💬 Message Bus <span className="swarm-count">{swarmMessages.length}</span>
                  {isRunning(selectedSwarm.phase) && (
                    <span className="swarm-live-indicator">
                      <SwarmSpinner color="#22c55e" size={10} />
                      Streaming
                    </span>
                  )}
                </h3>
                {swarmMessages.length === 0 ? (
                  <div className="swarm-empty-messages">
                    {isRunning(selectedSwarm.phase) ? (
                      <span
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 8,
                          justifyContent: "center",
                        }}
                      >
                        <SwarmSpinner color="#6366f1" size={14} />
                        Waiting for messages...
                      </span>
                    ) : (
                      "No messages recorded"
                    )}
                  </div>
                ) : (
                  <div className="swarm-messages-list">
                    {swarmMessages.map((msg, i) => (
                      <div key={i} className="swarm-message-item new">
                        <div className="swarm-message-header">
                          <span
                            className="swarm-message-sender"
                            style={{ color: ROLE_COLORS[msg.msg_type] || "#6366f1" }}
                          >
                            {msg.sender}
                          </span>
                          <span className="swarm-message-arrow">→</span>
                          <span className="swarm-message-recipient">{msg.recipient}</span>
                          <span
                            className="swarm-message-type"
                            style={{ color: ROLE_COLORS[msg.msg_type] || "#6366f1" }}
                          >
                            [{msg.msg_type}]
                          </span>
                          <span className="swarm-message-time">{formatTime(msg.timestamp)}</span>
                        </div>
                        <div className="swarm-message-content">{msg.content}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Status & Timing */}
              <div className="swarm-detail-section">
                <h3 className="swarm-detail-section-title">📊 Status</h3>
                <div className="swarm-status-grid">
                  <div className="swarm-status-card">
                    <span className="swarm-status-label">Agents</span>
                    <span className="swarm-status-value">{selectedSwarm.agents.length}</span>
                  </div>
                  <div className="swarm-status-card">
                    <span className="swarm-status-label">Tasks</span>
                    <span className="swarm-status-value">{selectedSwarm.tasks.length}</span>
                  </div>
                  <div className="swarm-status-card">
                    <span className="swarm-status-label">Messages</span>
                    <span className="swarm-status-value">{swarmMessages.length}</span>
                  </div>
                  <div className="swarm-status-card">
                    <span className="swarm-status-label">Events</span>
                    <span className="swarm-status-value">{timelineEvents.length}</span>
                  </div>
                  {isRunning(selectedSwarm.phase) && selectedSwarm.phaseStartedAt && (
                    <div className="swarm-status-card">
                      <span className="swarm-status-label">Elapsed</span>
                      <span className="swarm-status-value">
                        <LiveTimer startTs={selectedSwarm.phaseStartedAt} />
                      </span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
