"use client";

import { useEffect, useState, createContext, useContext, useRef, type ReactNode } from "react";
import type { DashboardData } from "./AeonOSDashboard";
import {
  getSectorTools,
  listRegisteredSectors,
  type SectorToolDefinition,
} from "@/lib/sector-registry";
export type { SectorToolDefinition as SectorTool } from "@/lib/sector-registry";

const SECTOR_TOOLS: Record<string, SectorToolDefinition[]> = Object.fromEntries(
  listRegisteredSectors().map((sector) => [sector.id, getSectorTools(sector.id)])
);

const REFRESH_INTERVAL_MS = 30_000;

/**
 * Sector Dashboard Provider
 * ==========================
 * Fetches from individual /api/sector/[sector]/[tool] endpoints and assembles
 * the results into the DashboardData shape expected by the existing dashboard
 * components (CyberSecurityDashboard, HealthDashboard, etc.).
 *
 * Auto-polls every {REFRESH_INTERVAL_MS}ms so data stays current without
 * requiring a page reload.
 */

// ─── Tool endpoint descriptor ────────────────────────────────────────────────

// ─── Context ─────────────────────────────────────────────────────────────────

interface SectorDataContextValue {
  data: DashboardData | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
  lastRefreshed: Date | null;
  nextRefreshIn: number;
  isLive: boolean;
  /** Increments on every successful data fetch — used to trigger animations */
  refreshKey: number;
}

const SectorDataContext = createContext<SectorDataContextValue>({
  data: null,
  loading: true,
  error: null,
  refresh: () => {},
  lastRefreshed: null,
  nextRefreshIn: REFRESH_INTERVAL_MS,
  isLive: false,
  refreshKey: 0,
});

export function useSectorDataContext() {
  return useContext(SectorDataContext);
}

// ─── Provider ────────────────────────────────────────────────────────────────

interface SectorDashboardProviderProps {
  sectorId: string;
  children: ReactNode;
  /** Optional fallback dashboard data (e.g., from the unified endpoint) */
  fallbackData?: DashboardData | null;
}

export function SectorDashboardProvider({
  sectorId,
  children,
  fallbackData,
}: SectorDashboardProviderProps) {
  const [data, setData] = useState<DashboardData | null>(fallbackData ?? null);
  const [loading, setLoading] = useState(!fallbackData);
  const [error, setError] = useState<string | null>(null);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);
  const [nextRefreshIn, setNextRefreshIn] = useState(REFRESH_INTERVAL_MS);
  const [isLive, setIsLive] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const tools = SECTOR_TOOLS[sectorId];
  const hasTools = tools && tools.length > 0;

  async function fetchAll() {
    if (!hasTools) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);

    const results = await Promise.allSettled(
      tools.map((tool) =>
        fetch(`/api/sector/${sectorId}/${tool.path}`, { cache: "no-store" }).then((r) => {
          if (!r.ok) throw new Error(`HTTP ${r.status}`);
          return r.json();
        })
      )
    );

    const assembled: Record<string, unknown> = { ok: true };
    let anyError = false;

    results.forEach((result, idx) => {
      const tool = tools[idx];
      if (result.status === "fulfilled") {
        const body = result.value;
        if (tool.entireResponse) {
          assembled[tool.targetKey] = body;
        } else {
          assembled[tool.targetKey] = body[tool.responseKey] ?? null;
        }
      } else {
        anyError = true;
        assembled[tool.targetKey] = null;
      }
    });

    setData(assembled as DashboardData);
    setLoading(false);
    setLastRefreshed(new Date());
    setNextRefreshIn(REFRESH_INTERVAL_MS);
    setIsLive(true);
    setRefreshKey((k) => k + 1); // signal data changed for animations
    if (anyError) {
      setError("Some sector tools could not be loaded");
    }
  }

  // Initial fetch + auto-polling interval
  useEffect(() => {
    if (hasTools) {
      fetchAll();
    } else {
      setLoading(false);
    }

    // Auto-poll every REFRESH_INTERVAL_MS
    intervalRef.current = setInterval(() => {
      fetchAll();
    }, REFRESH_INTERVAL_MS);

    // Countdown tick every 1s
    const countdownId = setInterval(() => {
      setNextRefreshIn((prev) => Math.max(0, prev - 1000));
    }, 1000);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
      clearInterval(countdownId);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sectorId]);

  // Reset countdown after refresh
  useEffect(() => {
    if (!loading) {
      setNextRefreshIn(REFRESH_INTERVAL_MS);
    }
  }, [loading]);

  return (
    <SectorDataContext.Provider
      value={{
        data,
        loading,
        error,
        refresh: fetchAll,
        lastRefreshed,
        nextRefreshIn,
        isLive,
        refreshKey,
      }}
    >
      {children}
    </SectorDataContext.Provider>
  );
}

// ─── Fallback hook to try granular endpoints first, then fall back to dashboard ─

export function useSectorDashboardData(sectorId: string, fallbackData?: DashboardData | null) {
  const ctx = useSectorDataContext();
  return {
    ...ctx,
    data: ctx.data ?? fallbackData ?? null,
  };
}
