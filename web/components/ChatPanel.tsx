"use client";

import { useChat } from "@ai-sdk/react";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { getStoredProvider, type StoredProvider } from "@/lib/provider";

type Episode = {
  id: number; ts: number;
  kind: "user" | "bot" | "obs"; text: string; ref: string | null;
};

/* --------- lightweight markdown (bold, italic, inline code, fenced code,
   headings, blockquotes, simple lists, and links). Zero new deps. --------- */
function renderInline(s: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(`[^`]+`)|(\*\*[^*]+\*\*)|(\*[^*]+\*)|(\[[^\]]+\]\([^)]+\))/g;
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(s))) {
    if (m.index > last) out.push(s.slice(last, m.index));
    if (m[1]) out.push(<code className="md-inline-code">{m[1].slice(1, -1)}</code>);
    else if (m[2]) out.push(<strong>{m[2].slice(2, -2)}</strong>);
    else if (m[3]) out.push(<em>{m[3].slice(1, -1)}</em>);
    else if (m[4]) {
      const lm = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(m[4]);
      if (lm) out.push(<a href={lm[2]} target="_blank" rel="noopener noreferrer">{lm[1]}</a>);
    }
    last = m.index + m[0].length;
  }
  if (last < s.length) out.push(s.slice(last));
  return out;
}

function Markdown({ text }: { text: string }) {
  const lines = text.split(/\n/);
  const blocks: ReactNode[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];

    // fenced code block
    if (line.startsWith("```")) {
      const lang = line.slice(3).trim();
      const buf: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) {
        buf.push(lines[i]); i++;
      }
      i++; // skip closing fence
      blocks.push(
        <pre className="md-code" key={blocks.length + ":" + lang}>
          <code>{buf.join("\n")}</code>
        </pre>,
      );
      continue;
    }

    // heading
    const hm = /^(#{1,3})\s+(.*)$/.exec(line);
    if (hm) {
      const lvl = hm[1].length;
      const Tag = ("h" + lvl) as "h1" | "h2" | "h3";
      blocks.push(<Tag key={blocks.length} className={"md-h md-h" + lvl}>{hm[2]}</Tag>);
      i++; continue;
    }

    // unordered list
    if (/^[-*]\s+/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^[-*]\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^[-*]\s+/, "")); i++;
      }
      blocks.push(
        <ul key={blocks.length} className="md-ul">
          {items.map((it, k) => <li key={k}>{renderInline(it)}</li>)}
        </ul>,
      );
      continue;
    }

    // blank line → skip
    if (!line.trim()) { i++; continue; }

    // paragraph (collect continguous non-special lines)
    const para: string[] = [line];
    i++;
    while (
      i < lines.length &&
      lines[i].trim() &&
      !lines[i].startsWith("```") &&
      !/^#{1,3}\s/.test(lines[i]) &&
      !/^[-*]\s/.test(lines[i])
    ) {
      para.push(lines[i]); i++;
    }
    blocks.push(
      <p key={blocks.length} className="md-p">
        {renderInline(para.join(" "))}
      </p>,
    );
  }
  return <div className="md">{blocks}</div>;
}

export default function ChatPanel({
  backend,
  memories,
  onMemoryWrite,
}: {
  backend: string;
  memories: Episode[];
  onMemoryWrite: (kind: "user" | "bot", text: string) => void;
}) {
  const [provider, setProvider] = useState<StoredProvider>(getStoredProvider());

  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === "aeon_provider" && e.newValue) {
        setProvider(e.newValue as StoredProvider);
      }
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const { messages, input, handleInputChange, handleSubmit, status, setMessages } =
    useChat({
      api: "/api/chat",
      body: { backend },
      headers: { "x-aeon-provider": provider },
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
            <div
              key={m.id}
              className={"msg " + (m.role === "user" ? "user" : "bot") + " msg-slide"}
            >
              <div className={"role " + (m.role === "user" ? "" : "bot")}>
                {m.role}
              </div>
              {m.role === "user" ? (
                <div style={{ whiteSpace: "pre-wrap" }}>{m.content}</div>
              ) : (
                <Markdown text={m.content} />
              )}
            </div>
          ))
        )}
        {status === "submitted" || status === "streaming" ? (
          <div className="msg bot msg-slide">
            <div className="role bot">assistant</div>
            <div className="typing-dots"><span></span><span></span><span></span></div>
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
