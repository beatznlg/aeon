"use client";

import { ReactNode, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { SessionProvider, useSession } from "next-auth/react";
import { SidebarProvider } from "./SidebarContext";
import ThemeProvider from "./ThemeProvider";
import UserMenu from "./UserMenu";
import NotificationBell from "./NotificationBell";
import CommandPalette from "./CommandPalette";
import { ThemeConfig } from "@/lib/theme-config";
import { ToastProvider } from "@/lib/toast";

interface ProvidersProps {
  children: ReactNode;
  sidebar: ReactNode;
  initialConfig?: Partial<ThemeConfig>;
}

export default function Providers(props: ProvidersProps) {
  return (
    <SessionProvider>
      <ApplicationShell {...props} />
    </SessionProvider>
  );
}

function ApplicationShell({ children, sidebar, initialConfig }: ProvidersProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [setupChecked, setSetupChecked] = useState(false);
  const pathname = usePathname();
  const router = useRouter();
  const { status: sessionStatus } = useSession();

  const isPublicSurface =
    pathname === "/login" || pathname === "/showcase" || pathname.startsWith("/landing");
  const isOnboarding = pathname.startsWith("/onboarding");

  useEffect(() => {
    const saved = (
      typeof window !== "undefined" ? window.localStorage.getItem("aeon-theme") : null
    ) as "dark" | "light" | null;
    const nextTheme = saved || "dark";
    setTheme(nextTheme);
    document.documentElement.classList.toggle("light", nextTheme === "light");
  }, []);

  useEffect(() => {
    if (isPublicSurface || isOnboarding || sessionStatus !== "authenticated") {
      setSetupChecked(sessionStatus !== "loading");
      return;
    }

    let cancelled = false;
    setSetupChecked(false);
    fetch("/api/onboarding/status", { cache: "no-store" })
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => {
        if (cancelled) return;
        setSetupChecked(true);
        if (data?.needsSetup) {
          router.replace(`/onboarding?callbackUrl=${encodeURIComponent(pathname || "/")}`);
        }
      })
      .catch(() => {
        if (!cancelled) setSetupChecked(true);
      });

    return () => {
      cancelled = true;
    };
  }, [isOnboarding, isPublicSurface, pathname, router, sessionStatus]);

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.classList.toggle("light", next === "light");
    window.localStorage.setItem("aeon-theme", next);
  };

  const closeSidebar = () => setSidebarOpen(false);

  if (isPublicSurface || isOnboarding) {
    return <>{children}</>;
  }

  if (sessionStatus === "loading" || !setupChecked) {
    return (
      <div className="min-h-screen bg-aeon-bg-0 text-aeon-text-1 flex items-center justify-center">
        <div className="text-sm text-aeon-fg-mute">Loading AEON OS...</div>
      </div>
    );
  }

  return (
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
              <Link href="/settings" className="sidebar-footer-link" onClick={closeSidebar}>
                <span className="sidebar-link-icon">⚙</span>
                <span>Settings & Keys</span>
              </Link>
              <button className="sidebar-footer-link" onClick={toggleTheme}>
                <span className="sidebar-link-icon">{theme === "dark" ? "☼" : "☾"}</span>
                <span>{theme === "dark" ? "Light Mode" : "Dark Mode"}</span>
              </button>
            </div>
          </aside>

          <div className="main-content">
            <header className="main-header">
              <div className="main-header-left">
                <button className="btn-icon" onClick={() => setSidebarOpen(true)} title="Menu">
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
  );
}
