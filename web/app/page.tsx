"use client";

import { useEffect, useState } from "react";
import { createClient } from "@supabase/supabase-js";
import Sidebar from "../components/Sidebar";
import Topbar from "../components/Topbar";
import ChatPanel from "../components/ChatPanel";
import SettingsDrawer from "../components/SettingsDrawer";
import MemoryBrowser from "../components/MemoryBrowser";

type Episode = {
  id: number; ts: number;
  kind: "user" | "bot" | "obs"; text: string; ref: string | null;
};

const sbUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
const sbKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "";
const supabase = sbUrl && sbKey ? createClient(sbUrl, sbKey) : null;

export default function Page() {
  const [backend, setBackend] = useState<string>("auto");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [memoryOpen, setMemoryOpen] = useState(false);
  const [memories, setMemories] = useState<Episode[]>([]);
  const [loadingMemories, setLoadingMemories] = useState(true);

  // Load last 5 episodes from Supabase on mount (cheap pre-history).
  useEffect(() => {
    if (!supabase) { setLoadingMemories(false); return; }
    (async () => {
      const { data, error } = await supabase
        .from("episodes")
        .select("id,ts,kind,text,ref")
        .order("id", { ascending: false })
        .limit(5);
      if (!error && Array.isArray(data)) setMemories((data as Episode[]).slice().reverse());
      setLoadingMemories(false);
    })();
  }, []);

  const writeMemory = async (kind: "user" | "bot", text: string) => {
    if (!supabase) return;
    const trimmed = String(text).trim().slice(0, 2000);
    if (!trimmed) return;
    const { data, error } = await supabase
      .from("episodes")
      .insert([{ ts: Date.now() / 1000, kind, text: trimmed, ref: "web_v3" }])
      .select();
    if (!error && Array.isArray(data) && data[0]) {
      setMemories((prev) => [...prev, data[0] as Episode].slice(-50));
    }
  };

  const newChat = () => {
    // Soft reset: just clear history; full reset is done by ChatPanel's reset button.
    setMemories([]);
  };

  return (
    <div className="app">
      <Sidebar
        onNewChat={newChat}
        onOpenMemory={() => setMemoryOpen(true)}
        onOpenSettings={() => setSettingsOpen(true)}
      />

      <div className="main">
        <Topbar backend={backend} onBackend={setBackend} />

        {!loadingMemories && memories.length > 0 && (
          <details className="memories-panel">
            <summary>Recent memories ({memories.length})</summary>
            {memories.slice(-5).map((m) => (
              <div key={m.id} className="memory-item">
                <div className="meta">
                  #{m.id} · {m.kind}
                  {m.ref ? " · " + m.ref : ""}
                </div>
                <div>{m.text}</div>
              </div>
            ))}
          </details>
        )}

        <ChatPanel backend={backend} memories={memories} onMemoryWrite={writeMemory} />
      </div>

      <SettingsDrawer open={settingsOpen} onClose={() => setSettingsOpen(false)} />
      <MemoryBrowser open={memoryOpen} onClose={() => setMemoryOpen(false)} />
    </div>
  );
}
