"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

interface ProviderMeta {
  id: string;
  name: string;
  icon: string;
  color: string;
  models: string[];
  configured: boolean;
  active: boolean;
  env_var: string | null;
  desc: string;
}

const FALLBACK_PROVIDERS: ProviderMeta[] = [
  { id: "stub", name: "Stub (No AI)", icon: "◇", color: "#71717a", models: ["deterministic stub"], configured: true, active: false, env_var: null, desc: "Fallback mode for testing. Returns deterministic responses." },
  { id: "openai", name: "OpenAI", icon: "⚡", color: "#10a37f", models: ["gpt-4o-mini", "gpt-4o"], configured: false, active: false, env_var: "OPENAI_API_KEY", desc: "Industry-leading language models with strong reasoning and coding capabilities." },
  { id: "anthropic", name: "Anthropic (Claude)", icon: "✦", color: "#d97706", models: ["claude-3-5-sonnet", "claude-3-haiku"], configured: false, active: false, env_var: "ANTHROPIC_API_KEY", desc: "Advanced AI with exceptional reasoning and analysis." },
  { id: "ollama", name: "Ollama (Local)", icon: "🦙", color: "#8b5cf6", models: ["llama3", "mistral", "gemma"], configured: true, active: false, env_var: "OLLAMA_BASE_URL", desc: "Run LLMs locally on your infrastructure." },
  { id: "hf", name: "Hugging Face", icon: "🤗", color: "#fbbf24", models: ["Qwen2.5-3B-Instruct", "Phi-3"], configured: false, active: false, env_var: "HUGGINGFACE_TOKEN", desc: "Access thousands of open-source models via the HF Inference API." },
  { id: "qwen", name: "Qwen Local (GPU)", icon: "🧠", color: "#6366f1", models: ["Qwen2.5-3B (quantized)"], configured: true, active: false, env_var: null, desc: "Built-in small language model on GPU. Downloads automatically." },
];

