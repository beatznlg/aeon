"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";

type Notification = {
  id: string;
  type: string;
  title: string;
  body: string | null;
  icon: string;
  link: string | null;
  read: boolean;
  created_at: string;
};

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(dateStr).toLocaleDateString();
}

export default function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const [recent, setRecent] = useState<Notification[]>([]);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  const fetchUnread = useCallback(async () => {
    try {
      const res = await fetch("/api/notifications?limit=5&unread=true", { cache: "no-store" });
      const data = await res.json();
      if (data.ok) {
        setUnreadCount(data.unread_count ?? data.notifications?.length ?? 0);
        if (open) setRecent(data.notifications || []);
      }
    } catch {
      // silent
    }
  }, [open]);

  // Polling fallback / initial load
  useEffect(() => {
    fetchUnread();
    intervalRef.current = setInterval(fetchUnread, 30000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchUnread]);

  // Fetch full list when dropdown opens
  useEffect(() => {
    if (open) fetchUnread();
  }, [open, fetchUnread]);

  // SSE real-time updates
  useEffect(() => {
    if (typeof window === "undefined") return;

    const connect = () => {
      try {
        const es = new EventSource("/api/stream");
        eventSourceRef.current = es;

        es.addEventListener("notification", (event) => {
          try {
            const data = JSON.parse(event.data);
            const payload = data.payload as Notification | undefined;
            if (payload) {
              setRecent((prev) => [payload, ...prev].slice(0, 10));
              setUnreadCount((c) => c + 1);
            }
          } catch {
            // ignore malformed event
          }
        });

        es.addEventListener("notification_read", (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.payload?.read_all) {
              setRecent([]);
              setUnreadCount(0);
            } else if (data.payload?.id) {
              setRecent((prev) => prev.filter((n) => n.id !== data.payload.id));
              setUnreadCount((c) => Math.max(0, c - 1));
            }
          } catch {
            // ignore malformed event
          }
        });

        es.addEventListener("error", () => {
          // Close and let reconnect logic try again
          es.close();
        });
      } catch {
        // SSE not supported; polling fallback remains active
      }
    };

    connect();

    // Reconnect every 60s to recover from transient failures
    const reconnect = setInterval(() => {
      if (eventSourceRef.current?.readyState === EventSource.CLOSED) {
        connect();
      }
    }, 60000);

    return () => {
      clearInterval(reconnect);
      eventSourceRef.current?.close();
    };
  }, []);

  // Close on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    if (open) document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  const markRead = async (id: string) => {
    try {
      await fetch("/api/notifications", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id }),
      });
      setRecent((prev) => prev.filter((n) => n.id !== id));
      setUnreadCount((c) => Math.max(0, c - 1));
    } catch {}
  };

  return (
    <div className="notif-bell-wrapper" ref={dropdownRef}>
      <button
        className="notif-bell-btn"
        onClick={() => setOpen(!open)}
        aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ""}`}
      >
        🔔
        {unreadCount > 0 && (
          <span className="notif-bell-badge">
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="notif-bell-dropdown">
          <div className="notif-bell-header">
            <h4>
              🔔 Notifications
              {unreadCount > 0 && (
                <span style={{ color: "var(--fg-mute)", fontWeight: 400, marginLeft: 6, fontSize: "0.78rem" }}>
                  ({unreadCount} new)
                </span>
              )}
            </h4>
            {unreadCount > 0 && (
              <button
                className="btn btn-sm"
                style={{ fontSize: "0.7rem", padding: "2px 8px" }}
                onClick={async () => {
                  try {
                    await fetch("/api/notifications", {
                      method: "PATCH",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({ read_all: true }),
                    });
                    setRecent([]);
                    setUnreadCount(0);
                  } catch {}
                }}
              >
                Mark all read
              </button>
            )}
          </div>

          <div className="notif-bell-list">
            {recent.length === 0 ? (
              <div style={{ padding: "24px 16px", textAlign: "center", color: "var(--fg-mute)", fontSize: "0.82rem" }}>
                All caught up! 🎉
              </div>
            ) : (
              recent.map((notif) => (
                <div
                  key={notif.id}
                  className={`notif-bell-item ${notif.read ? "" : "unread"}`}
                  onClick={() => {
                    if (!notif.read) markRead(notif.id);
                    if (notif.link) window.location.href = notif.link;
                    setOpen(false);
                  }}
                >
                  <span className="notif-bell-item-icon">{notif.icon || "🔔"}</span>
                  <div className="notif-bell-item-body">
                    <div className="notif-bell-item-title">{notif.title}</div>
                    <span className="notif-bell-item-time">{timeAgo(notif.created_at)}</span>
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="notif-bell-footer">
            <Link href="/os/notifications" onClick={() => setOpen(false)}>
              View all notifications →
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
