"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useParams } from "next/navigation";
import html2canvas from "html2canvas";
import jsPDF from "jspdf";

class PdfCancelledError extends Error {
  constructor() {
    super("PDF generation cancelled");
    this.name = "PdfCancelledError";
  }
}

// ── Types (mirrored from swarm page) ─────────────────────────────────────

type SwarmPhase =
  "pending" | "planning" | "executing" | "reflecting" | "summarizing" | "done" | "failed";

interface SwarmTaskResult {
  id: string;
  description: string;
  status: string;
  assigned_to: string | null;
  output: string;
}

interface SwarmMessageItem {
  sender: string;
  recipient: string;
  content: string;
  msg_type: string;
  timestamp: number;
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

const PHASE_LABELS: Record<string, { label: string; icon: string; color: string }> = {
  pending: { label: "Pending", icon: "⏳", color: "#94a3b8" },
  planning: { label: "Planning", icon: "📋", color: "#6366f1" },
  executing: { label: "Executing", icon: "⚡", color: "#22c55e" },
  reflecting: { label: "Reflecting", icon: "🔍", color: "#f59e0b" },
  summarizing: { label: "Summarizing", icon: "📝", color: "#06b6d4" },
  done: { label: "Completed", icon: "✅", color: "#22c55e" },
  failed: { label: "Failed", icon: "❌", color: "#ef4444" },
};

function formatAbsoluteTime(ts: number): string {
  const d = new Date(ts * 1000);
  return d.toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  const secs = Math.floor(ms / 1000);
  if (secs < 60) return `${secs}.${Math.floor((ms % 1000) / 100)}s`;
  const mins = Math.floor(secs / 60);
  return `${mins}m ${secs % 60}s`;
}

// ── PDF Download ─────────────────────────────────────────────────────────

async function downloadPDF(
  contentEl: HTMLDivElement,
  filename: string,
  isDark: boolean = false,
  cancelRef: { current: boolean },
  onProgress?: (pct: number) => void
): Promise<void> {
  // Check cancellation before starting
  if (cancelRef.current) throw new PdfCancelledError();
  onProgress?.(2);

  // Phase 1: html2canvas capture (0→35%). Time-based simulation since no native callback.
  let captureDone = false;
  const captureTimer = setInterval(() => {
    if (!captureDone) onProgress?.(Math.min(5 + Math.random() * 25, 33));
  }, 200);

  const canvas = await html2canvas(contentEl, {
    scale: 2,
    useCORS: true,
    logging: false,
    backgroundColor: isDark ? "#0f172a" : "#ffffff",
    width: contentEl.scrollWidth,
    height: contentEl.scrollHeight,
    windowWidth: contentEl.scrollWidth,
  });

  captureDone = true;
  clearInterval(captureTimer);

  // Check cancellation after capture
  if (cancelRef.current) throw new PdfCancelledError();
  onProgress?.(35);

  const pdf = new jsPDF({
    orientation: "portrait",
    unit: "px",
    format: "a4",
  });

  const pdfW = pdf.internal.pageSize.getWidth();
  const pdfH = pdf.internal.pageSize.getHeight();
  const margin = 24;
  const usableW = pdfW - margin * 2;
  const usableH = pdfH - margin * 2;

  const imgW = canvas.width;
  const imgH = canvas.height;
  const ratio = Math.min(usableW / imgW, usableH / imgH);
  const scaledW = imgW * ratio;
  const scaledH = imgH * ratio;

  // Phase 2: Multi-page split (35→80%)
  let remainingH = scaledH;
  let yOffset = 0;
  let page = 0;
  const totalPages = Math.ceil(scaledH / usableH);

  while (remainingH > 0) {
    if (cancelRef.current) throw new PdfCancelledError();

    if (page > 0) pdf.addPage();

    const pageH = Math.min(usableH, remainingH);
    const srcY = yOffset / ratio;
    const srcH = pageH / ratio;

    const pageCanvas = document.createElement("canvas");
    pageCanvas.width = canvas.width;
    pageCanvas.height = srcH;
    const ctx = pageCanvas.getContext("2d")!;
    ctx.drawImage(canvas, 0, srcY, canvas.width, srcH, 0, 0, canvas.width, srcH);
    const pageImgData = pageCanvas.toDataURL("image/png");

    pdf.addImage(pageImgData, "PNG", margin, margin, usableW, pageH);

    remainingH -= pageH;
    yOffset += pageH;
    page++;

    const progress = 35 + Math.round((page / totalPages) * 45);
    onProgress?.(progress);
  }

  // Check cancellation before saving
  if (cancelRef.current) throw new PdfCancelledError();

  // Phase 3: Saving (80→100%)
  onProgress?.(85);
  await new Promise((r) => setTimeout(r, 100));
  onProgress?.(92);
  pdf.save(filename);
  onProgress?.(100);
}

// ── Report Page ──────────────────────────────────────────────────────────

export default function SwarmReportPage() {
  const params = useParams();
  const id = params?.id as string;

  const [swarmData, setSwarmData] = useState<SwarmResult | null>(null);
  const [messages, setMessages] = useState<SwarmMessageItem[]>([]);
  const [status, setStatus] = useState<SwarmStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [phase, setPhase] = useState<SwarmPhase>("pending");
  const [generatingPDF, setGeneratingPDF] = useState(false);
  const [pdfProgress, setPdfProgress] = useState(0);
  const [pdfCancelled, setPdfCancelled] = useState(false);
  const [darkMode, setDarkMode] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);
  const cancelPdfRef = useRef({ current: false });

