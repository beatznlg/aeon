"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSession } from "next-auth/react";

type ApiKey = {
  id: string;
  name: string;
  prefix: string;
  workspace_id: string;
  user_id?: string;
  enabled: boolean;
  rate_limit_per_min: number;
  created_at: number;
  last_used_at?: number;
  expires_at?: number;
};

type UsageStats = {
  total_calls: number;
  errors: number;
  error_rate: number;
  total_keys: number;
  active_keys: number;
  by_key: { key_id: string; name: string; calls: number; errors: number }[];
  by_endpoint: Record<string, number>;
};

export default function ApiKeysPage() {
  const { data: session } = useSession();
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [usage, setUsage] = useState<UsageStats | null>(null);
  const [loading, setLoading] = useState(true);

  const [showCreate, setShowCreate] = useState(false);
  const [newKeyName, setNewKeyName] = useState("");
  const [newKeyRateLimit, setNewKeyRateLimit] = useState("100");
  const [createdKey, setCreatedKey] = useState<{ key: ApiKey; plaintext: string } | null>(null);
  const [copied, setCopied] = useState(false);

  const [revoking, setRevoking] = useState<string | null>(null);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const [keysRes, usageRes] = await Promise.all([
        fetch("/api/api-keys", { cache: "no-store" }),
        fetch("/api/api-keys/usage/summary", { cache: "no-store" }),
      ]);
      const keysData = await keysRes.json();
      const usageData = await usageRes.json();
      if (keysData.ok) setKeys(keysData.keys || []);
      if (usageData.ok) setUsage(usageData.usage);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const createKey = async () => {
    if (!newKeyName.trim()) return;
    setMessage(null);
    try {
      const res = await fetch("/api/api-keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: newKeyName.trim(),
          rate_limit_per_min: parseInt(newKeyRateLimit) || 100,
        }),
      });
      const data = await res.json();
      if (data.ok && data.key && data.plaintext_key) {
        setCreatedKey({ key: data.key, plaintext: data.plaintext_key });
        setKeys((prev) => [data.key, ...prev]);
        setNewKeyName("");
        setNewKeyRateLimit("100");
      } else {
        setMessage({ ok: false, text: data.error || "Failed to create key" });
      }
    } catch (e: any) {
      setMessage({ ok: false, text: e?.message || "Network error" });
    }
  };

  const revokeKey = async (keyId: string) => {
    if (!confirm("Revoke this API key? This action cannot be undone.")) return;
    setRevoking(keyId);
    setMessage(null);
    try {
      const res = await fetch(`/api/api-keys/${keyId}`, { method: "DELETE" });
      const data = await res.json();
      if (data.ok) {
        setKeys((prev) => prev.filter((k) => k.id !== keyId));
        setMessage({ ok: true, text: "API key revoked" });
      } else {
        setMessage({ ok: false, text: data.error || "Failed to revoke" });
      }
    } catch (e: any) {
      setMessage({ ok: false, text: e?.message || "Network error" });
    } finally {
      setRevoking(null);
    }
  };

  const toggleKey = async (keyId: string, enabled: boolean) => {
    try {
      const res = await fetch(`/api/api-keys/${keyId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: !enabled }),
      });
      const data = await res.json();
      if (data.ok) {
        setKeys((prev) => prev.map((k) => (k.id === keyId ? { ...k, enabled: !enabled } : k)));
      }
    } catch {}
  };

  const copyKey = (text: string) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    });
  };

  const dismissCreated = () => {
    setCreatedKey(null);
    setShowCreate(false);
  };

  if (loading) {
    return (
      <div className="os-page">
        <div style={{ padding: 40, textAlign: "center", color: "var(--fg-mute)" }}>Loading API keys…</div>
      </div>
    );
  }

  return (
    <div className="os-page">
      <header className="os-header">
        <div>
          <Link href="/os" className="os-back">← OS Launcher</Link>
          <h1>🔑 API Keys</h1>
          <p className="dashboard-subtitle">Manage API keys for external access, rate limits, and usage tracking</p>
        </div>
      </header>

      {message && (
        <div className={`module-alert ${message.ok ? "" : "danger"}`} style={{ marginBottom: 20 }}>
          {message.text}
        </div>
      )}

      {/* ── Usage Summary ── */}
      {usage && (
        <section className="billing-status-bar" style={{ marginBottom: 24 }}>
          <div className="billing-status-item">
            <span className="billing-status-label">Total Keys</span>
            <span className="billing-status-value">{usage.total_keys}</span>
          </div>
          <div className="billing-status-item">
            <span className="billing-status-label">Active</span>
            <span className="billing-status-value" style={{ color: usage.active_keys > 0 ? "#22c55e" : "#94a3b8" }}>
              {usage.active_keys}
            </span>
          </div>
          <div className="billing-status-item">
            <span className="billing-status-label">API Calls (30d)</span>
            <span className="billing-status-value">{usage.total_calls.toLocaleString()}</span>
          </div>
          <div className="billing-status-item">
            <span className="billing-status-label">Error Rate</span>
            <span className="billing-status-value" style={{ color: usage.error_rate > 5 ? "#ef4444" : "#22c55e" }}>
              {usage.error_rate}%
            </span>
          </div>
        </section>
      )}

      {/* ── Create Key Dialog ── */}
      {!createdKey && (
        <section className="module-widget" style={{ marginBottom: 24 }}>
          <h3>{showCreate ? "➕ New API Key" : "🔑 API Keys"}</h3>
          {showCreate ? (
            <div>
              <input
                className="os-input"
                placeholder="Key name (e.g., Production API Key)"
                value={newKeyName}
                onChange={(e) => setNewKeyName(e.target.value)}
                autoFocus
              />
              <div style={{ marginTop: 8, display: "flex", gap: 8, alignItems: "center" }}>
                <label style={{ fontSize: "0.82rem", color: "var(--fg-soft)" }}>Rate limit (req/min):</label>
                <input
                  className="os-input"
                  type="number"
                  min={1}
                  max={10000}
                  value={newKeyRateLimit}
                  onChange={(e) => setNewKeyRateLimit(e.target.value)}
                  style={{ width: 100 }}
                />
              </div>
              <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
                <button className="btn btn-primary" onClick={createKey} disabled={!newKeyName.trim()}>
                  Generate Key
                </button>
                <button className="btn btn-sm" onClick={() => setShowCreate(false)}>
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
              + Generate New Key
            </button>
          )}
        </section>
      )}

      {/* ── Newly Created Key (shown once) ── */}
      {createdKey && (
        <section className="module-widget api-key-created-card" style={{ marginBottom: 24, borderColor: "#22c55e" }}>
          <h3 style={{ color: "#22c55e" }}>✅ Key Created — Copy It Now</h3>
          <p style={{ color: "var(--fg-soft)", fontSize: "0.85rem", marginBottom: 12 }}>
            This is the <strong>only time</strong> the full key will be shown. Store it securely.
          </p>
          <div className="api-key-plaintext-row">
            <code className="api-key-plaintext">{createdKey.plaintext}</code>
            <button className="btn btn-primary btn-sm" onClick={() => copyKey(createdKey.plaintext)}>
              {copied ? "Copied!" : "📋 Copy"}
            </button>
          </div>
          <p style={{ marginTop: 12, fontSize: "0.8rem", color: "var(--fg-mute)" }}>
            Prefix: <code>{createdKey.key.prefix}</code> · Name: {createdKey.key.name}
          </p>
          <button className="btn btn-sm" onClick={dismissCreated} style={{ marginTop: 8 }}>
            Done
          </button>
        </section>
      )}

      {/* ── Key List ── */}
      <section className="module-widget">
        <h3>🔑 Active Keys ({keys.length})</h3>
        {keys.length === 0 ? (
          <p className="module-empty">
            No API keys yet. Generate one to start integrating external services.
          </p>
        ) : (
          <div className="api-key-list">
            {keys.map((key) => (
              <div key={key.id} className="api-key-item">
                <div className="api-key-item-left">
                  <div className="api-key-item-header">
                    <strong>{key.name}</strong>
                    <span className={`api-key-badge ${key.enabled ? "active" : "disabled"}`}>
                      {key.enabled ? "Active" : "Disabled"}
                    </span>
                  </div>
                  <div className="api-key-meta">
                    <code className="api-key-prefix">{key.prefix}</code>
                    <span className="api-key-rate">⏱ {key.rate_limit_per_min}/min</span>
                    {key.last_used_at ? (
                      <span className="api-key-last-used">
                        Last used: {new Date(key.last_used_at * 1000).toLocaleDateString()}
                      </span>
                    ) : (
                      <span className="api-key-last-used" style={{ color: "var(--fg-mute)" }}>
                        Never used
                      </span>
                    )}
                    <span className="api-key-created">
                      Created: {new Date(key.created_at * 1000).toLocaleDateString()}
                    </span>
                  </div>
                </div>
                <div className="api-key-item-right">
                  <span
                    className="api-key-toggle"
                    onClick={() => toggleKey(key.id, key.enabled)}
                    title={key.enabled ? "Disable" : "Enable"}
                  >
                    {key.enabled ? "🔓" : "🔒"}
                  </span>
                  <button
                    className="btn btn-sm btn-danger"
                    onClick={() => revokeKey(key.id)}
                    disabled={revoking === key.id}
                  >
                    {revoking === key.id ? "..." : "× Revoke"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* ── Top Endpoints ── */}
      {usage?.by_endpoint && Object.keys(usage.by_endpoint).length > 0 && (
        <section className="module-widget" style={{ marginTop: 24 }}>
          <h3>📊 Top Endpoints</h3>
          <div className="api-key-endpoints">
            {Object.entries(usage.by_endpoint).slice(0, 10).map(([endpoint, count]) => (
              <div key={endpoint} className="api-key-endpoint-item">
                <code className="api-key-endpoint-path">{endpoint}</code>
                <span className="api-key-endpoint-count">{count} calls</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ── Rate Limit Info ── */}
      <section className="module-widget" style={{ marginTop: 24 }}>
        <h3>⚡ Rate Limiting</h3>
        <p style={{ color: "var(--fg-soft)", fontSize: "0.85rem", marginBottom: 12 }}>
          Each API key has a configurable rate limit (requests per minute). When exceeded, the API returns HTTP 429.
          Adjust rate limits when creating a key or by updating an existing key via the API.
        </p>
        <div className="api-key-rate-info">
          <div className="api-key-rate-card">
            <div className="api-key-rate-label">Default</div>
            <div className="api-key-rate-value">100 req/min</div>
          </div>
          <div className="api-key-rate-card">
            <div className="api-key-rate-label">Max</div>
            <div className="api-key-rate-value">10,000 req/min</div>
          </div>
          <div className="api-key-rate-card">
            <div className="api-key-rate-label">Sliding Window</div>
            <div className="api-key-rate-value">60 seconds</div>
          </div>
          <div className="api-key-rate-card">
            <div className="api-key-rate-label">Auth Method</div>
            <div className="api-key-rate-value">Bearer Token</div>
          </div>
        </div>
      </section>
    </div>
  );
}
