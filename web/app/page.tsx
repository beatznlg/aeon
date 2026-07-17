"use client";

import { useChat } from "@ai-sdk/react";
import { useEffect, useState } from "react";
import { createClient } from "@supabase/supabase-js";

// Browser-side Supabase client. `NEXT_PUBLIC_*` vars are inlined at build
// time by Next.js, so module-level reads are valid.
const sbUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
const sbKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "";
const supabase = sbUrl && sbKey ? createClient(sbUrl, sbKey) : null;

type Episode = {
  id: number;
  ts: number;
  kind: "user" | "bot" | "obs";
  text: string;
  ref: string | null;
};

export default function Page() {
  const [memories, setMemories] = useState<Episode[]>([]);
  const [loadingMemories, setLoadingMemories] = useState(true);

  // Load last 5 episodes from Supabase on mount.
  useEffect(() => {
    if (!supabase) {
      setLoadingMemories(false);
      return;
    }
    (async () => {
      const { data, error } = await supabase
        .from("episodes")
        .select("id,ts,kind,text,ref")
        .order("id", { ascending: false })
        .limit(5);
      if (!error && Array.isArray(data)) {
        setMemories((data as Episode[]).slice().reverse());
      }
      setLoadingMemories(false);
    })();
  }, []);

  const { messages, input, handleInputChange, handleSubmit, status } = useChat(
    {
      api: "/api/chat",
      onFinish: (msg) => {
        if (supabase) {
          supabase
            .from("episodes")
            .insert([
              {
                ts: Date.now() / 1000,
                kind: "bot",
                text: String(msg.content).slice(0, 2000),
                ref: "web_ui",
              },
            ])
            .then(() => {}, () => {});
        }
      },
    },
  );

  // Persist the user's prompt before delegating to useChat.
  const onSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    if (supabase && input.trim()) {
      supabase
        .from("episodes")
        .insert([
          {
            ts: Date.now() / 1000,
            kind: "user",
            text: input.trim().slice(0, 2000),
            ref: "web_ui",
          },
        ])
        .then(() => {}, () => {});
    }
    handleSubmit(e);
  };

  return (
    <main>
      <h1>AEON \u03b1</h1>
      <p className="subtle">
        Streaming chat. Vercel UI \u2192 AEON kernel on Hugging Face Spaces (or
        Hugging Face Inference API fallback) \u2192 Supabase for memory.
      </p>

      {loadingMemories ? (
        <p className="subtle">Syncing memories from Supabase\u2026</p>
      ) : memories.length > 0 ? (
        <details>
          <summary className="subtle">
            Memories ({memories.length} recent episodes from Supabase)
          </summary>
          {memories.map((m) => (
            <div key={m.id} className={"msg " + (m.kind === "user" ? "user" : "bot")}>
              <div className="role">
                {m.kind} \u00b7 #{m.id}
                {m.ref ? " \u00b7 " + m.ref : ""}
              </div>
              <div>{m.text}</div>
            </div>
          ))}
        </details>
      ) : null}

      {messages.map((m) => (
        <div key={m.id} className={"msg " + (m.role === "user" ? "user" : "bot")}>
          <div className="role">{m.role}</div>
          <div>{m.content}</div>
        </div>
      ))}
      {status === "submitted" || status === "streaming" ? (
        <div className="msg bot">
          <div className="role">assistant</div>
          <div>\u2026</div>
        </div>
      ) : null}
      <form onSubmit={onSubmit}>
        <input
          name="prompt"
          value={input}
          onChange={handleInputChange}
          placeholder="Ask AEON anything..."
          autoComplete="off"
        />
        <button type="submit" disabled={status !== "ready"}>
          Send
        </button>
      </form>
    </main>
  );
}
