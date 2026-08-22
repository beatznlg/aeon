"use client";

import { useEffect, useState } from "react";

interface ProviderMeta {
  id: string;
  name: string;
  icon: string;
  color: string;
  models: string[];
  model?: string;
  configured: boolean;
  active: boolean;
  env_var: string | null;
  base_url_env?: string;
  model_env_var?: string;
  desc: string;
}

const PROVIDERS: ProviderMeta[] = [
  {
    id: "openai",
    name: "OpenAI",
    icon: "⚡",
    color: "#10a37f",
    models: ["gpt-5.6", "gpt-5-mini", "gpt-4.1", "gpt-4.1-mini", "o3-pro"],
    configured: false,
    active: false,
    env_var: "OPENAI_API_KEY",
    desc: "Industry-leading models for reasoning, coding, and analysis.",
  },
  {
    id: "anthropic",
    name: "Anthropic",
    icon: "✦",
    color: "#d97706",
    models: ["claude-opus-4-1", "claude-sonnet-4-20250514", "claude-3-7-sonnet-latest", "claude-3-5-haiku-latest"],
    configured: false,
    active: false,
    env_var: "ANTHROPIC_API_KEY",
    desc: "Advanced reasoning with Claude models.",
  },
  {
    id: "google",
    name: "Google Gemini",
    icon: "◆",
    color: "#4285f4",
    models: ["gemini-3.7-flash", "gemini-3.1-pro", "gemini-3.1-flash-lite"],
    configured: false,
    active: false,
    env_var: "GEMINI_API_KEY",
    desc: "Multimodal models through Google's API.",
  },
  {
    id: "openrouter",
    name: "OpenRouter",
    icon: "◈",
    color: "#7c3aed",
    models: ["openai/gpt-4.1-mini", "anthropic/claude-sonnet-4", "google/gemini-3.7-flash", "meta-llama/llama-4-scout"],
    configured: false,
    active: false,
    env_var: "OPENROUTER_API_KEY",
    desc: "Access hundreds of models with one API key.",
  },
  {
    id: "mistral",
    name: "Mistral",
    icon: "◆",
    color: "#f97316",
    models: ["mistral-large-latest", "mistral-medium-latest", "mistral-small-latest"],
    configured: false,
    active: false,
    env_var: "MISTRAL_API_KEY",
    desc: "Fast, efficient models for enterprise use.",
  },
  {
    id: "ollama",
    name: "Ollama (Local)",
    icon: "🦙",
    color: "#8b5cf6",
    models: ["llama3.1", "qwen2.5", "gemma3", "mistral"],
    configured: true,
    active: false,
    env_var: "OLLAMA_BASE_URL",
    desc: "Run models locally on your machine.",
  },
  {
    id: "custom",
    name: "Custom Endpoint",
    icon: "✚",
    color: "#22c55e",
    models: ["custom-model"],
    configured: false,
    active: false,
    env_var: "AEON_CUSTOM_LLM_API_KEY",
    base_url_env: "AEON_CUSTOM_LLM_BASE_URL",
    model_env_var: "AEON_CUSTOM_LLM_MODEL",
    desc: "Connect any OpenAI-compatible API.",
  },
  {
    id: "stub",
    name: "Stub (No AI)",
    icon: "◇",
    color: "#71717a",
    models: ["deterministic stub"],
    configured: true,
    active: false,
    env_var: null,
    desc: "Testing mode — no API key needed.",
  },
];