  const fetchData = useCallback(async () => {
    if (!id) return;
    try {
      const [statusRes, messagesRes] = await Promise.all([
        fetch(`/api/swarm/${id}`),
        fetch(`/api/swarm/${id}/messages`),
      ]);

      if (statusRes.ok) {
        const sd: SwarmStatusResponse = await statusRes.json();
        setStatus(sd);
        if (!sd.running) setPhase("done");
        else setPhase("planning");
      }

      if (messagesRes.ok) {
        const md = await messagesRes.json();
        if (md.ok && md.messages) setMessages(md.messages);
      }
    } catch {
      // silently retry
    }
  }, [id]);

  // Fetch swarm data
  useEffect(() => {
    if (!id) return;
    (async () => {
      setLoading(true);
      await fetchData();
      setLoading(false);
    })();
  }, [id, fetchData]);

  // Poll while running
  useEffect(() => {
    if (!id || phase === "done" || phase === "failed") return;
    const timer = setInterval(fetchData, 3000);
    return () => clearInterval(timer);
  }, [id, phase, fetchData]);

  const phaseCfg = PHASE_LABELS[phase] || PHASE_LABELS.done;

  if (!id) {
    return (
      <div className="report-page">
        <div className="report-empty">
          <div className="report-empty-icon">🐝</div>
          <h2>No Swarm Specified</h2>
          <p>Please provide a valid swarm ID in the URL.</p>
          <a href="/swarms" className="report-back-link">
            ← Back to Swarms
          </a>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="report-page">
        <div className="report-loading">
          <div className="report-spinner" />
          <p>Loading swarm execution report...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="report-page">
        <div className="report-empty">
          <h2>Error Loading Report</h2>
          <p>{error}</p>
          <a href="/swarms" className="report-back-link">
            ← Back to Swarms
          </a>
        </div>
      </div>
    );
  }

  const agentCount = status?.task_count ?? swarmData?.agents.length ?? 0;
  const taskCount = status?.task_count ?? swarmData?.tasks.length ?? 0;
  const msgCount = status?.message_count ?? messages.length;

  // Build timeline events from messages
  const timelineEvents = [
    {
      ts: Date.now() / 1000 - 100,
      label: "Swarm Created",
      icon: "🐝",
      desc: `Swarm #${id} initialized`,
    },
    ...messages.slice(-10).map((m) => ({
      ts: m.timestamp,
      label: `${m.sender} → ${m.recipient}`,
      icon: "💬",
      desc: m.content.slice(0, 100),
    })),
  ];

