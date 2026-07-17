"use client";

import { useChat } from "@ai-sdk/react";

type Episode = {
  id: number; ts: number;
  kind: "user" | "bot" | "obs"; text: string; ref: string | null;
};

export default function ChatPanel({
  backend,
  memories,
  onMemoryWrite,
}: {
  backend: string;
  memories: Episode[];
  onMemoryWrite: (kind: "user" | "bot", text: string) => void;
}) {
  const { messages, input, handleInputChange, handleSubmit, status, setMessages } =
    useChat({
      api: "/api/chat",
      body: { backend },
      onFinish: (msg) => onMemoryWrite("bot", msg.content),
    });

  const resetChat = () => setMessages([]);

  const onSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    if (input.trim()) onMemoryWrite("user", input.trim());
    handleSubmit(e);
  };

  const isEmpty = messages.length === 0;

  return (
    <div className="chat-panel">
      <div className="chat-messages">
        {isEmpty ? (
          <div className="empty-state">
            <h1>What can I help you reason about?</h1>
            <p>AEON is a streaming AI kernel — text, code, tools and memory.</p>
            <p style={{ marginTop: 18, fontSize: "0.85rem" }}>
              Try: <em>&ldquo;Integrate x² dx&rdquo;</em> &middot;{" "}
              <em>&ldquo;What is causal credit assignment?&rdquo;</em> &middot;{" "}
              <em>&ldquo;Summarize the last 5 memories from Supabase&rdquo;</em>
            </p>
            {memories.length > 0 ? (
              <p style={{ marginTop: 14, color: "var(--fg-soft)" }}>
                Loaded {memories.length} recent episodes from Supabase.
              </p>
            ) : null}
          </div>
        ) : (
          messages.map((m) => (
            <div key={m.id} className={"msg " + (m.role === "user" ? "user" : "bot")}>
              <div className={"role " + (m.role === "user" ? "" : "bot")}>
                {m.role}
              </div>
              <div>{m.content}</div>
            </div>
          ))
        )}
        {status === "submitted" || status === "streaming" ? (
          <div className="msg bot">
            <div className="role bot">assistant</div>
            <div>…</div>
          </div>
        ) : null}
        {!isEmpty ? (
          <div style={{ textAlign: "center", marginTop: 18 }}>
            <button className="btn-secondary" onClick={resetChat}>
              ↻ Reset conversation
            </button>
          </div>
        ) : null}
      </div>

      <div className="chat-input">
        <form onSubmit={onSubmit}>
          <input
            name="prompt"
            value={input}
            onChange={handleInputChange}
            placeholder="Ask AEON anything..."
            autoComplete="off"
            autoFocus
          />
          <button type="submit" disabled={status !== "ready"}>
            Send ↵
          </button>
        </form>
      </div>
    </div>
  );
}
