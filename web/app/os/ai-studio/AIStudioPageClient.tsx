"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

type Prompt = {
  id: string;
  name: string;
  version: number;
  updated_at: number;
};

const providers = [
  { label: "OpenRouter (default)", value: "openrouter" },
  { label: "OpenAI", value: "openai" },
  { label: "Anthropic", value: "anthropic" },
  { label: "HuggingFace", value: "hf" },
  { label: "Ollama", value: "ollama" },
  { label: "Stub", value: "stub" },
];

export default function AIStudioPageClient() {
  const [prompts, setPrompts] = useState<Prompt[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [template, setTemplate] = useState("");
  const [system, setSystem] = useState("");
  const [provider, setProvider] = useState("openrouter");
  const [model, setModel] = useState("");
  const [tags, setTags] = useState("");

  useEffect(() => {
    fetchPrompts();
  }, []);

  const fetchPrompts = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/os/ai/prompts", { cache: "no-store" });
      const data = await res.json();
      if (data.ok) setPrompts(data.prompts || []);
      else setError(data.error || "failed to load prompts");
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setLoading(false);
    }
  };

  const savePrompt = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch("/api/os/ai/prompts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          template,
          system,
          provider,
          model,
          tags: tags.split(",").map((t) => t.trim()).filter(Boolean),
        }),
      });
      const data = await res.json();
      if (data.ok) {
        setPrompts((prev) => {
          const filtered = prev.filter((p) => p.id !== data.prompt.id);
          return [data.prompt, ...filtered];
        });
        setName("");
        setTemplate("");
        setSystem("");
        setModel("");
        setTags("");
      } else {
        setError(data.error || "failed to save prompt");
      }
    } catch (e: any) {
      setError(e?.message || String(e));
    }
  };

  const deletePrompt = async (id: string) => {
    if (!confirm("Delete this prompt?")) return;
    try {
      const res = await fetch(`/api/os/ai/prompts/${id}`, { method: "DELETE" });
      const data = await res.json();
      if (data.ok) setPrompts((prev) => prev.filter((p) => p.id !== id));
    } catch (e: any) {
      setError(e?.message || String(e));
    }
  };

  return (
    <div className="os-page">
      <header className="os-header">
        <div>
          <h1 style={{ background: "var(--grad)", WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent" }}>
            AI Studio
          </h1>
          <p className="dashboard-subtitle">Prompt registry, model selection, and RAG orchestration</p>
        </div>
        <Link href="/os" className="btn btn-secondary">← OS Launcher</Link>
      </header>

      {error && <div className="module-alert danger">{error}</div>}

      <section className="os-card" style={{ marginBottom: 24 }}>
        <h3>Create Prompt</h3>
        <form onSubmit={savePrompt} className="form-grid">
          <label>
            Name
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. customer-support" required />
          </label>
          <label>
            Provider
            <select value={provider} onChange={(e) => setProvider(e.target.value)}>
              {providers.map((p) => (
                <option key={p.value} value={p.value}>{p.label}</option>
              ))}
            </select>
          </label>
          <label>
            Model (optional)
            <input value={model} onChange={(e) => setModel(e.target.value)} placeholder="e.g. gpt-4o-mini" />
          </label>
          <label>
            Tags (comma separated)
            <input value={tags} onChange={(e) => setTags(e.target.value)} placeholder="support, rag" />
          </label>
          <label className="span-2">
            System message
            <textarea value={system} onChange={(e) => setSystem(e.target.value)} rows={3} placeholder="You are a helpful AEON assistant..." />
          </label>
          <label className="span-2">
            Template
            <textarea
              value={template}
              onChange={(e) => setTemplate(e.target.value)}
              rows={5}
              placeholder="Use {{query}} and {{context}} variables. Answer: {{query}}"
              required
            />
          </label>
          <button type="submit" className="btn btn-primary">Save Prompt</button>
        </form>
      </section>

      <section>
        <h3>Prompt Registry ({prompts.length})</h3>
        {loading ? (
          <p style={{ color: "var(--fg-mute)" }}>Loading…</p>
        ) : prompts.length === 0 ? (
          <p style={{ color: "var(--fg-mute)" }}>No prompts yet. Create one above.</p>
        ) : (
          <div className="os-grid">
            {prompts.map((p) => (
              <div key={p.id} className="os-card">
                <div className="os-card-header">
                  <h4>{p.name}</h4>
                  <span className="os-status-pill active">v{p.version}</span>
                </div>
                <p className="os-desc">ID: {p.id}</p>
                <p className="os-desc">Updated: {new Date(p.updated_at * 1000).toLocaleString()}</p>
                <button className="btn btn-sm" onClick={() => deletePrompt(p.id)}>Delete</button>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