  return (
    <div className={`report-page ${darkMode ? "report-dark" : ""}`}>
      {/* ── Report Toolbar ── */}
      <div className="report-toolbar no-print">
        <a href="/swarms" className="report-back-btn">
          ← Back to Swarms
        </a>
        <div className="report-toolbar-center">
          <span className="report-toolbar-id">Swarm Report #{id}</span>
        </div>
        <button
          className="report-dark-toggle"
          onClick={() => setDarkMode((p) => !p)}
          title={darkMode ? "Switch to light mode" : "Switch to dark mode"}
        >
          {darkMode ? (
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <circle cx="12" cy="12" r="5" />
              <line x1="12" y1="1" x2="12" y2="3" />
              <line x1="12" y1="21" x2="12" y2="23" />
              <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
              <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
              <line x1="1" y1="12" x2="3" y2="12" />
              <line x1="21" y1="12" x2="23" y2="12" />
              <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
              <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
            </svg>
          ) : (
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
            </svg>
          )}
        </button>
        <button
          className="report-print-btn"
          onClick={async () => {
            if (!contentRef.current || generatingPDF) return;
            setGeneratingPDF(true);
            setPdfProgress(0);
            setPdfCancelled(false);
            cancelPdfRef.current.current = false;
            try {
              await downloadPDF(
                contentRef.current,
                `swarm-report-${id}.pdf`,
                darkMode,
                cancelPdfRef.current,
                setPdfProgress
              );
            } catch (err) {
              if (err instanceof PdfCancelledError) {
                setPdfCancelled(true);
                setTimeout(() => setPdfCancelled(false), 2000);
              } else {
                window.print();
              }
            } finally {
              setGeneratingPDF(false);
              setPdfProgress(0);
            }
          }}
          disabled={generatingPDF}
          style={generatingPDF ? { cursor: "not-allowed" } : {}}
        >
          {generatingPDF ? (
            <div className="report-pdf-progress">
              <div className="report-pdf-progress-bar-wrap">
                <div className="report-pdf-progress-bar" style={{ width: `${pdfProgress}%` }} />
              </div>
              <div className="report-pdf-progress-row">
                <span className="report-pdf-progress-label">
                  {pdfProgress < 35
                    ? "Capturing page…"
                    : pdfProgress < 80
                      ? "Building PDF…"
                      : "Finalizing…"}{" "}
                  {pdfProgress}%
                </span>
                <button
                  className="report-pdf-cancel-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    cancelPdfRef.current.current = true;
                  }}
                >
                  ✕
                </button>
              </div>
            </div>
          ) : pdfCancelled ? (
            <span style={{ color: "#ef4444" }}>⚠ Cancelled</span>
          ) : (
            "📄 Download PDF"
          )}
        </button>
      </div>

      {/* ═══════════════════════════════════════════════════════════════
         REPORT CONTENT
         ═══════════════════════════════════════════════════════════════ */}
      <div className="report-content" ref={contentRef}>
        {/* ── Header ── */}
        <div className="report-header">
          <div className="report-header-left">
            <div className="report-logo">🐝 AEON OS</div>
            <div className="report-title">Swarm Execution Report</div>
            <div className="report-meta-row">
              <span className="report-meta-item">
                ID: <strong>#{id}</strong>
              </span>
              <span className="report-meta-item">
                Date: <strong>{formatAbsoluteTime(Date.now() / 1000)}</strong>
              </span>
              <span className="report-meta-item">
                Status:{" "}
                <strong style={{ color: phaseCfg.color }}>
                  {phaseCfg.icon} {phaseCfg.label}
                </strong>
              </span>
            </div>
            <div className="report-meta-row">
              <span className="report-meta-item">
                Agents: <strong>{agentCount}</strong>
              </span>
              <span className="report-meta-item">
                Tasks: <strong>{taskCount}</strong>
              </span>
              <span className="report-meta-item">
                Messages: <strong>{msgCount}</strong>
              </span>
            </div>
          </div>
          <div className="report-header-right">
            {swarmData?.prompt && (
              <div className="report-prompt-card">
                <div className="report-prompt-label">Task Prompt</div>
                <p className="report-prompt-text">{swarmData.prompt}</p>
              </div>
            )}
          </div>
        </div>

        {/* ── Agents & Roles ── */}
        <div className="report-section">
          <h2 className="report-section-title">🤖 Agents &amp; Roles</h2>
          <div className="report-agents-grid">
            {swarmData?.agents.map((agent) => {
              const role = swarmData.roles[agent] || "executor";
              const color = ROLE_COLORS[role] || "#6366f1";
              const icon = ROLE_ICONS[role] || "🤖";
              return (
                <div
                  key={agent}
                  className="report-agent-card"
                  style={{ borderLeft: `3px solid ${color}` }}
                >
                  <div className="report-agent-icon" style={{ color }}>
                    {icon}
                  </div>
                  <div className="report-agent-info">
                    <div className="report-agent-name">{agent}</div>
                    <div className="report-agent-role" style={{ color }}>
                      {role}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* ── Task Breakdown ── */}
        <div className="report-section">
          <h2 className="report-section-title">📋 Task Breakdown</h2>
          {!swarmData?.tasks || swarmData.tasks.length === 0 ? (
            <div className="report-empty-data">No tasks recorded</div>
          ) : (
            <div className="report-tasks-table">
              <div className="report-tasks-header">
                <span className="report-tasks-col-id">Task ID</span>
                <span className="report-tasks-col-desc">Description</span>
                <span className="report-tasks-col-agent">Assigned To</span>
                <span className="report-tasks-col-status">Status</span>
                <span className="report-tasks-col-output">Output</span>
              </div>
              {swarmData.tasks.map((task) => (
                <div key={task.id} className="report-tasks-row">
                  <span className="report-tasks-col-id report-mono">{task.id}</span>
                  <span className="report-tasks-col-desc">{task.description}</span>
                  <span className="report-tasks-col-agent">{task.assigned_to || "—"}</span>
                  <span className="report-tasks-col-status">
                    <span className={`report-status-badge ${task.status}`}>{task.status}</span>
                  </span>
                  <span className="report-tasks-col-output report-mono">
                    {task.output
                      ? task.output.slice(0, 120) + (task.output.length > 120 ? "..." : "")
                      : "—"}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ── Messages / Message Bus ── */}
        <div className="report-section">
          <h2 className="report-section-title">💬 Message Bus ({messages.length})</h2>
          {messages.length === 0 ? (
            <div className="report-empty-data">No messages recorded</div>
          ) : (
            <div className="report-messages-timeline">
              {messages.map((msg, i) => {
                const color = ROLE_COLORS[msg.msg_type] || "#6366f1";
                return (
                  <div key={i} className="report-msg-item">
                    <div className="report-msg-line">
                      <span className="report-msg-sender" style={{ color }}>
                        {msg.sender}
                      </span>
                      <span className="report-msg-arrow">→</span>
                      <span className="report-msg-recipient">{msg.recipient}</span>
                      <span className="report-msg-type" style={{ color }}>
                        [{msg.msg_type}]
                      </span>
                      <span className="report-msg-time">{formatAbsoluteTime(msg.timestamp)}</span>
                    </div>
                    <div className="report-msg-content">{msg.content}</div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* ── Results / Agent Outputs ── */}
        {swarmData?.results && Object.keys(swarmData.results).length > 0 && (
          <div className="report-section">
            <h2 className="report-section-title">📊 Agent Results</h2>
            <div className="report-results-grid">
              {Object.entries(swarmData.results).map(([agent, result]) => (
                <div key={agent} className={`report-result-card ${result.ok ? "ok" : "fail"}`}>
                  <div className="report-result-header">
                    <span className={`report-result-status ${result.ok ? "ok" : "fail"}`}>
                      {result.ok ? "✓" : "✗"}
                    </span>
                    <span className="report-result-agent">{agent}</span>
                  </div>
                  {result.output && (
                    <pre className="report-result-output">{result.output.slice(0, 300)}</pre>
                  )}
                  {result.error && <div className="report-result-error">{result.error}</div>}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── Reflection ── */}
        {swarmData?.reflection?.answer && (
          <div className="report-section">
            <h2 className="report-section-title">🔍 Reflection</h2>
            <div className="report-reflection-card">
              <div className="report-reflection-agent">
                Reviewed by: <strong>{swarmData.reflection.agent || "unknown"}</strong>
              </div>
              <p className="report-reflection-text">{swarmData.reflection.answer}</p>
            </div>
          </div>
        )}

        {/* ── Summary ── */}
        {swarmData?.summary && (
          <div className="report-section">
            <h2 className="report-section-title">📝 Summary</h2>
            <div className="report-summary-card">
              <p>{swarmData.summary}</p>
            </div>
          </div>
        )}

        {/* ── Evolution Suggestions ── */}
        {swarmData?.evolution_suggestions && swarmData.evolution_suggestions.length > 0 && (
          <div className="report-section">
            <h2 className="report-section-title">🧬 Evolution Suggestions</h2>
            {swarmData.evolution_suggestions.map((sug, i) => (
              <div key={i} className="report-evolution-item">
                <pre>{typeof sug === "string" ? sug : JSON.stringify(sug, null, 2)}</pre>
              </div>
            ))}
          </div>
        )}

        {/* ── Timeline ── */}
        <div className="report-section">
          <h2 className="report-section-title">📜 Event Timeline</h2>
          {timelineEvents.length === 0 ? (
            <div className="report-empty-data">No events recorded</div>
          ) : (
            <div className="report-timeline">
              <div className="report-timeline-line" />
              {timelineEvents.map((evt, i) => (
                <div key={i} className="report-timeline-event">
                  <div className="report-timeline-dot">{evt.icon}</div>
                  <div className="report-timeline-content">
                    <div className="report-timeline-label">{evt.label}</div>
                    <div className="report-timeline-desc">{evt.desc}</div>
                    <div className="report-timeline-time">{formatAbsoluteTime(evt.ts)}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ── Footer ── */}
        <div className="report-footer">
          <p>
            AEON OS — Swarm Execution Report — Generated {formatAbsoluteTime(Date.now() / 1000)}
          </p>
        </div>
      </div>
    </div>
  );
}
