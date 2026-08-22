"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import ErrorState from "@/components/ui/ErrorState";

interface AeonEvent {
  type: string;
  payload: Record<string, any>;
  user_id?: string;
  workspace_id?: string;
  timestamp: string;
}

const EVENT_LABELS: Record<string, { label: string; icon: string; color: string }> = {
  notification: { label: "Notification", icon: "🔔", color: "#6366f1" },
  notification_read: { label: "Read", icon: "✓", color: "#22c55e" },
  swarm_status: { label: "Swarm", icon: "🐝", color: "#f59e0b" },
  workflow_status: { label: "Workflow", icon: "⚡", color: "#a855f7" },
  audit_log: { label: "Audit", icon: "📋", color: "#3b82f6" },
  workspace_activity: { label: "Workspace", icon: "🏢", color: "#10b981" },
  system: { label: "System", icon: "🖥️", color: "#94a3b8" },
};

function formatTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function eventTitle(ev: AeonEvent): string {
  const p = ev.payload || {};
  switch (ev.type) {
    case "notification":
      return p.title || "New notification";
    case "notification_read":
      return p.read_all ? "Marked all notifications read" : "Notification read";
    case "swarm_status":
      return `Swarm ${p.status || "updated"}${p.swarm_id ? ` · ${p.swarm_id.slice(0, 8)}` : ""}`;
    case "workflow_status":
      return `Workflow ${p.status || "updated"}${p.workflow_id ? ` · ${p.workflow_id.slice(0, 8)}` : ""}`;
    case "audit_log":
      return p.action ? `Audit: ${p.action}` : "Audit log event";
    case "workspace_activity":
      return p.action || "Workspace activity";
    case "system":
      return p.message || "System event";
    default:
      return `${ev.type} event`;
  }
}

function eventBody(ev: AeonEvent): string {
  const p = ev.payload || {};
  if (p.body) return p.body;
  if (p.error) return p.error;
  if (p.message) return p.message;
  if (p.prompt) return p.prompt;
  return "";
}

export default function ActivityStreamPage() {
  const [events, setEvents] = useState<AeonEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Load historical activity events on mount
  useEffect(() => {
    fetch("/api/activity?limit=50")
      .then((res) => res.json())
      .then((data) => {
        if (data.ok && Array.isArray(data.events)) {
          const historical = data.events.map((ev: any) => ({
            type: ev.type,
            payload: ev.payload,
            user_id: ev.user_id,
            workspace_id: ev.workspace_id,
            timestamp: ev.created_at,
          }));
          setEvents((prev) => [...prev, ...historical].slice(0, 200));
        }
      })
      .catch(() => {
        // Historical load is best-effort; live stream still works
      });
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const es = new EventSource("/api/stream");
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    es.onopen = () => {
      setConnected(true);
      setError(null);
    };

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "system" && data.payload?.message?.includes("Connected")) {
          // Connection handshake, don't add to timeline
          return;
        }
        setEvents((prev) => [data, ...prev].slice(0, 200));
      } catch {
        // ignore malformed events
      }
    };

    es.onerror = () => {
      setConnected(false);
      setError("Connection lost — reconnecting…");
      es.close();
      if (!reconnectTimer) {
        reconnectTimer = setTimeout(() => {
          window.location.reload();
        }, 5000);
      }
    };

    return () => {
      es.close();
      if (reconnectTimer) clearTimeout(reconnectTimer);
    };
  }, []);

  const clearEvents = () => setEvents([]);

  return (
    <div className="os-page" style={{ padding: 24 }}>
      <header className="os-header" style={{ marginBottom: 20 }}>
        <div>
          <h1
            style={{
              background: "var(--grad)",
              WebkitBackgroundClip: "text",
              backgroundClip: "text",
              color: "transparent",
            }}
          >
            ⚡ Live Activity Stream
          </h1>
          <p className="dashboard-subtitle">
            Real-time events from swarms, workflows, notifications, and workspace activity.
          </p>
        </div>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              fontSize: "0.8rem",
              color: connected ? "#22c55e" : "var(--fg-mute)",
            }}
          >
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                background: connected ? "#22c55e" : "#ef4444",
                boxShadow: connected ? "0 0 6px #22c55e" : "none",
              }}
            />
            {connected ? "Live" : "Disconnected"}
          </span>
          <button className="btn btn-sm" onClick={clearEvents}>
            Clear
          </button>
          <Link href="/os" className="btn btn-sm btn-primary">
            ← Back to OS
          </Link>
        </div>
      </header>

      {error && (
        <div style={{ marginBottom: 16 }}>
          <ErrorState
            error={error}
            onRetry={() => window.location.reload()}
            title="Activity stream disconnected"
          />
        </div>
      )}

      <section
        style={{
          border: "1px solid var(--border)",
          borderRadius: 12,
          background: "var(--bg)",
          minHeight: 400,
          maxHeight: "calc(100vh - 220px)",
          overflowY: "auto",
        }}
      >
        {events.length === 0 ? (
          <div
            style={{
              padding: 60,
              textAlign: "center",
              color: "var(--fg-mute)",
            }}
          >
            <div style={{ fontSize: "2rem", marginBottom: 12, opacity: 0.5 }}>📡</div>
            <p>Listening for live events…</p>
            <p style={{ fontSize: "0.78rem", marginTop: 8 }}>
              Run a swarm or workflow to see real-time updates here.
            </p>
          </div>
        ) : (
          <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {events.map((ev, idx) => {
              const meta = EVENT_LABELS[ev.type] || { label: ev.type, icon: "●", color: "#94a3b8" };
              return (
                <li
                  key={`${ev.timestamp}-${idx}`}
                  style={{
                    display: "flex",
                    gap: 12,
                    padding: "14px 18px",
                    borderBottom: "1px solid var(--border)",
                    transition: "background 0.15s ease",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = "var(--bg-1)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = "transparent";
                  }}
                >
                  <div
                    style={{
                      width: 36,
                      height: 36,
                      borderRadius: "50%",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: "1.1rem",
                      background: `${meta.color}20`,
                      flexShrink: 0,
                    }}
                  >
                    {meta.icon}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div
                      style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}
                    >
                      <span
                        style={{
                          fontSize: "0.72rem",
                          fontWeight: 700,
                          textTransform: "uppercase",
                          letterSpacing: "0.05em",
                          color: meta.color,
                          background: `${meta.color}15`,
                          padding: "2px 8px",
                          borderRadius: 999,
                        }}
                      >
                        {meta.label}
                      </span>
                      <span style={{ fontSize: "0.78rem", color: "var(--fg-mute)" }}>
                        {formatTime(ev.timestamp)}
                      </span>
                    </div>
                    <div style={{ fontWeight: 600, color: "var(--fg)", marginTop: 4 }}>
                      {eventTitle(ev)}
                    </div>
                    {eventBody(ev) && (
                      <div
                        style={{
                          color: "var(--fg-soft)",
                          fontSize: "0.85rem",
                          marginTop: 2,
                          lineHeight: 1.5,
                        }}
                      >
                        {eventBody(ev)}
                      </div>
                    )}
                    <div style={{ fontSize: "0.72rem", color: "var(--fg-mute)", marginTop: 6 }}>
                      {formatDate(ev.timestamp)}
                      {ev.workspace_id && ` · workspace ${ev.workspace_id.slice(0, 8)}`}
                    </div>
                  </div>
                </li>
              );
            })}
            <div ref={bottomRef} />
          </ul>
        )}
      </section>
    </div>
  );
}