export default function LLMPage() {
  const [providers, setProviders] = useState<ProviderMeta[]>(FALLBACK_PROVIDERS);
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null);
  const [activeProvider, setActiveProvider] = useState<string>("");
  const [testResult, setTestResult] = useState<string | null>(null);
  const [testLoading, setTestLoading] = useState<string | null>(null);
  const [switchLoading, setSwitchLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});

  useEffect(() => {
    loadProviders();
  }, []);

  const loadProviders = async () => {
    try {
      const res = await fetch("/api/llm/providers");
      const data = await res.json();
      if (data.ok && data.providers?.length) {
        setProviders(data.providers);
        const active = data.providers.find((p: ProviderMeta) => p.active);
        if (active) setActiveProvider(active.id);
      }
    } catch {
      // fallback already set
    }
  };

  const activateProvider = async (id: string) => {
    setSwitchLoading(id);
    setError(null);
    try {
      const res = await fetch("/api/llm/switch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider: id }),
      });
      const data = await res.json();
      if (data.ok) {
        setActiveProvider(id);
        setProviders((prev) =>
          prev.map((p) => ({ ...p, active: p.id === id }))
        );
      } else {
        setError(data.error || "Failed to switch provider");
      }
    } catch (e: any) {
      setError(e.message || "Failed to switch provider");
    } finally {
      setSwitchLoading(null);
    }
  };

  const testProvider = async (id: string) => {
    setTestLoading(id);
    setTestResult(null);
    setError(null);
    try {
      const res = await fetch("/api/llm/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider: id }),
      });
      const data = await res.json();
      if (data.ok) {
        setTestResult(
          `✅ ${data.backend}: ${data.text.slice(0, 100)} (${data.latency_s}s, ${data.tokens_used} tokens)`
        );
      } else {
        setTestResult(`❌ ${data.error || "Test failed"}`);
      }
    } catch (e: any) {
      setTestResult(`❌ ${e.message}`);
    } finally {
      setTestLoading(null);
    }
  };

  const toggleShowKey = (id: string) => {
    setShowKeys((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(text);
      setTimeout(() => setCopied(null), 2000);
    } catch {}
  };

  const setupUrls: Record<string, string> = {
    openai: "https://platform.openai.com/api-keys",
    anthropic: "https://console.anthropic.com/",
    hf: "https://huggingface.co/settings/tokens",
    ollama: "https://ollama.ai",
  };

  return (
    <div className="dashboard">
      {/* Header */}
      <div className="dashboard-header">
        <div>
          <h1 className="dashboard-title">⚡ LLM Brain Connector</h1>
          <p className="dashboard-subtitle">
            Connect any AI provider to power AEON OS. Hot-swappable — change anytime.
          </p>
        </div>
        <button className="btn" onClick={loadProviders}>
          ↻ Refresh
        </button>
      </div>

      {/* Status Banner */}
      <div style={{
        background: "rgba(99,102,241,0.08)",
        border: "1px solid rgba(99,102,241,0.2)",
        borderRadius: "var(--radius)",
        padding: "16px 20px",
        marginBottom: 24,
        display: "flex",
        alignItems: "center",
        gap: 12,
      }}>
        <span style={{ fontSize: "1.2rem" }}>💡</span>
        <div>
          <div style={{ fontWeight: 600, marginBottom: 2 }}>Plug-and-Play Architecture</div>
          <div style={{ fontSize: "0.82rem", color: "var(--fg-soft)" }}>
            AEON OS can switch between any LLM provider at runtime. Active provider: <strong>{activeProvider || "stub"}</strong>.
            Set your API keys in the <strong>Keys / API Keys</strong> tab, then switch here.
          </div>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div style={{
          background: "rgba(239,68,68,0.08)",
          border: "1px solid rgba(239,68,68,0.2)",
          borderRadius: "var(--radius)",
          padding: "12px 16px",
          marginBottom: 16,
          color: "var(--danger)",
          fontSize: "0.85rem",
        }}>
          {error}
        </div>
      )}

      {/* Test Result Banner */}
      {testResult && (
        <div style={{
          background: testResult.startsWith("✅") ? "rgba(16,185,129,0.08)" : "rgba(239,68,68,0.08)",
          border: `1px solid ${testResult.startsWith("✅") ? "rgba(16,185,129,0.2)" : "rgba(239,68,68,0.2)"}`,
          borderRadius: "var(--radius)",
          padding: "12px 16px",
          marginBottom: 16,
          fontSize: "0.85rem",
          fontFamily: "ui-monospace, monospace",
        }}>
          {testResult}
        </div>
      )}

      {/* Provider Grid */}
      <div className="llm-connector">
        <div className="llm-provider-grid">
          {providers.map((provider) => (
            <div
              key={provider.id}
              className={`llm-provider-card ${selectedProvider === provider.id ? "active" : ""} ${provider.active ? "provider-active" : ""}`}
              onClick={() => setSelectedProvider(provider.id === selectedProvider ? null : provider.id)}
            >
              <div className="llm-provider-header">
                <div className="llm-provider-icon" style={{ background: `${provider.color}15`, color: provider.color }}>
                  {provider.icon}
                </div>
                <div>
                  <div className="llm-provider-name">
                    {provider.name}
                    {provider.active && (
                      <span className="status-badge active-badge">Active</span>
                    )}
                    {!provider.configured && !provider.active && (
                      <span className="status-badge missing-key-badge">No Key</span>
                    )}
                  </div>
                  <div className="llm-provider-model">{provider.models.join(", ")}</div>
                </div>
              </div>

              <div className="llm-provider-desc">{provider.desc}</div>

              <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
                <button
                  className={`btn btn-sm ${provider.active ? "btn-success" : "btn-primary"}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    activateProvider(provider.id);
                  }}
                  disabled={provider.active || switchLoading === provider.id}
                  style={{ flex: 1 }}
                >
                  {switchLoading === provider.id
                    ? "Switching..."
                    : provider.active
                    ? "✓ Active"
                    : `Activate`}
                </button>
                <button
                  className="btn btn-sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    testProvider(provider.id);
                  }}
                  disabled={testLoading === provider.id}
                >
                  {testLoading === provider.id ? "Testing..." : "Test"}
                </button>
              </div>

              {selectedProvider === provider.id && (
                <div style={{ marginTop: 12 }}>
                  {provider.id === "stub" || provider.id === "qwen" ? (
                    <div className="info-box">
                      {provider.id === "stub"
                        ? "✓ No API key required. Returns deterministic responses for testing."
                        : "✓ No API key needed. Qwen2.5-3B downloads automatically on first use (requires GPU)."}
                    </div>
                  ) : (
                    <div>
                      {setupUrls[provider.id] && (
                        <a
                          href={setupUrls[provider.id]}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="btn btn-sm"
                          style={{ marginBottom: 10, display: "inline-flex" }}
                        >
                          Get {provider.name} API key ↗
                        </a>
                      )}
                      <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                        <input
                          type={showKeys[provider.id] ? "text" : "password"}
                          className="llm-provider-key-input"
                          placeholder={provider.env_var || "No key needed"}
                          readOnly
                          value={provider.env_var || "(no key needed)"}
                          style={{ flex: 1, cursor: "pointer" }}
                          onClick={() => provider.env_var && copyToClipboard(provider.env_var)}
                        />
                        {provider.env_var && (
                          <>
                            <button
                              className="btn btn-sm"
                              onClick={(e) => { e.stopPropagation(); toggleShowKey(provider.id); }}
                            >
                              {showKeys[provider.id] ? "Hide" : "Show"}
                            </button>
                            <button
                              className="btn btn-sm btn-primary"
                              onClick={(e) => { e.stopPropagation(); copyToClipboard(provider.env_var!); }}
                            >
                              {copied === provider.env_var ? "Copied!" : "Copy"}
                            </button>
                          </>
                        )}
                      </div>
                      {provider.env_var && (
                        <p style={{ fontSize: "0.72rem", color: "var(--fg-mute)", marginTop: 8 }}>
                          Set <code style={{ background: "var(--bg-elevated)", padding: "2px 4px", borderRadius: 4 }}>{provider.env_var}</code> in the <strong>Keys / API Keys</strong> tab, then refresh this page.
                        </p>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Architecture Diagram */}
      <div className="arch-diagram">
        <h3 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: 16 }}>Architecture: How AEON Routes to Your LLM</h3>
        <div className="arch-tree">
          <div>┌─ <strong>User Query</strong></div>
          <div>│</div>
          <div>├─→ <strong className="accent">AEON OS Kernel</strong> (reflection, goals, memory)</div>
          <div>│</div>
          <div>├─→ <strong className="success">LLM Provider Bridge</strong> (UI selector or AEON_LLM_PROVIDER env)</div>
          {providers.map((p) => (
            <div key={p.id}>
              │   {p.active ? "●" : "○"}── {p.name}{p.active ? " ← active" : ""}
            </div>
          ))}
          <div>│</div>
          <div>└─→ <strong>Response</strong> (streamed to UI)</div>
        </div>
      </div>
    </div>
  );
}
