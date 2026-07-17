"use client";

import { useEffect, useState } from "react";
import { createClient } from "@supabase/supabase-js";
import Sidebar from "../components/Sidebar";
import Topbar from "../components/Topbar";
import ChatPanel from "../components/ChatPanel";
import SettingsDrawer from "../components/SettingsDrawer";
import MemoryBrowser from "../components/MemoryBrowser";
import DeployGuidePanel from "../components/DeployGuidePanel";

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
  const [deployOpen, setDeployOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false); // mobile
  const [memories, setMemories] = useState<Episode[]>([]);
  const [loadingMemories, setLoadingMemories] = useState(true);

  // Auto-open the deploy guide for first-time visitors if any required env is missing.
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (window.localStorage.getItem("aeon-deploy-seen")) return;
    fetch("/api/onboarding/status", { cache: "no-store" })
      .then((r) => r.json())
      .then((s) => {
        const anyUnset = (s?.steps || []).some((st: any) =>
          ["warn", "missing"].includes(st.state),
        );
        if (anyUnset) setDeployOpen(true);
        window.localStorage.setItem("aeon-deploy-seen", "1");
      })
      .catch(() => { window.localStorage.setItem("aeon-deploy-seen", "1"); });
  }, []);

  // Load last 5 episodes from Supabase on mount.
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

  const newChat = () => setMemories([]);

  return (
    <div className="app">
      <Sidebar
        onNewChat={newChat}
        onOpenMemory={() => setMemoryOpen(true)}
        onOpenSettings={() => setSettingsOpen(true)}
        onOpenDeploy={() => setDeployOpen(true)}
        mobileOpen={sidebarOpen}
        onCloseMobile={() => setSidebarOpen(false)}
      />

      <div className="main">
        <Topbar
          backend={backend}
          onBackend={setBackend}
          onToggleSidebar={() => setSidebarOpen((v) => !v)}
        />

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
      <MemoryBrowser   open={memoryOpen}  onClose={() => setMemoryOpen(false)} />
      <DeployGuidePanel open={deployOpen} onClose={() => setDeployOpen(false)} />
    </div>
  );
}
