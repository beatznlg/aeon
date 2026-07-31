"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { getFlaskToken, getFlaskUser, getAuthHeaders } from "@/lib/flask-auth";

// ── Types ────────────────────────────────────────────────────────────────
interface Message {
  role: "user" | "aeon";
  text: string;
  backend?: string;
}

interface Workspace {
  id: string;
  slug: string;
  name: string;
  plan: string;
  role: string;
}

interface HistoryItem {
  id?: number;
  ts?: number;
  kind?: string;
  text?: string;
  ref?: string | null;
  role?: string;
  content?: string;
}

// ── Markdown formatting ───────────────────────────────────────────────────
function formatMessage(text: string) {
  const parts = text.split(/(```[\s\S]*?```|\*\*[\s\S]*?\*\*)/g);
  return parts.map((part, index) => {
    if (part.startsWith("```") && part.endsWith("```")) {
      return (
        <pre key={index} className="chat-code">
          {part.slice(3, -3).replace(/^[\w]+\n/, "")}
        </pre>
      );
    }
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }
    return <span key={index}>{part}</span>;
  });
}

// ── Provider metadata ────────────────────────────────────────────────────
const PROVIDERS = [
  { id: "stub", name: "Stub (No AI)", icon: "◇", color: "#71717a" },
  { id: "openai", name: "OpenAI", icon: "⚡", color: "#10a37f" },
  { id: "anthropic", name: "Claude", icon: "✦", color: "#d97706" },
  { id: "ollama", name: "Ollama", icon: "🦙", color: "#8b5cf6" },
  { id: "hf", name: "Hugging Face", icon: "🤗", color: "#fbbf24" },
  { id: "qwen", name: "Qwen Local", icon: "🧠", color: "#6366f1" },
];

