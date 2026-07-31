"use client";

import { useEffect, useState } from "react";

type Status = {
  ok: boolean;
  ts: number;
  steps: Array<{
    id: string;
    title: string;
    state: "ok" | "warn" | "missing" | "external";
    detail: string;
    href?: string;
    cta?: string;
  }>;
  notes: string[];
};

export default function DeployGuidePanel({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const [status, setStatus] = useState<Status | null>(null);

  useEffect(() => {
    if (!open) return;
    let alive = true;
    async function probe() {
      try {
        const r = await fetch("/api/onboarding/status", { cache: "no-store" });
        const j = (await r.json()) as Status;
        if (alive) setStatus(j);
      } catch {
        if (alive) setStatus(null);
      }
    }
    probe();
    const t = setInterval(probe, 15_000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [open]);

  return (
    <>
      <div className={"drawer-backdrop" + (open ? " open" : "")} onClick={onClose}></div>
      <aside className={"drawer" + (open ? " open" : "")} aria-hidden={!open}>
        <button className="close" onClick={onClose} title="Close">
          ×
        </button>
        <h2>Deploy guide</h2>
        <p style={{ color: "var(--fg-mute)", fontSize: "0.85rem", marginTop: -4 }}>
          Live status of all four integrations. Auto-refresh every 15 s.
        </p>

        {status === null ? (
          <p style={{ color: "var(--fg-mute)" }}>Connecting…</p>
        ) : (
          <>
            <ol className="deploy-steps">
              {status.steps.map((s) => (
                <li key={s.id} className={"deploy-step " + s.state}>
                  <div className="deploy-step-row">
                    <span className={"deploy-mark " + s.state} aria-hidden>
                      {s.state === "ok"
                        ? "✅"
                        : s.state === "warn"
                          ? "🟡"
                          : s.state === "external"
                            ? "↗"
                            : "❌"}
                    </span>
                    <div className="deploy-step-body">
                      <div className="deploy-step-title">{s.title}</div>
                      <div className="deploy-step-detail">{s.detail}</div>
                      {s.href && (
                        <a
                          className="deploy-cta"
                          href={s.href}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          {s.cta || "Open"} ↗
                        </a>
                      )}
                    </div>
                  </div>
                </li>
              ))}
            </ol>

            {status.notes.length > 0 && (
              <div className="deploy-notes">
                <strong>Notes from the server:</strong>
                <ul>
                  {status.notes.map((n, i) => (
                    <li key={i}>{n}</li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}

        <div className="deploy-footer">
          <a
            className="deploy-cta"
            href="https://github.com/beatznlg/aeon"
            target="_blank"
            rel="noopener noreferrer"
          >
            Open the GitHub repo ↗
          </a>
        </div>
      </aside>
    </>
  );
}