export default function LLMPage() {
  const [providers, setProviders] = useState<ProviderMeta[]>(PROVIDERS);
  const [activeProvider, setActiveProvider] = useState<string>("");
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState<string>("");
  const [apiKey, setApiKey] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showKey, setShowKey] = useState(false);

  useEffect(() => {
    loadProviders();
    loadPreference();
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
    } catch {}
  };

  const loadPreference = async () => {
    try {
      const res = await fetch("/api/llm/preferences", { cache: "no-store" });
      const data = await res.json();
      if (data.ok && data.preference?.provider) {
        setActiveProvider(data.preference.provider);
        if (data.preference.model) setSelectedModel(data.preference.model);
      }
    } catch {}
  };

  const activateProvider = async () => {
    if (!selectedProvider) return;
    setSaving(true);
    setError(null);
    try {
      const res = await fetch("/api/llm/switch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider: selectedProvider, model: selectedModel || undefined }),
      });
      const data = await res.json();
      if (data.ok) {
        setActiveProvider(selectedProvider);
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
      } else {
        setError(data.error || "Failed to save");
      }
    } catch (e: any) {
      setError(e.message || "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const testProvider = async () => {
    if (!selectedProvider) return;
    setTesting(true);
    setTestResult(null);
    try {
      const res = await fetch("/api/llm/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider: selectedProvider, model: selectedModel || undefined }),
      });
      const data = await res.json();
      if (data.ok) {
        setTestResult(`✅ ${data.text.slice(0, 80)} (${data.latency_s}s)`);
      } else {
        setTestResult(`❌ ${data.error || "Test failed"}`);
      }
    } catch {
      setTestResult("❌ Connection failed");
    } finally {
      setTesting(false);
    }
  };

  const current = providers.find((p) => p.id === selectedProvider);

  return (
    <div style={s.page}>
      {/* Header */}
      <div style={s.header}>
        <div>
          <h1 style={s.title}>🧠 Connect Brain</h1>
          <p style={s.subtitle}>Choose an AI provider, enter your API key, and start building.</p>
        </div>
        {activeProvider && (
          <div style={s.activeBadge}>
            <span style={{ color: "#10b981" }}>●</span> Active: {activeProvider}
          </div>
        )}
      </div>

      {error && <div style={s.error}>{error}</div>}

      {/* Step 1: Provider Grid */}
      <div style={s.section}>
        <div style={s.stepLabel}>1. Choose Provider</div>
        <div style={s.grid}>
          {providers.map((p) => (
            <button
              key={p.id}
              style={{
                ...s.providerCard,
                ...(selectedProvider === p.id ? s.providerCardActive : {}),
                borderColor: selectedProvider === p.id ? p.color + "44" : undefined,
              }}
              onClick={() => {
                setSelectedProvider(p.id);
                setSelectedModel(p.model || p.models[0] || "");
                setApiKey("");
                setTestResult(null);
                setError(null);
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <div style={{ ...s.providerIcon, background: p.color + "15", color: p.color }}>{p.icon}</div>
                <div style={{ textAlign: "left" }}>
                  <div style={s.providerName}>
                    {p.name}
                    {activeProvider === p.id && <span style={s.activeTag}>Active</span>}
                  </div>
                  <div style={s.providerDesc}>{p.desc}</div>
                </div>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Step 2 & 3: Config Panel */}
      {current && (
        <div style={s.configPanel}>
          <div style={s.stepLabel}>2. Configure {current.name}</div>

          {/* Model Selector */}
          {current.id !== "stub" && current.models.length > 0 && (
            <div style={s.field}>
              <label style={s.label}>Model</label>
              <select
                style={s.select}
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
              >
                {current.models.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </div>
          )}

          {/* API Key Input */}
          {current.env_var && current.id !== "ollama" && current.id !== "stub" && (
            <div style={s.field}>
              <label style={s.label}>
                API Key
                <span style={s.envVar}>{current.env_var}</span>
              </label>
              <div style={s.keyWrap}>
                <input
                  type={showKey ? "text" : "password"}
                  style={s.keyInput}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder={`Paste your ${current.env_var}`}
                />
                <button style={s.eyeBtn} onClick={() => setShowKey(!showKey)} type="button">
                  {showKey ? "🙈" : "👁"}
                </button>
              </div>
              <p style={s.keyHint}>
                Set this in your deployment environment, or paste it here for testing.
                <br />
                <a
                  href={
                    current.id === "openai" ? "https://platform.openai.com/api-keys" :
                    current.id === "anthropic" ? "https://console.anthropic.com/" :
                    current.id === "openrouter" ? "https://openrouter.ai/keys" :
                    current.id === "google" ? "https://aistudio.google.com/apikey" :
                    current.id === "mistral" ? "https://console.mistral.ai/api-keys/" : "#"
                  }
                  target="_blank"
                  rel="noopener noreferrer"
                  style={s.link}
                >
                  Get {current.name} API key ↗
                </a>
              </p>
            </div>
          )}

          {current.id === "ollama" && (
            <div style={s.infoBox}>
              ✓ No API key needed. Make sure Ollama is running locally on <code>http://localhost:11434</code>
            </div>
          )}

          {current.id === "stub" && (
            <div style={s.infoBox}>
              ✓ No configuration needed. Returns deterministic test responses.
            </div>
          )}

          {/* Actions */}
          <div style={s.actions}>
            <button
              style={{
                ...s.saveBtn,
                ...(saved ? { background: "rgba(16,185,129,0.15)", color: "#10b981", borderColor: "rgba(16,185,129,0.3)" } : {}),
              }}
              onClick={activateProvider}
              disabled={saving}
            >
              {saving ? "Saving..." : saved ? "✓ Saved" : "Save & Activate"}
            </button>
            <button
              style={s.testBtn}
              onClick={testProvider}
              disabled={testing}
            >
              {testing ? "Testing..." : "Test Connection"}
            </button>
          </div>

          {testResult && (
            <div style={{
              ...s.testResult,
              background: testResult.startsWith("✅") ? "rgba(16,185,129,0.08)" : "rgba(239,68,68,0.08)",
              borderColor: testResult.startsWith("✅") ? "rgba(16,185,129,0.2)" : "rgba(239,68,68,0.2)",
              color: testResult.startsWith("✅") ? "#10b981" : "#f87171",
            }}>
              {testResult}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

const s: Record<string, React.CSSProperties> = {
  page: {
    padding: "32px 24px",
    maxWidth: 900,
    margin: "0 auto",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 32,
  },
  title: {
    fontSize: 28,
    fontWeight: 700,
    color: "#f1f1f4",
    margin: 0,
  },
  subtitle: {
    fontSize: 14,
    color: "#888",
    marginTop: 4,
  },
  activeBadge: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    padding: "8px 14px",
    background: "rgba(16,185,129,0.08)",
    border: "1px solid rgba(16,185,129,0.2)",
    borderRadius: 10,
    fontSize: 13,
    color: "#aaa",
    fontWeight: 500,
  },
  error: {
    background: "rgba(239,68,68,0.08)",
    border: "1px solid rgba(239,68,68,0.2)",
    borderRadius: 10,
    padding: "12px 16px",
    marginBottom: 20,
    color: "#f87171",
    fontSize: 13,
  },
  section: {
    marginBottom: 28,
  },
  stepLabel: {
    fontSize: 13,
    fontWeight: 700,
    color: "#a5b4fc",
    textTransform: "uppercase",
    letterSpacing: "0.05em",
    marginBottom: 14,
  },
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
    gap: 10,
  },
  providerCard: {
    display: "block",
    width: "100%",
    textAlign: "left",
    padding: "14px 16px",
    background: "rgba(255,255,255,0.03)",
    border: "1px solid rgba(255,255,255,0.06)",
    borderRadius: 12,
    cursor: "pointer",
    transition: "all 0.15s",
    color: "inherit",
  },
  providerCardActive: {
    background: "rgba(99,102,241,0.08)",
    borderColor: "rgba(99,102,241,0.3)",
  },
  providerIcon: {
    width: 36,
    height: 36,
    borderRadius: 10,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 18,
    flexShrink: 0,
  },
  providerName: {
    fontSize: 14,
    fontWeight: 600,
    color: "#f1f1f4",
    display: "flex",
    alignItems: "center",
    gap: 8,
  },
  activeTag: {
    fontSize: 10,
    padding: "2px 8px",
    background: "rgba(16,185,129,0.15)",
    color: "#10b981",
    borderRadius: 6,
    fontWeight: 600,
  },
  providerDesc: {
    fontSize: 12,
    color: "#888",
    marginTop: 2,
  },
  configPanel: {
    background: "rgba(255,255,255,0.02)",
    border: "1px solid rgba(255,255,255,0.06)",
    borderRadius: 16,
    padding: 24,
  },
  field: {
    marginBottom: 20,
  },
  label: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    fontSize: 12,
    fontWeight: 600,
    color: "#aaa",
    textTransform: "uppercase",
    letterSpacing: "0.03em",
    marginBottom: 8,
  },
  envVar: {
    fontSize: 10,
    padding: "2px 6px",
    background: "rgba(255,255,255,0.05)",
    borderRadius: 4,
    color: "#666",
    fontFamily: "monospace",
    textTransform: "none",
    letterSpacing: 0,
    fontWeight: 400,
  },
  select: {
    width: "100%",
    padding: "11px 14px",
    background: "rgba(255,255,255,0.04)",
    border: "1px solid rgba(255,255,255,0.08)",
    borderRadius: 10,
    color: "#f1f1f4",
    fontSize: 14,
    outline: "none",
    cursor: "pointer",
    appearance: "none",
    backgroundImage: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%23666' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E\")",
    backgroundRepeat: "no-repeat",
    backgroundPosition: "right 12px center",
    paddingRight: 36,
    boxSizing: "border-box",
  },
  keyWrap: {
    position: "relative",
  },
  keyInput: {
    width: "100%",
    padding: "11px 48px 11px 14px",
    background: "rgba(255,255,255,0.04)",
    border: "1px solid rgba(255,255,255,0.08)",
    borderRadius: 10,
    color: "#f1f1f4",
    fontSize: 14,
    fontFamily: "monospace",
    outline: "none",
    boxSizing: "border-box",
  },
  eyeBtn: {
    position: "absolute",
    right: 10,
    top: "50%",
    transform: "translateY(-50%)",
    background: "none",
    border: "none",
    cursor: "pointer",
    fontSize: 16,
    padding: 4,
  },
  keyHint: {
    fontSize: 11,
    color: "#666",
    marginTop: 8,
    lineHeight: 1.5,
  },
  link: {
    color: "#a5b4fc",
    textDecoration: "none",
  },
  infoBox: {
    padding: "14px 16px",
    background: "rgba(99,102,241,0.06)",
    border: "1px solid rgba(99,102,241,0.15)",
    borderRadius: 10,
    fontSize: 13,
    color: "#aaa",
    marginBottom: 20,
  },
  actions: {
    display: "flex",
    gap: 10,
  },
  saveBtn: {
    padding: "11px 24px",
    background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
    border: "1px solid transparent",
    borderRadius: 10,
    color: "#fff",
    fontSize: 13,
    fontWeight: 700,
    cursor: "pointer",
    transition: "all 0.2s",
  },
  testBtn: {
    padding: "11px 20px",
    background: "rgba(255,255,255,0.04)",
    border: "1px solid rgba(255,255,255,0.1)",
    borderRadius: 10,
    color: "#aaa",
    fontSize: 13,
    fontWeight: 500,
    cursor: "pointer",
  },
  testResult: {
    marginTop: 14,
    padding: "10px 14px",
    borderRadius: 10,
    fontSize: 13,
    border: "1px solid",
  },
};
