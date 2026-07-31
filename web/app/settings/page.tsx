"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSession, signOut } from "next-auth/react";
import type { ConnectorType } from "@/lib/connectors";
import { CONNECTORS } from "@/lib/connectors";

type SetupKeys = {
  huggingface_token?: { present: boolean; length: number };
  supabase_url?: { present: boolean; host: string | null };
  next_public_supabase_url?: { present: boolean; host: string | null };
  aeon_hf_space_url?: { present: boolean; host: string | null };
  gh_token?: { present: boolean; length: number };
};

type SetupStatus = {
  ok: boolean;
  backend: string;
  keys: SetupKeys;
  notes: string[];
};

type Health = { ok: boolean; backend?: string; ts?: number };

type ConnectorCatalogItem = {
  id: string;
  name: string;
  type: ConnectorType;
  description: string;
  requiredSecrets: string[];
  optionalSecrets: string[];
};

const KEY_DEFINITIONS = [
  {
    id: "openrouter_api_key",
    label: "OpenRouter API Key",
    env: "OPENROUTER_API_KEY",
    desc: "Default provider — access 100+ models (Claude, GPT-4, Llama, Qwen). Get your key at openrouter.ai/keys",
    placeholder: "sk-or-...",
    href: "https://openrouter.ai/keys",
  },
  {
    id: "aeon_llm_provider",
    label: "LLM Provider",
    env: "AEON_LLM_PROVIDER",
    desc: "Server-side default AI backend. Use the LLM Connector page to set the active runtime provider.",
    placeholder: "openrouter / openai / anthropic / hf / stub",
    href: null,
  },
  {
    id: "openai_api_key",
    label: "OpenAI API Key",
    env: "OPENAI_API_KEY",
    desc: "Required for OpenAI provider. Get your key at platform.openai.com",
    placeholder: "sk-...",
    href: "https://platform.openai.com/api-keys",
  },
  {
    id: "anthropic_api_key",
    label: "Anthropic API Key",
    env: "ANTHROPIC_API_KEY",
    desc: "Required for Anthropic provider. Get your key at console.anthropic.com",
    placeholder: "sk-ant-...",
    href: "https://console.anthropic.com/",
  },
  {
    id: "huggingface_token",
    label: "Hugging Face Token",
    env: "HUGGINGFACE_TOKEN",
    desc: "Required for HF provider. Create token at huggingface.co/settings/tokens",
    placeholder: "hf_...",
    href: "https://huggingface.co/settings/tokens",
  },
  {
    id: "supabase_url",
    label: "Supabase Project URL",
    env: "NEXT_PUBLIC_SUPABASE_URL",
    desc: "Your Supabase project URL for memory persistence",
    placeholder: "https://xxx.supabase.co",
    href: "https://supabase.com/dashboard",
  },
  {
    id: "supabase_anon_key",
    label: "Supabase Anon Key",
    env: "NEXT_PUBLIC_SUPABASE_ANON_KEY",
    desc: "Supabase anon/public key for browser-side queries",
    placeholder: "eyJ...",
    href: null,
  },
  {
    id: "gh_token",
    label: "GitHub Token",
    env: "GH_TOKEN",
    desc: "Optional — raises GitHub API rate limit for code search",
    placeholder: "github_pat_...",
    href: "https://github.com/settings/tokens",
  },
];

