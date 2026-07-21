"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getStoredProvider, setStoredProvider, type StoredProvider } from "@/lib/provider";

const PROVIDERS = [
  {
    id: "openrouter",
    name: "OpenRouter",
    icon: "🌐",
    color: "#5b5bd6",
    models: "Claude 3.5, GPT-4o, Llama 3.1, Qwen, and 100+",
    envVar: "OPENROUTER_API_KEY",
    placeholder: "sk-or-...",
    setupUrl: "https://openrouter.ai/keys",
    desc: "Default provider — one key unlocks hundreds of top-tier models. Includes free models out of the box.",
  },
  {
    id: "openai",
    name: "OpenAI",
    icon: "⚡",
    color: "#10a37f",
    models: "GPT-4o, GPT-4o-mini, GPT-4 Turbo",
    envVar: "OPENAI_API_KEY",
    placeholder: "sk-...",
    setupUrl: "https://platform.openai.com/api-keys",
    desc: "Industry-leading language models with strong reasoning, coding, and instruction-following capabilities.",
  },
  {
    id: "anthropic",
    name: "Anthropic (Claude)",
    icon: "✦",
    color: "#d97706",
    models: "Claude 3.5 Sonnet, Claude 3 Haiku",
    envVar: "ANTHROPIC_API_KEY",
    placeholder: "sk-ant-...",
    setupUrl: "https://console.anthropic.com/",
    desc: "Advanced AI assistants focused on safety, with exceptional reasoning, analysis, and coding abilities.",
  },
  {
    id: "hf",
    name: "Hugging Face",
    icon: "🤗",
    color: "#fbbf24",
    models: "Phi-3, Qwen, Llama, Mistral, and 500k+ models",
    envVar: "HUGGINGFACE_TOKEN",
    placeholder: "hf_...",
    setupUrl: "https://huggingface.co/settings/tokens",
    desc: "Access thousands of open-source models via the Hugging Face Inference API.",
  },
  {
    id: "ollama",
    name: "Ollama (Local)",
    icon: "🦙",
    color: "#8b5cf6",
    models: "Llama 3, Mistral, Gemma, Qwen 2.5",
    envVar: "OLLAMA_BASE_URL",
    placeholder: "http://localhost:11434",
    setupUrl: "https://ollama.ai",
    desc: "Run LLMs locally on your infrastructure. Perfect for air-gapped government deployments.",
  },
  {
    id: "qwen",
    name: "Qwen Local (GPU)",
    icon: "🧠",
    color: "#6366f1",
    models: "Qwen2.5-3B-Instruct (quantized)",
    envVar: "_AEON_QWEN_PATH",
    placeholder: "Auto-downloads on first use",
    setupUrl: null,
    desc: "Built-in small language model that runs on GPU. Downloads automatically — no API key needed.",
  },
  {
    id: "stub",
    name: "Stub (No AI)",
    icon: "◇",
    color: "#71717a",
    models: "Deterministic responses",
    envVar: "AEON_LLM_PROVIDER=stub",
    placeholder: "No key required",
    setupUrl: null,
    desc: "Fallback mode for testing and development. Returns deterministic responses without any API calls.",
  },
];