// ── Chat page ────────────────────────────────────────────────────────────
export default function ChatPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [provider, setProvider] = useState("stub");
  const [showProviderMenu, setShowProviderMenu] = useState(false);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [wsReady, setWsReady] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // ── Redirect if not authenticated ──
  useEffect(() => {
    if (status === "unauthenticated") {
      router.push("/login?callbackUrl=/chat");
    }
  }, [status, router]);

  // ── Load workspace from Flask JWT ──
  useEffect(() => {
    if (status !== "authenticated") return;

    const flaskUser = getFlaskUser();
    const flaskToken = getFlaskToken();

    if (flaskUser?.workspace_id) {
      // Already have workspace info from login
      setWorkspace({
        id: flaskUser.workspace_id,
        slug: flaskUser.workspace_id?.slice(0, 8) || "default",
        name: `${flaskUser.email?.split("@")[0] || "User"}'s Workspace`,
        plan: "free",
        role: flaskUser.role || "VIEWER",
      });
      setWsReady(true);
    } else if (flaskToken) {
      // Try fetching workspace list from Flask
      fetch("/api/workspaces", {
        headers: { Authorization: `Bearer ${flaskToken}` },
      })
        .then((r) => r.json())
        .then((data) => {
          if (data.ok && data.workspaces?.length > 0) {
            const ws = data.workspaces[0];
            setWorkspace(ws);
            setWsReady(true);
          }
        })
        .catch(() => {});
    } else {
      // No Flask JWT yet — try a direct /api/chat call which will 401,
      // but we set wsReady anyway so the user can still interact.
      setWsReady(true);
    }
  }, [status]);

  // ── Load conversation history ──
  useEffect(() => {
    if (!wsReady || historyLoaded || !workspace?.id) return;

    const flaskToken = getFlaskToken();
    if (!flaskToken) {
      setHistoryLoaded(true);
      return;
    }

    fetch(`/api/workspaces/${workspace.id}/history?limit=30`, {
      headers: { Authorization: `Bearer ${flaskToken}` },
    })
      .then((r) => r.json())
      .then((data) => {
        setHistoryLoaded(true);
        if (!data.ok || !data.history) return;

        const history = data.history as HistoryItem[];
        if (history.length === 0) return;

        // Convert history to messages
        const loaded: Message[] = [];
        for (const item of history) {
          const text = item.text || item.content || "";
          const kind = item.kind || item.role || "";
          if (kind === "user") {
            loaded.push({ role: "user", text });
          } else if (kind === "bot" || kind === "assistant") {
            loaded.push({ role: "aeon", text });
          }
        }
        if (loaded.length > 0) {
          setMessages(loaded);
        }
      })
      .catch(() => setHistoryLoaded(true));
  }, [wsReady, historyLoaded, workspace?.id]);

  // ── Auto-scroll ──
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading]);

  // ── Get auth headers for API calls ──
  const getAuthHeaders = useCallback((): Record<string, string> => {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    const token = getFlaskToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    return headers;
  }, []);

  // ── Send message ──
  const sendMessage = async () => {
    if (!input.trim() || loading) return;
    const userMsg = input.trim();
    setMessages((prev) => [...prev, { role: "user", text: userMsg }]);
    setInput("");
    setLoading(true);

    try {
      const payload: any = { query: userMsg, provider };
      let chatUrl = "/api/chat";

      if (workspace?.id) {
        chatUrl = `/api/workspaces/${workspace.id}/chat`;
      }

      const res = await fetch(chatUrl, {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify(payload),
      });
      const data = await res.json();

      let reply = "";
      let backend = "";
      if (data.data && typeof data.data === "object") {
        reply = data.data.answer || data.data.text || JSON.stringify(data.data);
        backend = data.data.backend || data.backend || "";
      } else if (typeof data.data === "string") {
        reply = data.data;
        backend = data.backend || "";
      } else {
        reply = data.error ? `Error: ${data.error}` : JSON.stringify(data, null, 2);
      }

      setMessages((prev) => [...prev, { role: "aeon", text: reply, backend }]);
    } catch (e: any) {
      setMessages((prev) => [...prev, { role: "aeon", text: `Error: ${e.message}` }]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  if (status === "loading") {
    return (
      <div className="chat-container">
        <div className="chat-loading">Loading session...</div>
      </div>
    );
  }

  if (status === "unauthenticated") {
    return null; // Redirecting
  }

  const activeProvider = PROVIDERS.find((p) => p.id === provider) || PROVIDERS[0];
  const userEmail = session?.user?.email || "";

  return (
    <div className="chat-container">
      {/* ── Header ── */}
      <header className="chat-header">
        <div className="chat-header-left">
          <div className="chat-brand">⟁ AEON</div>
          {workspace && (
            <span className="chat-workspace-badge" title={workspace.id}>
              {workspace.name}
            </span>
          )}
        </div>
        <div className="chat-header-right">
          {/* Provider selector */}
          <div className="provider-selector">
            <button
              className="provider-current"
              onClick={() => setShowProviderMenu(!showProviderMenu)}
              title={`Active provider: ${activeProvider.name}`}
            >
              <span style={{ color: activeProvider.color }}>{activeProvider.icon}</span>
              <span>{activeProvider.name}</span>
              <span className="provider-arrow">▼</span>
            </button>
            {showProviderMenu && (
              <>
                <div className="provider-overlay" onClick={() => setShowProviderMenu(false)} />
                <div className="provider-menu">
                  {PROVIDERS.map((p) => (
                    <button
                      key={p.id}
                      className={`provider-option ${p.id === provider ? "active" : ""}`}
                      onClick={() => {
                        setProvider(p.id);
                        setShowProviderMenu(false);
                        // Also sync via backend API
                        const token = getFlaskToken();
                        if (token) {
                          fetch("/api/llm/switch", {
                            method: "POST",
                            headers: {
                              "Content-Type": "application/json",
                              Authorization: `Bearer ${token}`,
                            },
                            body: JSON.stringify({ provider: p.id }),
                          }).catch(() => {});
                        }
                      }}
                    >
                      <span style={{ color: p.color }}>{p.icon}</span>
                      <span>{p.name}</span>
                      {p.id === provider && <span className="provider-check">✓</span>}
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>

          {/* User info */}
          <div className="chat-user">
            <span className="chat-user-email" title={userEmail}>
              {userEmail}
            </span>
          </div>
        </div>
      </header>

      {/* ── Messages ── */}
      <div ref={scrollRef} className="chat-messages-area">
        {messages.length === 0 && !loading && (
          <div className="chat-empty">
            <div className="chat-empty-icon">⟁</div>
            <h2>What can AEON help you with?</h2>
            <p className="chat-empty-hint">
              Ask about mathematics, code, business analysis, or any topic. AEON uses{" "}
              <strong>{activeProvider.name}</strong> to generate responses.
            </p>
            <div className="chat-suggestions">
              <button
                onClick={() => {
                  setInput("What is the integral of x² dx?");
                  inputRef.current?.focus();
                }}
              >
                ∫ x² dx
              </button>
              <button
                onClick={() => {
                  setInput("Explain causal credit assignment in reinforcement learning");
                  inputRef.current?.focus();
                }}
              >
                Causal credit
              </button>
              <button
                onClick={() => {
                  setInput(
                    "Write a Python function that retries an HTTP request 3 times with exponential backoff"
                  );
                  inputRef.current?.focus();
                }}
              >
                Retry pattern
              </button>
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div
            key={i}
            className={`chat-msg ${m.role === "user" ? "chat-msg-user" : "chat-msg-aeon"}`}
          >
            <div className={`chat-msg-label ${m.role === "user" ? "" : "bot"}`}>
              {m.role === "user" ? "You" : "AEON"}
            </div>
            <div
              className={`chat-msg-bubble ${m.role === "user" ? "chat-bubble-user" : "chat-bubble-aeon"}`}
            >
              <div className="chat-msg-text">{formatMessage(m.text)}</div>
              {m.backend && m.role === "aeon" && (
                <div className="chat-msg-backend">via {m.backend}</div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="chat-msg chat-msg-aeon">
            <div className="chat-msg-label bot">AEON</div>
            <div className="chat-msg-bubble chat-bubble-aeon">
              <div className="chat-typing">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── Input ── */}
      <div className="chat-input-area">
        <div className="chat-input-wrapper">
          <input
            ref={inputRef}
            className="chat-input-field"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
              }
            }}
            placeholder="Ask AEON anything..."
            autoFocus
          />
          <button
            onClick={sendMessage}
            disabled={loading || !input.trim()}
            className="chat-send-btn"
          >
            Send
          </button>
        </div>
        <div className="chat-input-footer">
          Provider: <span style={{ color: activeProvider.color }}>{activeProvider.name}</span>
          {workspace && <span> · Workspace: {workspace.name}</span>}
        </div>
      </div>
    </div>
  );
}
