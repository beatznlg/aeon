"use client";

import { useEffect, useState } from "react";

type Episode = {
  id: number;
  ts: number;
  kind: "user" | "bot" | "obs";
  text: string;
  ref: string | null;
};

export default function MemoryBrowser({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [page, setPage] = useState(0);
  const [rows, setRows] = useState<Episode[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    fetch("/api/memories/tail?limit=20&before_id=" + (page * 20 + 1))
      .then((r) => r.json())
      .then((d) => {
        if (d.ok && Array.isArray(d.rows)) setRows(d.rows as Episode[]);
        else setRows([]);
      })
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  }, [open, page]);

  return (
    <>
      <div className={"drawer-backdrop" + (open ? " open" : "")} onClick={onClose}></div>
      <aside className={"drawer" + (open ? " open" : "")} aria-hidden={!open}>
        <button className="close" onClick={onClose} title="Close">
          ×
        </button>
        <h2>Memory browser</h2>
        <p style={{ color: "var(--fg-mute)", fontSize: "0.85rem" }}>
          Latest 20 episodes from Supabase, page {page + 1}.
        </p>

        {loading ? (
          <p style={{ color: "var(--fg-mute)" }}>Loading…</p>
        ) : rows.length === 0 ? (
          <p style={{ color: "var(--fg-mute)" }}>
            No episodes yet. Send your first message in chat to populate this.
          </p>
        ) : (
          <div>
            {rows.map((e) => (
              <div key={e.id} className="memory-item">
                <div className="meta">
                  #{e.id} · {e.kind}
                  {e.ref ? " · " + e.ref : ""} · {new Date(e.ts * 1000).toLocaleString()}
                </div>
                <div>{e.text}</div>
              </div>
            ))}
          </div>
        )}

        <div style={{ display: "flex", gap: 6, marginTop: 18 }}>
          <button
            className="btn-secondary"
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
          >
            ← Prev
          </button>
          <button
            className="btn-secondary"
            onClick={() => setPage((p) => p + 1)}
            disabled={rows.length < 20}
          >
            Next →
          </button>
        </div>
      </aside>
    </>
  );
}
