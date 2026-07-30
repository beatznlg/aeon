"use client";

import { ReactNode, useEffect, useState } from "react";
import Link from "next/link";
import { SessionProvider } from "next-auth/react";
import { SidebarProvider } from "./SidebarContext";
import ThemeProvider from "./ThemeProvider";
import UserMenu from "./UserMenu";
import NotificationBell from "./NotificationBell";
import CommandPalette from "./CommandPalette";
import { ThemeConfig } from "@/lib/theme-config";
import { ToastProvider } from "@/lib/toast";

export default function Providers({
  children,
  sidebar,
  initialConfig,
}: {
  children: ReactNode;
  sidebar: ReactNode;
  initialConfig?: Partial<ThemeConfig>;
}) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  useEffect(() => {
    const saved = (typeof window !== "undefined"
      ? window.localStorage.getItem("aeon-theme")
      : null) as "dark" | "light" | null;
    const t = saved || "dark";
    setTheme(t);
    document.documentElement.classList.toggle("light", t === "light");
  }, []);

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.classList.toggle("light", next === "light");
    if (typeof window !== "undefined") {
      window.localStorage.setItem("aeon-theme", next);
    }
  };

  const closeSidebar = () => setSidebarOpen(false);

  return (
    <SessionProvider>
      <ThemeProvider initialConfig={initialConfig}>
        <ToastProvider>
        <SidebarProvider close={closeSidebar}>
          <div
            className={`sidebar-overlay ${sidebarOpen ? "open" : ""}`}
            onClick={closeSidebar}
          />

          <aside className={`sidebar ${sidebarOpen ? "open" : ""}`}>
            {sidebar}
            <div className="sidebar-footer">
              <Link
                href="/settings"
                className="sidebar-footer-link"
                onClick={closeSidebar}
              >
                <span className="sidebar-link-icon">⚙</span>
                <span>Settings & Keys</span>
              </Link>
              <button className="sidebar-footer-link" onClick={toggleTheme}>
                <span className="sidebar-link-icon">
                  {theme === "dark" ? "☼" : "☾"}
                </span>
                <span>{theme === "dark" ? "Light Mode" : "Dark Mode"}</span>
              </button>
            </div>
          </aside>

          <div className="main-content">
            <header className="main-header">
              <div className="main-header-left">
                <button
                  className="btn-icon"
                  onClick={() => setSidebarOpen(true)}
                  title="Menu"
                >
                  ☰
                </button>
                <h1>AEON OS</h1>
              </div>
              <div className="main-header-right">
                <button
                  className="search-trigger-btn"
                  onClick={() => {
                    const event = new KeyboardEvent("keydown", {
                      key: "k",
                      metaKey: true,
                      bubbles: true,
                    });
                    document.dispatchEvent(event);
                  }}
                  title="Search (Cmd+K)"
                >
                  <span>🔍</span>
                  <span className="search-trigger-text">Search</span>
                  <kbd className="search-trigger-kbd">⌘K</kbd>
                </button>
                <NotificationBell />
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
          <CommandPalette />
        </SidebarProvider>
        </ToastProvider>
      </ThemeProvider>
    </SessionProvider>
  );
}
