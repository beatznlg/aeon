"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { getThemeConfig, mergeThemeConfig, ThemeConfig } from "@/lib/theme-config";

interface ThemeContextValue {
  config: ThemeConfig;
  resolvedPrimary: string;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}

export default function ThemeProvider({
  children,
  initialConfig,
}: {
  children: ReactNode;
  initialConfig?: Partial<ThemeConfig>;
}) {
  const [config, setConfig] = useState<ThemeConfig>(() =>
    initialConfig ? mergeThemeConfig(initialConfig) : getThemeConfig()
  );

  useEffect(() => {
    if (initialConfig) {
      setConfig(mergeThemeConfig(initialConfig));
    }
  }, [initialConfig]);

  // Persist the resolved config on the window so non-React callers of
  // getThemeConfig() also see the latest branding.
  useEffect(() => {
    if (typeof window !== "undefined") {
      (window as any).__AEON_THEME__ = config;
    }
  }, [config]);

  // Inject primary color as a CSS variable so Tailwind `aeon-primary` can be overridden.
  useEffect(() => {
    if (typeof document === "undefined") return;
    const style = document.documentElement.style;
    style.setProperty("--aeon-primary", config.primaryColor);
    style.setProperty("--aeon-primary-hover", adjustBrightness(config.primaryColor, -20));
  }, [config.primaryColor]);

  const value: ThemeContextValue = {
    config,
    resolvedPrimary: config.primaryColor,
  };

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

function adjustBrightness(hex: string, amount: number): string {
  const normalized = hex.replace("#", "");
  const num = parseInt(normalized, 16);
  let r = (num >> 16) + amount;
  let g = ((num >> 8) & 0x00ff) + amount;
  let b = (num & 0x0000ff) + amount;
  r = Math.max(0, Math.min(255, r));
  g = Math.max(0, Math.min(255, g));
  b = Math.max(0, Math.min(255, b));
  return `#${((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1)}`;
}