export default function SettingsPage() {
  const { data: session } = useSession();
  const [health, setHealth] = useState<Health | null>(null);
  const [setup, setSetup] = useState<SetupStatus | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const [connectorCatalog, setConnectorCatalog] = useState<ConnectorCatalogItem[]>([]);
  const [connectorStatus, setConnectorStatus] = useState<
    Record<string, { ok: boolean; message: string }>
  >({});
  const userRole = ((session?.user as any)?.role as string) || "viewer";

  useEffect(() => {
    fetch("/api/health", { cache: "no-store" })
      .then((r) => r.json())
      .then((d) => setHealth(d))
      .catch(() => {});

    fetch("/api/onboarding/status", { cache: "no-store" })
      .then((r) => r.json())
      .then((d) => setSetup(d))
      .catch(() => {});

    fetch("/api/connectors", { cache: "no-store" })
      .then((r) => r.json())
      .then((d) => setConnectorCatalog(d.catalog || []))
      .catch(() => {});
  }, []);

  const copyKey = async (key: string) => {
    try {
      await navigator.clipboard.writeText(key);
      setCopied(key);
      setTimeout(() => setCopied(null), 2000);
    } catch {}
  };

  const testConnector = async (item: ConnectorCatalogItem) => {
    setConnectorStatus((s) => ({ ...s, [item.id]: { ok: false, message: "testing..." } }));
    const secrets: Record<string, string> = {};
    item.requiredSecrets.forEach((k) => {
      secrets[k] = process.env[k] || "";
    });
    try {
      const res = await fetch("/api/connectors", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "test",
          config: { name: item.name, type: item.type, enabled: true, secrets },
        }),
      });
      const data = await res.json();
      setConnectorStatus((s) => ({
        ...s,
        [item.id]: { ok: data.ok, message: data.ok ? "connected" : data.error || "failed" },
      }));
    } catch (e: any) {
      setConnectorStatus((s) => ({
        ...s,
        [item.id]: { ok: false, message: e?.message || "error" },
      }));
    }
  };

  const keyStatus = (envName: string): "connected" | "disconnected" | "pending" => {
    if (!setup?.keys) return "pending";
    const k = setup.keys as any;
    for (const [key, val] of Object.entries(k)) {
      if (key.replace(/_/g, "").includes(envName.replace(/_/g, "").toLowerCase())) {
        return (val as any)?.present ? "connected" : "disconnected";
      }
    }
    return "disconnected";
  };

  return (
    <div className="settings-page">
      <h1>⚙ Settings & Keys</h1>
      <p>Configure your AEON OS instance. Add API keys to connect your preferred LLM backend.</p>

      {/* System Health */}
      <div className="settings-section">
        <div className="settings-section-header">
          <span style={{ fontSize: "1.2rem" }}>⟁</span>
          <div>
            <h2>System Status</h2>
            <p>AEON OS runtime health and configuration</p>
          </div>
        </div>
        <div className="settings-item">
          <div>
            <div className="settings-item-label">Backend Status</div>
            <div className="settings-item-desc">AI inference backend</div>
          </div>
          <div className="settings-item-right">
            <span className={`settings-status ${health?.ok ? "connected" : "disconnected"}`}>
              {health === null
                ? "..."
                : health.ok
                  ? `Online · ${health.backend || "stub"}`
                  : "Offline"}
            </span>
          </div>
        </div>
        <div className="settings-item">
          <div>
            <div className="settings-item-label">System Version</div>
            <div className="settings-item-desc">AEON kernel</div>
          </div>
          <div className="settings-item-right">
            <span
              style={{
                color: "var(--fg-soft)",
                fontFamily: "ui-monospace, monospace",
                fontSize: "0.85rem",
              }}
            >
              v3.0
            </span>
          </div>
        </div>
        <div className="settings-item">
          <div>
            <div className="settings-item-label">Missing Integrations</div>
            <div className="settings-item-desc">Unconfigured services</div>
          </div>
          <div className="settings-item-right">
            <span
              className={`settings-status ${(setup?.notes?.length || 0) > 0 ? "disconnected" : "connected"}`}
            >
              {setup?.notes?.length || 0} items
            </span>
          </div>
        </div>
      </div>

      {/* Account & Security */}
      <div className="settings-section">
        <div className="settings-section-header">
          <span style={{ fontSize: "1.2rem" }}>👤</span>
          <div>
            <h2>Account & Security</h2>
            <p>Current session and role</p>
          </div>
        </div>
        <div className="settings-item">
          <div>
            <div className="settings-item-label">Logged in as</div>
            <div className="settings-item-desc">{session?.user?.email || "Guest"}</div>
          </div>
          <span className={`settings-status ${session?.user ? "connected" : "disconnected"}`}>
            {session?.user ? "Active" : "Anonymous"}
          </span>
        </div>
        <div className="settings-item">
          <div>
            <div className="settings-item-label">Role</div>
            <div className="settings-item-desc">RBAC level for this session</div>
          </div>
          <span
            style={{
              color: "var(--fg-soft)",
              fontFamily: "ui-monospace, monospace",
              fontSize: "0.85rem",
              textTransform: "uppercase",
            }}
          >
            {userRole}
          </span>
        </div>
        <div className="settings-item">
          <div>
            <div className="settings-item-label">Session</div>
            <div className="settings-item-desc">Sign out to end this session</div>
          </div>
          <button className="btn btn-sm" onClick={() => signOut({ callbackUrl: "/login" })}>
            Sign out
          </button>
        </div>
      </div>

      {/* LLM Provider Keys */}
      <div className="settings-section">
        <div className="settings-section-header">
          <span style={{ fontSize: "1.2rem" }}>⚡</span>
          <div>
            <h2>LLM Provider Keys</h2>
            <p>Connect your AI brain — add API keys for any supported provider</p>
          </div>
        </div>
        {KEY_DEFINITIONS.slice(0, 4).map((keyDef) => (
          <div key={keyDef.id} className="settings-item">
            <div>
              <div className="settings-item-label">{keyDef.label}</div>
              <div className="settings-item-desc">
                {keyDef.desc}
                {keyDef.href && (
                  <>
                    {" · "}
                    <a
                      href={keyDef.href}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ color: "var(--accent)" }}
                    >
                      Get key ↗
                    </a>
                  </>
                )}
              </div>
            </div>
            <div className="settings-item-right">
              <span className={`settings-status ${keyStatus(keyDef.env)}`}>
                {keyStatus(keyDef.env) === "connected" ? "✓ Set" : "Not set"}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Infrastructure Keys */}
      <div className="settings-section">
        <div className="settings-section-header">
          <span style={{ fontSize: "1.2rem" }}>🔌</span>
          <div>
            <h2>Infrastructure & Storage</h2>
            <p>Memory persistence, code search, and deployment configuration</p>
          </div>
        </div>
        {KEY_DEFINITIONS.slice(4).map((keyDef) => (
          <div key={keyDef.id} className="settings-item">
            <div>
              <div className="settings-item-label">{keyDef.label}</div>
              <div className="settings-item-desc">
                {keyDef.desc}
                {keyDef.href && (
                  <>
                    {" · "}
                    <a
                      href={keyDef.href}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ color: "var(--accent)" }}
                    >
                      {keyDef.id === "gh_token" ? "Create token ↗" : "Open dashboard ↗"}
                    </a>
                  </>
                )}
              </div>
            </div>
            <div className="settings-item-right">
              <span className={`settings-status ${keyStatus(keyDef.env)}`}>
                {keyStatus(keyDef.env) === "connected" ? "✓ Set" : "Not set"}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Quick Guide */}
      <div className="settings-section">
        <div className="settings-section-header">
          <span style={{ fontSize: "1.2rem" }}>📖</span>
          <div>
            <h2>Quick Start Guide</h2>
            <p>Get AEON OS running in minutes</p>
          </div>
        </div>
        <div className="settings-item">
          <div>
            <div className="settings-item-label">1. Connect your LLM</div>
            <div className="settings-item-desc">
              Add an OpenAI, Anthropic, or HuggingFace API key above, or use stub mode
            </div>
          </div>
          <Link href="/llm" className="btn btn-sm btn-primary">
            Connect
          </Link>
        </div>
        <div className="settings-item">
          <div>
            <div className="settings-item-label">2. Launch a module</div>
            <div className="settings-item-desc">
              Open any industry module to see autonomous AI in action
            </div>
          </div>
          <Link href="/os" className="btn btn-sm">
            Open OS
          </Link>
        </div>
        <div className="settings-item">
          <div>
            <div className="settings-item-label">3. Set your provider</div>
            <div className="settings-item-desc">
              Set AEON_LLM_PROVIDER env var to your chosen backend
            </div>
          </div>
          <button className="btn btn-sm" onClick={() => copyKey("AEON_LLM_PROVIDER")}>
            {copied === "AEON_LLM_PROVIDER" ? "Copied!" : "Copy env name"}
          </button>
        </div>
      </div>

      {/* Enterprise Connectors */}
      <div className="settings-section">
        <div className="settings-section-header">
          <span style={{ fontSize: "1.2rem" }}>🔌</span>
          <div>
            <h2>Enterprise Connectors</h2>
            <p>Secure data sources for RAG and workflow automation</p>
          </div>
        </div>
        {connectorCatalog.length === 0 ? (
          <div className="settings-item">
            <div>
              <div className="settings-item-label">No connectors configured</div>
              <div className="settings-item-desc">Check your API access or contact an admin.</div>
            </div>
          </div>
        ) : (
          connectorCatalog.map((item) => (
            <div key={item.id} className="settings-item">
              <div>
                <div className="settings-item-label">{item.name}</div>
                <div className="settings-item-desc">{item.description}</div>
                <div className="settings-item-desc" style={{ marginTop: 4 }}>
                  Required: {item.requiredSecrets.join(", ") || "none"}
                </div>
              </div>
              <div className="settings-item-right">
                <button
                  className="btn btn-sm"
                  onClick={() => testConnector(item)}
                  disabled={!["ADMIN", "OPERATOR"].includes(userRole)}
                >
                  {connectorStatus[item.id]?.message || "Test"}
                </button>
                {connectorStatus[item.id] && (
                  <span
                    className={`settings-status ${
                      connectorStatus[item.id].ok ? "connected" : "disconnected"
                    }`}
                    style={{ marginLeft: 8 }}
                  >
                    {connectorStatus[item.id].ok ? "✓" : "✕"}
                  </span>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Workspace Branding */}
      <div className="settings-section">
        <div className="settings-section-header">
          <span style={{ fontSize: "1.2rem" }}>🎨</span>
          <div>
            <h2>Workspace Branding</h2>
            <p>Customize the look and feel for your company or organization</p>
          </div>
        </div>
        <div className="settings-item">
          <div>
            <div className="settings-item-label">Company Branding</div>
            <div className="settings-item-desc">
              Edit company name, product name, logo, primary color, and module toggles
            </div>
          </div>
          <Link href="/settings/branding" className="btn btn-sm btn-primary">
            Customize
          </Link>
        </div>
      </div>

      {/* Workspace Info */}
      <div className="settings-section">
        <div className="settings-section-header">
          <span style={{ fontSize: "1.2rem" }}>🛡️</span>
          <div>
            <h2>Workspace & RBAC</h2>
            <p>Current workspace and permission level</p>
          </div>
        </div>
        <div className="settings-item">
          <div>
            <div className="settings-item-label">Current Role</div>
            <div className="settings-item-desc">Determines what actions you can perform</div>
          </div>
          <span
            className={`settings-status ${userRole === "ADMIN" ? "connected" : "disconnected"}`}
          >
            {userRole.toUpperCase()}
          </span>
        </div>
        <div className="settings-item">
          <div>
            <div className="settings-item-label">Workspace ID</div>
            <div className="settings-item-desc">Active workspace context for data isolation</div>
          </div>
          <span
            style={{
              color: "var(--fg-soft)",
              fontFamily: "ui-monospace, monospace",
              fontSize: "0.85rem",
            }}
          >
            {(session?.user as any)?.workspaceId || "default"}
          </span>
        </div>
      </div>
    </div>
  );
}
