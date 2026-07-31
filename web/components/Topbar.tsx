"use client";

import { useEffect, useState } from "react";

export default function Topbar({
  backend, // "auto" | "aeon-kernel" | "hf-inference"
  onBackend,
  onToggleSidebar,
  version = "v2.1",
}: {
  backend: string;
  onBackend: (b: string) => void;
  onToggleSidebar?: () => void;
  version?: string;
}) {
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  useEffect(() => {
    const saved = (
      typeof window !== "undefined" ? window.localStorage.getItem("aeon-theme") : null
    ) as "dark" | "light" | null;
    const t = saved || "dark";
    setTheme(t);
    document.documentElement.classList.toggle("light", t === "light");
  }, []);

  const flipTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.classList.toggle("light", next === "light");
    if (typeof window !== "undefined") {
      window.localStorage.setItem("aeon-theme", next);
    }
  };

  return (
    <div className="topbar">
      <button
        className="hamburger"
        onClick={onToggleSidebar}
        aria-label="Toggle sidebar"
        title="Toggle sidebar"
      >
        ≡
      </button>
      <h2>AEON α</h2>
      <span className="badge">{version}</span>
      <span className="badge">{backend === "auto" ? "auto · route" : backend}</span>
      <div className="spacer"></div>
      <select
        className="select-backend"
        value={backend}
        onChange={(e) => onBackend(e.target.value)}
        title="Inference backend"
      >
        <option value="auto">auto (AEON → HF)</option>
        <option value="aeon-kernel">force AEON kernel</option>
        <option value="hf-inference">force HF Inference API</option>
      </select>
      <button className="theme-toggle" onClick={flipTheme}>
        {theme === "dark" ? "☼ light" : "☾ dark"}
      </button>
    </div>
  );
}