export default function LLMPage() {
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null);
  const [activeProvider, setActiveProvider] = useState<StoredProvider>(getStoredProvider());
  const [copied, setCopied] = useState<string | null>(null);
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});

  useEffect(() => {
    setActiveProvider(getStoredProvider());
  }, []);

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
        <Link href="/settings" className="btn">
          ⚙ Settings & Keys
        </Link>
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
            AEON OS can switch between any LLM provider at runtime. Set your API keys in Settings, then choose your active provider here or via the <code style={{ background: "var(--bg-elevated)", padding: "2px 6px", borderRadius: 4 }}>AEON_LLM_PROVIDER</code> environment variable.
          </div>
        </div>
      </div>

      {/* Provider Grid */}
      <div className="llm-connector">
        <div className="llm-provider-grid">
          {PROVIDERS.map((provider) => (
            <div
              key={provider.id}
              className={`llm-provider-card ${selectedProvider === provider.id ? "active" : ""}`}
              onClick={() => setSelectedProvider(provider.id === selectedProvider ? null : provider.id)}
            >
              <div className="llm-provider-header">
                <div className="llm-provider-icon" style={{ background: `${provider.color}15`, color: provider.color }}>
                  {provider.icon}
                </div>
                <div>
                  <div className="llm-provider-name">
                    {provider.name}
                    {activeProvider === provider.id && (
                      <span style={{
                        marginLeft: 8,
                        fontSize: "0.65rem",
                        fontWeight: 700,
                        textTransform: "uppercase",
                        letterSpacing: 0.04,
                        padding: "2px 8px",
                        borderRadius: 999,
                        background: "rgba(16,185,129,0.15)",
                        color: "var(--success)",
                      }}>Active</span>
                    )}
                  </div>
                  <div className="llm-provider-model">{provider.models}</div>
                </div>
              </div>

              <div className="llm-provider-desc">{provider.desc}</div>

              <button
                className={`btn btn-sm ${activeProvider === provider.id ? "" : "btn-primary"}`}
                onClick={(e) => {
                  e.stopPropagation();
                  setStoredProvider(provider.id as StoredProvider);
                  setActiveProvider(provider.id as StoredProvider);
                }}
                disabled={activeProvider === provider.id}
                style={{ marginTop: 10, width: "100%" }}
              >
                {activeProvider === provider.id ? "✓ Currently Active" : `Activate ${provider.name}`}
              </button>

              {selectedProvider === provider.id && (
                <div style={{ marginTop: 12 }}>
                  {provider.envVar === "AEON_LLM_PROVIDER=stub" ? (
                    <div style={{
                      background: "rgba(16,185,129,0.08)",
                      border: "1px solid rgba(16,185,129,0.2)",
                      borderRadius: "var(--radius-sm)",
                      padding: "10px 12px",
                      color: "var(--success)",
                      fontSize: "0.82rem",
                    }}>
                      ✓ No API key required. Set <code style={{ background: "var(--bg-elevated)", padding: "2px 4px", borderRadius: 4 }}>AEON_LLM_PROVIDER=stub</code> in your environment.
                    </div>
                  ) : provider.id === "qwen" ? (
                    <div style={{
                      background: "rgba(99,102,241,0.08)",
                      border: "1px solid rgba(99,102,241,0.2)",
                      borderRadius: "var(--radius-sm)",
                      padding: "10px 12px",
                      color: "var(--accent)",
                      fontSize: "0.82rem",
                    }}>
                      ✓ No API key needed. Qwen2.5-3B downloads automatically on first use (requires GPU).
                    </div>
                  ) : (
                    <div>
                      {provider.setupUrl && (
                        <a
                          href={provider.setupUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="btn btn-sm"
                          style={{ marginBottom: 10, display: "inline-flex" }}
                        >
                          Get your {provider.name} API key ↗
                        </a>
                      )}
                      <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                        <input
                          type={showKeys[provider.id] ? "text" : "password"}
                          className="llm-provider-key-input"
                          placeholder={provider.placeholder}
                          readOnly
                          value={provider.envVar}
                          style={{ flex: 1, cursor: "pointer" }}
                          onClick={() => copyToClipboard(provider.envVar)}
                        />
                        <button
                          className="btn btn-sm"
                          onClick={(e) => { e.stopPropagation(); toggleShowKey(provider.id); }}
                          title={showKeys[provider.id] ? "Hide" : "Show"}
                        >
                          {showKeys[provider.id] ? "Hide" : "Show"}
                        </button>
                        <button
                          className="btn btn-sm btn-primary"
                          onClick={(e) => { e.stopPropagation(); copyToClipboard(provider.envVar); }}
                        >
                          {copied === provider.envVar ? "Copied!" : "Copy"}
                        </button>
                      </div>
                      <p style={{ fontSize: "0.72rem", color: "var(--fg-mute)", marginTop: 8 }}>
                        Set <code style={{ background: "var(--bg-elevated)", padding: "2px 4px", borderRadius: 4 }}>{provider.envVar}</code> in your environment variables, then paste the value in the Keys tab.
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Architecture Diagram */}
      <div style={{
        background: "var(--bg-card)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius)",
        padding: 24,
        marginTop: 8,
      }}>
        <h3 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: 16 }}>Architecture: How AEON Routes to Your LLM</h3>
        <div style={{
          display: "flex",
          flexDirection: "column",
          gap: 8,
          fontFamily: "ui-monospace, monospace",
          fontSize: "0.82rem",
          color: "var(--fg-soft)",
          lineHeight: 1.8,
        }}>
          <div>┌─ <strong style={{ color: "var(--fg)" }}>User Query</strong></div>
          <div>│</div>
          <div>├─→ <strong style={{ color: "var(--accent)" }}>AEON OS Kernel</strong> (reflection, goals, memory)</div>
          <div>│</div>
          <div>├─→ <strong style={{ color: "var(--success)" }}>LLM Provider Bridge</strong> (UI selector or AEON_LLM_PROVIDER env)</div>
          <div>│   ├── OpenRouter    ← default (100+ models, one key)</div>
          <div>│   ├── OpenAI        ← if provider=openai</div>
          <div>│   ├── Anthropic     ← if provider=anthropic</div>
          <div>│   ├── HuggingFace   ← if provider=hf</div>
          <div>│   ├── Ollama        ← if provider=ollama</div>
          <div>│   ├── Qwen Local    ← if provider=qwen</div>
          <div>│   └── Stub          ← if provider=stub</div>
          <div>│</div>
          <div>└─→ <strong style={{ color: "var(--fg)" }}>Response</strong> (streamed to UI)</div>
        </div>
      </div>
    </div>
  );
}
