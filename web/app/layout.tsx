"use client";

import { useState, useEffect } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { SessionProvider } from "next-auth/react";
import UserMenu from "@/components/UserMenu";
import "./globals.css";

// ─── Navigation items ───────────────────────────────────────────
const NAV_ITEMS = [
  {
    section: "Core",
    links: [
      { href: "/", label: "Dashboard", icon: "◈" },
      { href: "/os", label: "OS Modules", icon: "⊞" },
      { href: "/llm", label: "LLM Brain", icon: "⚡" },
    ],
  },
  {
    section: "Modules",
    links: [
      { href: "/os/cybersecurity", label: "Security", icon: "🛡️" },
      { href: "/os/health", label: "Health", icon: "🏥" },
      { href: "/os/finance", label: "Finance", icon: "💰" },
      { href: "/os/retail", label: "Commerce", icon: "📦" },
      { href: "/os/transport", label: "Transport", icon: "🚚" },
      { href: "/os/manufacturing", label: "Manufacturing", icon: "🏭" },
      { href: "/os/tourism", label: "Tourism", icon: "🏨" },
      { href: "/os/cultural_heritage", label: "Cultural", icon: "🎭" },
      { href: "/os/professional", label: "Professional", icon: "📋" },
      { href: "/os/utilities", label: "Utilities", icon: "⚡" },
      { href: "/os/sme", label: "SME Suite", icon: "🏢" },
    ],
  },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [health, setHealth] = useState<{ ok: boolean; backend?: string } | null>(null);
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  useEffect(() => {
    const saved = localStorage.getItem("aeon-theme") as "dark" | "light" | null;
    const t = saved || "dark";
    setTheme(t);
    document.documentElement.classList.toggle("light", t === "light");
  }, []);

  useEffect(() => {
    fetch("/api/health", { cache: "no-store" })
      .then((r) => r.json())
      .then((d) => setHealth(d))
      .catch(() => setHealth({ ok: false }));
    const t = setInterval(() => {
      fetch("/api/health", { cache: "no-store" })
        .then((r) => r.json())
        .then((d) => setHealth(d))
        .catch(() => {});
    }, 30000);
    return () => clearInterval(t);
  }, []);

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.classList.toggle("light", next === "light");
    localStorage.setItem("aeon-theme", next);
  };

  const isActive = (href: string) => {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  };

  return (
    <html lang="en">
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>AEON OS — Enterprise AI Operating System</title>
        <meta name="description" content="AEON OS: Autonomous AI operating system for government and enterprise." />
      </head>
      <body>
        <SessionProvider>
        {/* Mobile overlay */}
        <div
          className={`sidebar-overlay ${sidebarOpen ? "open" : ""}`}
          onClick={() => setSidebarOpen(false)}
        />

        {/* Sidebar */}
        <aside className={`sidebar ${sidebarOpen ? "open" : ""}`}>
          <div className="sidebar-header">
            <div className="sidebar-brand">
              <div className="sidebar-logo">⟁</div>
              <div>
                <div className="sidebar-brand-text">AEON OS</div>
                <div className="sidebar-brand-sub">Enterprise Intelligence</div>
              </div>
            </div>
            <div className="sidebar-status">
              <span className="sidebar-status-dot" />
              <span>
                {health === null
                  ? "Connecting..."
                  : health.ok
                  ? `System Online · ${health.backend || "stub"}`
                  : "Connecting..."}
              </span>
            </div>
          </div>

          <nav className="sidebar-nav">
            {NAV_ITEMS.map((section) => (
              <div key={section.section}>
                <div className="sidebar-section-label">{section.section}</div>
                {section.links.map((link) => (
                  <Link
                    key={link.href}
                    href={link.href}
                    className={`sidebar-link ${isActive(link.href) ? "active" : ""}`}
                    onClick={() => setSidebarOpen(false)}
                  >
                    <span className="sidebar-link-icon">{link.icon}</span>
                    <span className="sidebar-link-text">{link.label}</span>
                  </Link>
                ))}
              </div>
            ))}
          </nav>

          <div className="sidebar-footer">
            <Link href="/settings" className="sidebar-footer-link" onClick={() => setSidebarOpen(false)}>
              <span className="sidebar-link-icon">⚙</span>
              <span>Settings & Keys</span>
            </Link>
            <button className="sidebar-footer-link" onClick={toggleTheme}>
              <span className="sidebar-link-icon">{theme === "dark" ? "☼" : "☾"}</span>
              <span>{theme === "dark" ? "Light Mode" : "Dark Mode"}</span>
            </button>
          </div>
        </aside>

        {/* Main content */}
        <div className="main-content">
          <header className="main-header">
            <div className="main-header-left">
              <button className="btn-icon" onClick={() => setSidebarOpen(true)} title="Menu">
                ☰
              </button>
              <h1>AEON OS</h1>
            </div>
            <div className="main-header-right">
              <UserMenu />
              <Link href="/settings" className="btn btn-sm">
                ⚙ Settings
              </Link>
              <Link href="/llm" className="btn btn-sm btn-primary">
                ⚡ Connect Brain
              </Link>
            </div>
          </header>
          {children}
        </div>
        </SessionProvider>
      </body>
    </html>
  );
}
