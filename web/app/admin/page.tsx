"use client";

import { useCallback, useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { redirect } from "next/navigation";
import Link from "next/link";

type SystemStats = {
  total_users: number;
  total_workspaces: number;
  total_memberships: number;
  role_distribution: Record<string, number>;
  plan_distribution: Record<string, number>;
  total_audit_entries: number;
};

type AdminUser = {
  id: string;
  email: string;
  name: string | null;
  role: string;
  created_at: string;
  tenant_id: string | null;
  memberships: { workspace_id: string; role: string }[];
  member_count: number;
};

type AdminWorkspace = {
  id: string;
  slug: string;
  name: string;
  plan: string;
  created_at: string;
  tenant_id: string | null;
  member_count: number;
};

type Tab = "overview" | "users" | "workspaces" | "audit";

export default function AdminPage() {
  const { data: session } = useSession();
  const role = (session?.user as any)?.role;

  const [tab, setTab] = useState<Tab>("overview");
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [workspaces, setWorkspaces] = useState<AdminWorkspace[]>([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const [editingRole, setEditingRole] = useState<string | null>(null);
  const [notifSending, setNotifSending] = useState(false);

  // New workspace form
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newSlug, setNewSlug] = useState("");

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [statsRes, usersRes, workspacesRes] = await Promise.all([
        fetch("/api/admin/stats", { cache: "no-store" }),
        fetch("/api/admin/users", { cache: "no-store" }),
        fetch("/api/admin/workspaces", { cache: "no-store" }),
      ]);
      const s = await statsRes.json();
      const u = await usersRes.json();
      const w = await workspacesRes.json();
      if (s.ok) setStats(s.stats);
      if (u.ok) setUsers(u.users);
      if (w.ok) setWorkspaces(w.workspaces);
    } catch (e: any) {
      setMessage({ ok: false, text: e?.message || "Failed to load admin data" });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (role && role !== "ADMIN") {
    redirect("/settings");
  }

  const updateRole = async (userId: string, newRole: string) => {
    setMessage(null);
    try {
      const res = await fetch(`/api/admin/users/${userId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role: newRole }),
      });
      const data = await res.json();
      if (data.ok) {
        setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, role: newRole } : u)));
        setMessage({ ok: true, text: "Role updated" });
      } else {
        setMessage({ ok: false, text: data.error || "Failed to update role" });
      }
    } catch (e: any) {
      setMessage({ ok: false, text: e?.message || "Network error" });
    }
    setEditingRole(null);
  };

  const deleteUser = async (userId: string, email: string) => {
    if (!confirm(`Delete user ${email}? This cannot be undone.`)) return;
    try {
      const res = await fetch(`/api/admin/users/${userId}`, { method: "DELETE" });
      const data = await res.json();
      if (data.ok) {
        setUsers((prev) => prev.filter((u) => u.id !== userId));
        setMessage({ ok: true, text: `User ${email} deleted` });
      } else {
        setMessage({ ok: false, text: data.error || "Failed to delete user" });
      }
    } catch (e: any) {
      setMessage({ ok: false, text: e?.message || "Network error" });
    }
  };

  const deleteWorkspace = async (wsId: string, name: string) => {
    if (!confirm(`Delete workspace "${name}"? This cannot be undone.`)) return;
    try {
      const res = await fetch(`/api/admin/workspaces/${wsId}`, { method: "DELETE" });
      const data = await res.json();
      if (data.ok) {
        setWorkspaces((prev) => prev.filter((w) => w.id !== wsId));
        setMessage({ ok: true, text: `Workspace "${name}" deleted` });
      } else {
        setMessage({ ok: false, text: data.error || "Failed to delete workspace" });
      }
    } catch (e: any) {
      setMessage({ ok: false, text: e?.message || "Network error" });
    }
  };

  const createWorkspace = async () => {
    if (!newName.trim() || !newSlug.trim()) return;
    setMessage(null);
    try {
      const res = await fetch("/api/admin/workspaces", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newName.trim(), slug: newSlug.trim(), plan: "free" }),
      });
      const data = await res.json();
      if (data.ok) {
        setWorkspaces((prev) => [data.workspace, ...prev]);
        setShowCreate(false);
        setNewName("");
        setNewSlug("");
        setMessage({ ok: true, text: "Workspace created" });
      } else {
        setMessage({ ok: false, text: data.error || "Failed to create workspace" });
      }
    } catch (e: any) {
      setMessage({ ok: false, text: e?.message || "Network error" });
    }
  };

  const tabs: { id: Tab; label: string; icon: string }[] = [
    { id: "overview", label: "Overview", icon: "📊" },
    { id: "users", label: "Users", icon: "👥" },
    { id: "workspaces", label: "Workspaces", icon: "🏢" },
    { id: "audit", label: "Audit Log", icon: "📋" },
  ];

  return (
    <div className="os-page">
      <header className="os-header">
        <div>
          <Link href="/os" className="os-back">← OS Launcher</Link>
          <h1>⚙️ Admin Panel</h1>
          <p className="dashboard-subtitle">System administration, user management, and multi-tenant oversight</p>
        </div>
      </header>

      {message && (
        <div className={`module-alert ${message.ok ? "" : "danger"}`} style={{ marginBottom: 20 }}>
          {message.text}
        </div>
      )}

      {/* ── Tab Bar ── */}
      <div className="admin-tabs" style={{ display: "flex", gap: 4, marginBottom: 24, borderBottom: "1px solid var(--border)", paddingBottom: 0 }}>
        {tabs.map((t) => (
          <button
            key={t.id}
            className={`admin-tab ${tab === t.id ? "active" : ""}`}
            onClick={() => setTab(t.id)}
          >
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div style={{ color: "var(--fg-mute)", padding: 40, textAlign: "center" }}>Loading admin data…</div>
      ) : (
        <>
          {/* ═══════════════════════ OVERVIEW ═══════════════════════ */}
          {tab === "overview" && stats && (
            <>
              <section className="admin-stats-grid">
                <div className="admin-stat-card">
                  <div className="admin-stat-icon">👤</div>
                  <div className="admin-stat-value">{stats.total_users}</div>
                  <div className="admin-stat-label">Total Users</div>
                </div>
                <div className="admin-stat-card">
                  <div className="admin-stat-icon">🏢</div>
                  <div className="admin-stat-value">{stats.total_workspaces}</div>
                  <div className="admin-stat-label">Workspaces</div>
                </div>
                <div className="admin-stat-card">
                  <div className="admin-stat-icon">🔗</div>
                  <div className="admin-stat-value">{stats.total_memberships}</div>
                  <div className="admin-stat-label">Memberships</div>
                </div>
                <div className="admin-stat-card">
                  <div className="admin-stat-icon">📋</div>
                  <div className="admin-stat-value">{stats.total_audit_entries}</div>
                  <div className="admin-stat-label">Audit Entries</div>
                </div>
                <div
                  className="admin-stat-card"
                  style={{ cursor: "pointer", position: "relative", opacity: notifSending ? 0.6 : 1 }}
                  onClick={async () => {
                    if (notifSending) return;
                    setNotifSending(true);
                    setMessage(null);
                    try {
                      const res = await fetch("/api/notifications", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                          type: "system_alert",
                          title: "Test Notification from Admin",
                          body: "This is a test notification to verify the notification pipeline. If you see this, everything is wired up!",
                          icon: "\uD83E\uDDEA",
                          link: "/admin",
                          metadata: { source: "admin_test", timestamp: new Date().toISOString() },
                        }),
                      });
                      const data = await res.json();
                      if (data.ok) {
                        setMessage({ ok: true, text: "Test notification sent! Check your notification bell. \uD83E\uDDEA" });
                      } else {
                        setMessage({ ok: false, text: data.error || "Failed to send test notification" });
                      }
                    } catch (e: any) {
                      setMessage({ ok: false, text: e?.message || "Network error sending test notification" });
                    } finally {
                      setNotifSending(false);
                    }
                  }}
                >
                  <div className="admin-stat-icon">{notifSending ? "\u23F3" : "\uD83E\uDDEA"}</div>
                  <div className="admin-stat-value" style={{ fontSize: "0.85rem" }}>{notifSending ? "Sending..." : "Send Test"}</div>
                  <div className="admin-stat-label">Test Notification</div>
                </div>
              </section>

              <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 24, marginTop: 24 }}>
                <div className="os-card" style={{ padding: 20 }}>
                  <h3 style={{ marginBottom: 16, fontSize: "0.85rem", textTransform: "uppercase", letterSpacing: 1, color: "var(--fg-mute)" }}>
                    Role Distribution
                  </h3>
                  {Object.entries(stats.role_distribution).map(([role, count]) => (
                    <div key={role} className="admin-bar-row">
                      <span className="admin-bar-label">{role}</span>
                      <div className="admin-bar-track">
                        <div
                          className="admin-bar-fill"
                          style={{
                            width: `${stats.total_users > 0 ? (count / stats.total_users) * 100 : 0}%`,
                            background: role === "ADMIN" ? "#6366f1" : role === "OPERATOR" ? "#f59e0b" : "#22c55e",
                          }}
                        />
                      </div>
                      <span className="admin-bar-count">{count}</span>
                    </div>
                  ))}
                </div>

                <div className="os-card" style={{ padding: 20 }}>
                  <h3 style={{ marginBottom: 16, fontSize: "0.85rem", textTransform: "uppercase", letterSpacing: 1, color: "var(--fg-mute)" }}>
                    Plan Distribution
                  </h3>
                  {Object.entries(stats.plan_distribution).map(([plan, count]) => (
                    <div key={plan} className="admin-bar-row">
                      <span className="admin-bar-label">{plan}</span>
                      <div className="admin-bar-track">
                        <div
                          className="admin-bar-fill"
                          style={{
                            width: `${stats.total_workspaces > 0 ? (count / stats.total_workspaces) * 100 : 0}%`,
                            background: plan === "enterprise" ? "#6366f1" : plan === "team" ? "#f59e0b" : "#22c55e",
                          }}
                        />
                      </div>
                      <span className="admin-bar-count">{count}</span>
                    </div>
                  ))}
                </div>
              </section>
            </>
          )}

          {/* ═══════════════════════ USERS ═══════════════════════ */}
          {tab === "users" && (
            <section className="module-widget">
              <h3>👥 All Users ({users.length})</h3>
              <div style={{ overflowX: "auto", marginTop: 16 }}>
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Email</th>
                      <th>Role</th>
                      <th>Workspaces</th>
                      <th>Created</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((user) => (
                      <tr key={user.id}>
                        <td><strong>{user.name || "—"}</strong></td>
                        <td>{user.email}</td>
                        <td>
                          {editingRole === user.id ? (
                            <select
                              value={user.role}
                              onChange={(e) => {
                                setUsers((prev) => prev.map((u) => u.id === user.id ? { ...u, role: e.target.value } : u));
                              }}
                              className="input"
                              style={{ width: 130, fontSize: "0.8rem", padding: "2px 6px" }}
                              autoFocus
                            >
                              <option value="VIEWER">VIEWER</option>
                              <option value="OPERATOR">OPERATOR</option>
                              <option value="ADMIN">ADMIN</option>
                            </select>
                          ) : (
                            <span className={`admin-role-badge role-${user.role.toLowerCase()}`}>{user.role}</span>
                          )}
                        </td>
                        <td style={{ color: "var(--fg-soft)" }}>{user.member_count}</td>
                        <td style={{ color: "var(--fg-mute)", fontSize: "0.8rem" }}>
                          {new Date(user.created_at).toLocaleDateString()}
                        </td>
                        <td>
                          <div style={{ display: "flex", gap: 4 }}>
                            {editingRole === user.id ? (
                              <>
                                <button className="btn btn-sm btn-primary" onClick={() => updateRole(user.id, user.role)}>Save</button>
                                <button className="btn btn-sm" onClick={() => setEditingRole(null)}>Cancel</button>
                              </>
                            ) : (
                              <button className="btn btn-sm" onClick={() => setEditingRole(user.id)}>Role</button>
                            )}
                            <button className="btn btn-sm btn-danger" onClick={() => deleteUser(user.id, user.email)}>Del</button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {/* ═══════════════════════ WORKSPACES ═══════════════════════ */}
          {tab === "workspaces" && (
            <section className="module-widget">
              <h3>🏢 All Workspaces ({workspaces.length})</h3>
              <div style={{ marginBottom: 16 }}>
                {showCreate ? (
                  <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                    <input className="os-input" placeholder="Workspace name" value={newName} onChange={(e) => setNewName(e.target.value)} autoFocus />
                    <input className="os-input" placeholder="slug (e.g., my-team)" value={newSlug} onChange={(e) => setNewSlug(e.target.value)} style={{ width: 160 }} />
                    <button className="btn btn-primary" onClick={createWorkspace} disabled={!newName.trim() || !newSlug.trim()}>Create</button>
                    <button className="btn btn-sm" onClick={() => setShowCreate(false)}>Cancel</button>
                  </div>
                ) : (
                  <button className="btn btn-primary" onClick={() => setShowCreate(true)}>+ New Workspace</button>
                )}
              </div>
              <div style={{ overflowX: "auto" }}>
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Slug</th>
                      <th>Plan</th>
                      <th>Members</th>
                      <th>Created</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {workspaces.map((ws) => (
                      <tr key={ws.id}>
                        <td><strong>{ws.name}</strong></td>
                        <td><code style={{ color: "var(--fg-soft)" }}>{ws.slug}</code></td>
                        <td>
                          <span className={`admin-plan-badge plan-${ws.plan}`}>{ws.plan}</span>
                        </td>
                        <td style={{ color: "var(--fg-soft)" }}>{ws.member_count}</td>
                        <td style={{ color: "var(--fg-mute)", fontSize: "0.8rem" }}>
                          {new Date(ws.created_at).toLocaleDateString()}
                        </td>
                        <td>
                          <button className="btn btn-sm btn-danger" onClick={() => deleteWorkspace(ws.id, ws.name)}>Delete</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {/* ═══════════════════════ AUDIT LOG ═══════════════════════ */}
          {tab === "audit" && (
            <section className="module-widget">
              <h3>📋 Audit Log</h3>
              <p style={{ color: "var(--fg-soft)", fontSize: "0.85rem", marginBottom: 16 }}>
                System-wide audit events. For workspace-specific logs, visit the Governance panel.
              </p>
              <AuditLogViewer />
            </section>
          )}
        </>
      )}
    </div>
  );
}

/* ── Audit Log Sub-Component ── */

type AuditRow = {
  id: string;
  action: string;
  module: string;
  email?: string;
  user_id?: string;
  workspace_id?: string;
  metadata: Record<string, any>;
  timestamp: string;
};

function AuditLogViewer() {
  const [rows, setRows] = useState<AuditRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [offset, setOffset] = useState(0);
  const [actionFilter, setActionFilter] = useState("");

  useEffect(() => {
    setLoading(true);
    const params = new URLSearchParams({ limit: "50", offset: String(offset) });
    if (actionFilter) params.set("action", actionFilter);

    fetch(`/api/governance/audit?${params.toString()}`, { cache: "no-store" })
      .then((r) => r.json())
      .then((data) => {
        setRows(data.rows || []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [offset, actionFilter]);

  return (
    <div>
      <div style={{ display: "flex", gap: 12, marginBottom: 16 }}>
        <input
          type="text"
          placeholder="Filter by action"
          value={actionFilter}
          onChange={(e) => { setActionFilter(e.target.value); setOffset(0); }}
          className="input"
          style={{ flex: 1 }}
        />
      </div>

      {loading ? (
        <div style={{ color: "var(--fg-mute)" }}>Loading audit logs…</div>
      ) : (
        <>
          <div style={{ overflowX: "auto" }}>
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Action</th>
                  <th>Module</th>
                  <th>Email</th>
                  <th>Workspace</th>
                  <th>Time</th>
                  <th>Metadata</th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 ? (
                  <tr><td colSpan={6} style={{ textAlign: "center", color: "var(--fg-mute)", padding: 24 }}>No audit entries found</td></tr>
                ) : (
                  rows.map((row) => (
                    <tr key={row.id} style={{ borderBottom: "1px solid var(--border)" }}>
                      <td><code>{row.action}</code></td>
                      <td>{row.module}</td>
                      <td>{row.email || "—"}</td>
                      <td style={{ fontSize: "0.8rem", color: "var(--fg-mute)" }}>
                        {row.workspace_id ? row.workspace_id.substring(0, 8) + "…" : "—"}
                      </td>
                      <td style={{ fontSize: "0.8rem", color: "var(--fg-mute)" }}>
                        {new Date(row.timestamp).toLocaleString()}
                      </td>
                      <td style={{ maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {JSON.stringify(row.metadata).substring(0, 60)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 16 }}>
            <button onClick={() => setOffset((o) => Math.max(0, o - 50))} disabled={offset === 0} className="btn btn-sm">
              ← Previous
            </button>
            <span style={{ fontSize: "0.8rem", color: "var(--fg-mute)" }}>
              Showing {offset + 1}–{offset + rows.length}
            </span>
            <button onClick={() => setOffset((o) => o + 50)} className="btn btn-sm">
              Next →
            </button>
          </div>
        </>
      )}
    </div>
  );
}
