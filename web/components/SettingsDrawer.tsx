"use client";

import { useEffect, useState } from "react";

const SUPA_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
const SUPA_ANON_SET = !!process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
const HFSPACE_SET = !!process.env.AEON_HF_SPACE_URL;

export default function SettingsDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [health, setHealth] = useState<{ ok: boolean; backend?: string; ts?: number } | null>(null);

  useEffect(() => {
    if (!open) return;
    fetch("/api/health")
      .then((r) => r.json())
      .then((d) => setHealth(d))
      .catch(() => setHealth({ ok: false }));
  }, [open]);

  return (
    <>
      <div className={"drawer-backdrop" + (open ? " open" : "")} onClick={onClose}></div>
      <aside className={"drawer" + (open ? " open" : "")} aria-hidden={!open}>
        <button className="close" onClick={onClose} title="Close">
          ×
        </button>
        <h2>Settings & keys</h2>

        <div className="setting">
          <div className="label">Backend liveness</div>
          <div className={"value " + (health?.ok ? "ok" : "no")}>
            {health === null
              ? "checking…"
              : health.ok
                ? "ok" + (health.backend ? " · " + health.backend : "")
                : "unreachable"}
          </div>
        </div>

        <div className="setting">
          <div className="label">Supabase (NEXT_PUBLIC_)</div>
          <div className={"value " + (SUPA_URL && SUPA_ANON_SET ? "ok" : "no")}>
            {SUPA_URL && SUPA_ANON_SET ? "wired" : "missing URL or anon key"}
          </div>
          {SUPA_URL ? (
            <div className="value" style={{ fontSize: "0.78rem", marginTop: 4 }}>
              {SUPA_URL.replace(/^https?:\/\//, "")}
            </div>
          ) : null}
        </div>

        <div className="setting">
          <div className="label">AEON kernel on HF Spaces</div>
          <div className={"value " + (HFSPACE_SET ? "ok" : "no")}>
            {HFSPACE_SET ? "proxied" : "falling back to HF Inference API"}
          </div>
        </div>

        <div className="setting">
          <div className="label">Hardening tip · Supabase RLS</div>
          <pre className="code">{`alter table episodes enable row level security;
create policy "anon read" on episodes
  for select using (auth.role() = 'anon');
create policy "service write" on episodes
  for insert with check (auth.role() = 'service_role');`}</pre>
        </div>

        <div className="setting">
          <div className="label">Roles of the keys you set</div>
          <ul style={{ paddingLeft: 18, color: "var(--fg-soft)", fontSize: "0.88rem" }}>
            <li>
              <code>NEXT_PUBLIC_SUPABASE_URL</code> · browser
            </li>
            <li>
              <code>NEXT_PUBLIC_SUPABASE_ANON_KEY</code> · browser
            </li>
            <li>
              <code>SUPABASE_SERVICE_ROLE_KEY</code> · server-only
            </li>
            <li>
              <code>HUGGINGFACE_TOKEN</code> · server
            </li>
            <li>
              <code>AEON_HF_SPACE_URL</code> · server
            </li>
            <li>
              <code>GH_TOKEN</code> (optional) · server
            </li>
          </ul>
        </div>

        <div className="setting">
          <div className="label">External</div>
          <ul style={{ paddingLeft: 18, color: "var(--fg-soft)", fontSize: "0.86rem" }}>
            <li>
              <a
                href="https://huggingface.co/settings/tokens"
                target="_blank"
                rel="noopener noreferrer"
              >
                Hugging Face tokens ↗
              </a>
            </li>
            <li>
              <a href="https://supabase.com/dashboard" target="_blank" rel="noopener noreferrer">
                Supabase dashboard ↗
              </a>
            </li>
            <li>
              <a href="https://huggingface.co/new-space" target="_blank" rel="noopener noreferrer">
                New HF Space ↗
              </a>
            </li>
            <li>
              <a href="https://vercel.com/dashboard" target="_blank" rel="noopener noreferrer">
                Vercel project ↗
              </a>
            </li>
          </ul>
        </div>
      </aside>
    </>
  );
}
