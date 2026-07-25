"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";

type KB = { id: string; name: string; document_count: number; chunk_count: number };
type Prompt = { id: string; name: string; version: number };

type Message = { role: "user" | "assistant"; content: string; context_chunks?: any[] };

export default function RAGChatPage() {
  const [kbs, setKbs] = useState<KB[]>([]);
  const [prompts, setPrompts] = useState<Prompt[]>([]);
  const [selectedKb, setSelectedKb] = useState("");
  const [selectedPrompt, setSelectedPrompt] = useState("");
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [showContext, setShowContext] = useState(false);
  const chatEnd = useRef<HTMLDivElement>(null);

  useEffect(() => {
    Promise.all([
      fetch("/api/os/ai/knowledge-bases", { cache: "no-store" }).then((r) => r.json()),
      fetch("/api/os/ai/prompts", { cache: "no-store" }).then((r) => r.json()),
    ]).then(([kbData, promptData]) => {
      if (kbData.ok) setKbs(kbData.knowledge_bases || []);
      if (promptData.ok) setPrompts(promptData.prompts || []);
    });
  }, []);

  useEffect(() => {
    chatEnd.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim() || !selectedKb) return;

    const userMsg: Message = { role: "user", content: query.trim() };
    setMessages((prev) => [...prev, userMsg]);
    setQuery("");
    setLoading(true);

    try {
      const res = await fetch("/api/os/ai/rag-chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          kb_id: selectedKb || null,
          prompt_id: selectedPrompt || null,
          variables: {},
          query: query.trim(),
          top_k: 5,
        }),
      });
      const data = await res.json();
      if (data.ok) {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: data.answer || "(empty response)",
            context_chunks: data.context_chunks || [],
          },
        ]);
      } else {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: `Error: ${data.error || "request failed"}` },
        ]);
      }
    } catch (e: any) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Network error: ${e?.message || "unknown"}` },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="os-page">
      <header className="os-header">
        <div>
          <Link href="/os" className="os-back">← OS Launcher</Link>
          <h1>🧠 RAG Chat</h1>
          <p className="dashboard-subtitle">Chat with your knowledge bases using retrieval-augmented generation</p>
        </div>
      </header>

      {/* ── Controls ── */}
      <section className="rag-chat-controls">
        <div className="rag-chat-select-row">
          <div className="rag-chat-select-group">
            <label className="rag-chat-label">Knowledge Base</label>
            <select className="os-input" value={selectedKb} onChange={(e) => setSelectedKb(e.target.value)}>
              <option value="">Select KB…</option>
              {kbs.map((k) => (
                <option key={k.id} value={k.id}>{k.name} ({k.document_count} docs)</option>
              ))}
            </select>
          </div>
          <div className="rag-chat-select-group">
            <label className="rag-chat-label">Prompt Template</label>
            <select className="os-input" value={selectedPrompt} onChange={(e) => setSelectedPrompt(e.target.value)}>
              <option value="">Default (context + query)</option>
              {prompts.map((p) => (
                <option key={p.id} value={p.id}>{p.name} v{p.version}</option>
              ))}
            </select>
          </div>
          <button className="btn btn-sm" onClick={() => setMessages([])} disabled={messages.length === 0}>
            Clear Chat
          </button>
        </div>
      </section>

      {/* ── Chat Messages ── */}
      <section className="rag-chat-messages">
        {messages.length === 0 && !loading && (
          <div className="rag-chat-empty">
            <div className="rag-chat-empty-icon">🧠</div>
            <h3>Ask your knowledge base anything</h3>
            <p>Select a Knowledge Base above, type your question, and get AI-powered answers with context from your documents.</p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`rag-chat-msg ${msg.role}`}>
            <div className="rag-chat-msg-role">{msg.role === "user" ? "You" : "AEON RAG"}</div>
            <div className="rag-chat-msg-content">{msg.content}</div>
            {msg.role === "assistant" && msg.context_chunks && msg.context_chunks.length > 0 && (
              <details className="rag-chat-context" open={showContext}>
                <summary onClick={(e) => { e.preventDefault(); setShowContext(!showContext); }}>
                  {showContext ? "Hide" : "Show"} context ({msg.context_chunks.length} chunks)
                </summary>
                <div className="rag-chat-context-list">
                  {msg.context_chunks.map((c: any, j: number) => (
                    <div key={j} className="rag-chat-context-item">
                      <div className="rag-chat-context-doc">📄 {c.doc_id || `chunk-${j}`}</div>
                      <div className="rag-chat-context-text">{c.text?.slice(0, 300)}</div>
                      <div className="rag-chat-context-score">
                        Score: {(c.rrf_score ?? c.score)?.toFixed(4)}
                        {c.vector_rank && ` · Vector rank: ${c.vector_rank}`}
                        {c.keyword_rank && ` · Keyword rank: ${c.keyword_rank}`}
                      </div>
                    </div>
                  ))}
                </div>
              </details>
            )}
          </div>
        ))}

        {loading && (
          <div className="rag-chat-msg assistant">
            <div className="rag-chat-msg-role">AEON RAG</div>
            <div className="rag-chat-typing">
              <span></span><span></span><span></span>
            </div>
          </div>
        )}
        <div ref={chatEnd} />
      </section>

      {/* ── Input ── */}
      <form className="rag-chat-input" onSubmit={sendMessage}>
        <input
          className="os-input"
          placeholder={selectedKb ? "Ask about your documents..." : "Select a knowledge base first"}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          disabled={!selectedKb || loading}
          autoFocus
        />
        <button className="btn btn-primary" type="submit" disabled={!selectedKb || !query.trim() || loading}>
          {loading ? "Thinking..." : "Send"}
        </button>
      </form>
    </div>
  );
}
