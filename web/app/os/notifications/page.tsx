"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

type Notification = {
  id: string;
  type: string;
  title: string;
  body: string | null;
  icon: string;
  link: string | null;
  workspace_id: string | null;
  read: boolean;
  metadata: Record<string, any>;
  created_at: string;
};

const NOTIF_ICONS: Record<string, string> = {
  swarm_completed: "✅",
  swarm_failed: "❌",
  workflow_completed: "✅",
  workflow_failed: "❌",
  chat_response: "💬",
  invoice_due: "💰",
  payment_succeeded: "💳",
  payment_failed: "💳",
  api_key_created: "🔑",
  api_key_revoked: "🔑",
  member_added: "👤",
  member_removed: "👤",
  integration_activated: "🔗",
  integration_error: "⚠️",
  system_alert: "🚨",
  admin_broadcast: "📢",
};

const TYPE_LABELS: Record<string, string> = {
  swarm_completed: "Swarm Complete",
  swarm_failed: "Swarm Failed",
  workflow_completed: "Workflow Complete",
  workflow_failed: "Workflow Failed",
  chat_response: "Chat Response",
  invoice_due: "Invoice Due",
  payment_succeeded: "Payment",
  payment_failed: "Payment Failed",
  api_key_created: "API Key Created",
  api_key_revoked: "API Key Revoked",
  member_added: "Member Added",
  member_removed: "Member Removed",
  integration_activated: "Integration Active",
  integration_error: "Integration Error",
  system_alert: "System Alert",
  admin_broadcast: "Admin Broadcast",
};

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(dateStr).toLocaleDateString();
}

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"all" | "unread">("all");
  const [offset, setOffset] = useState(0);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const pageSize = 30;

  const fetchNotifs = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        limit: String(pageSize),
        offset: String(offset),
      });
      if (filter === "unread") params.set("unread", "true");

      const res = await fetch(`/api/notifications?${params.toString()}`, { cache: "no-store" });
      const data = await res.json();
      if (data.ok) {
        setNotifications(data.notifications);
        setUnreadCount(data.unread_count);
        setTotalCount(data.count);
      }
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [offset, filter]);

  useEffect(() => {
    fetchNotifs();
  }, [fetchNotifs]);

  const markRead = async (id: string) => {
    try {
      await fetch("/api/notifications", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id }),
      });
      setNotifications((prev) => prev.map((n) => (n.id === id ? { ...n, read: true } : n)));
      setUnreadCount((c) => Math.max(0, c - 1));
    } catch {}
  };

  const markAllRead = async () => {
    try {
      const res = await fetch("/api/notifications", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ read_all: true }),
      });
      const data = await res.json();
      if (data.ok) {
        setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
        setUnreadCount(0);
        setMessage({ ok: true, text: "All marked as read" });
        setTimeout(() => setMessage(null), 2000);
      }
    } catch {}
  };

  const createTestNotif = async () => {
    try {
      const res = await fetch("/api/notifications", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          type: "system_alert",
          title: "Test Notification",
          body: "This is a test notification from the admin panel.",
          icon: "🧪",
          link: "/admin",
        }),
      });
      const data = await res.json();
      if (data.ok) {
        setNotifications((prev) => [data.notification, ...prev]);
        setUnreadCount((c) => c + 1);
        setTotalCount((c) => c + 1);
        setMessage({ ok: true, text: "Test notification created" });
        setTimeout(() => setMessage(null), 2000);
      }
    } catch {}
  };

  return (
    <div className="os-page">
      <header className="os-header">
        <div>
          <Link href="/os" className="os-back">
            ← OS Launcher
          </Link>
          <h1>🔔 Notifications</h1>
          <p className="dashboard-subtitle">
            {unreadCount > 0
              ? `${unreadCount} unread notification${unreadCount > 1 ? "s" : ""}`
              : "Stay up to date with your AEON workspace"}
          </p>
        </div>
      </header>

      {message && (
        <div className={`module-alert ${message.ok ? "" : "danger"}`} style={{ marginBottom: 16 }}>
          {message.text}
        </div>
      )}

      {/* ── Toolbar ── */}
      <div className="notif-toolbar">
        <div className="notif-filters">
          <button
            className={`notif-filter-btn ${filter === "all" ? "active" : ""}`}
            onClick={() => {
              setFilter("all");
              setOffset(0);
            }}
          >
            All ({totalCount})
          </button>
          <button
            className={`notif-filter-btn ${filter === "unread" ? "active" : ""}`}
            onClick={() => {
              setFilter("unread");
              setOffset(0);
            }}
          >
            Unread ({unreadCount})
          </button>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {unreadCount > 0 && (
            <button className="btn btn-sm" onClick={markAllRead}>
              ✓ Mark All Read
            </button>
          )}
          <button className="btn btn-sm" onClick={createTestNotif}>
            + Test
          </button>
        </div>
      </div>

      {/* ── List ── */}
      {loading ? (
        <div style={{ color: "var(--fg-mute)", padding: 40, textAlign: "center" }}>
          Loading notifications…
        </div>
      ) : notifications.length === 0 ? (
        <div className="notif-empty">
          <div className="notif-empty-icon">🔔</div>
          <div className="notif-empty-title">No notifications yet</div>
          <div className="notif-empty-desc">
            {filter === "unread"
              ? "You're all caught up! 🎉"
              : "System events and alerts will appear here."}
          </div>
        </div>
      ) : (
        <div className="notif-list">
          {notifications.map((notif) => (
            <div
              key={notif.id}
              className={`notif-item ${notif.read ? "read" : "unread"}`}
              onClick={() => !notif.read && markRead(notif.id)}
            >
              <div className="notif-item-icon">{notif.icon || NOTIF_ICONS[notif.type] || "🔔"}</div>
              <div className="notif-item-body">
                <div className="notif-item-header">
                  <strong className="notif-item-title">{notif.title}</strong>
                  <span className="notif-item-type">{TYPE_LABELS[notif.type] || notif.type}</span>
                </div>
                {notif.body && <div className="notif-item-text">{notif.body}</div>}
                <div className="notif-item-meta">
                  <span className="notif-item-time">{timeAgo(notif.created_at)}</span>
                  {notif.link && (
                    <Link
                      href={notif.link}
                      className="notif-item-link"
                      onClick={(e) => e.stopPropagation()}
                    >
                      View →
                    </Link>
                  )}
                  {unreadCount > 0 && !notif.read && <span className="notif-item-dot">●</span>}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Pagination ── */}
      {totalCount > pageSize && (
        <div className="notif-pagination">
          <button
            className="btn btn-sm"
            onClick={() => setOffset((o) => Math.max(0, o - pageSize))}
            disabled={offset === 0}
          >
            ← Previous
          </button>
          <span className="notif-page-info">
            {offset + 1}–{Math.min(offset + pageSize, totalCount)} of {totalCount}
          </span>
          <button
            className="btn btn-sm"
            onClick={() => setOffset((o) => o + pageSize)}
            disabled={offset + pageSize >= totalCount}
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}
