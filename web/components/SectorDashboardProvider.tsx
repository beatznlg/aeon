"use client";

import { useEffect, useState, createContext, useContext, useRef, type ReactNode } from "react";
import type { DashboardData } from "./AeonOSDashboard";

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

export interface SectorTool {
  /** Path segment for the tool, e.g. "threats" for /api/sector/cybersecurity/threats */
  path: string;
  /** Key in the response JSON where the data array/object lives, e.g. "threats" */
  responseKey: string;
  /** Target DashboardData property to map into, e.g. "threats" */
  targetKey: string;
  /** If true, the targetKey receives the entire response object (not just responseKey) */
  entireResponse?: boolean;
}

// ─── Sector tool registrations ───────────────────────────────────────────────

type SectorMap = Record<string, SectorTool[]>;

const SECTOR_TOOLS: SectorMap = {
  cybersecurity: [
    { path: "threats", responseKey: "threats", targetKey: "threats" },
    { path: "vulnerabilities", responseKey: "vulnerabilities", targetKey: "vulnerabilities" },
    { path: "compliance", responseKey: "compliance", targetKey: "compliance" },
    { path: "ip-reputation", responseKey: "ip_reputation", targetKey: "ip_reputation" },
    { path: "news", responseKey: "news", targetKey: "security_news" },
  ],
  health: [
    { path: "diagnostics", responseKey: "diagnostics", targetKey: "diagnostics" },
    { path: "vitals", responseKey: "vitals", targetKey: "patient_vitals" },
    { path: "drug-interactions", responseKey: "interactions", targetKey: "drug_interactions" },
    { path: "telehealth", responseKey: "triage", targetKey: "telehealth" },
  ],
  finance: [
    { path: "risk", responseKey: "risk", targetKey: "risk_data" },
    { path: "market", responseKey: "market", targetKey: "market_data" },
    { path: "fraud", responseKey: "fraud_cases", targetKey: "fraud_cases" },
    { path: "credit", responseKey: "applications", targetKey: "credit_applications" },
    { path: "payments", responseKey: "accounts", targetKey: "payment_analysis" },
  ],
  retail: [
    { path: "forecast", responseKey: "forecast", targetKey: "forecast" },
    { path: "inventory", responseKey: "inventory", targetKey: "inventory" },
    { path: "suppliers", responseKey: "suppliers", targetKey: "supplier_risks" },
    { path: "pricing", responseKey: "elasticity", targetKey: "price_elasticity" },
  ],
  transport: [
    { path: "traffic", responseKey: "zones", targetKey: "traffic" },
    { path: "fleet", responseKey: "fleet", targetKey: "fleet" },
    { path: "routes", responseKey: "routes", targetKey: "route_plan" },
  ],
  manufacturing: [
    { path: "maintenance", responseKey: "machines", targetKey: "maintenance" },
    { path: "quality", responseKey: "batches", targetKey: "qc" },
    { path: "logistics", responseKey: "shipments", targetKey: "logistics" },
  ],
  tourism: [
    { path: "bookings", responseKey: "bookings", targetKey: "bookings" },
    { path: "pricing", responseKey: "pricing", targetKey: "pricing" },
    { path: "concierge", responseKey: "requests", targetKey: "concierge" },
    { path: "visitors", responseKey: "venues", targetKey: "visitor_data" },
  ],
  utilities: [
    { path: "resources", responseKey: "resources", targetKey: "resource_data" },
    { path: "services", responseKey: "services", targetKey: "public_services" },
    { path: "waste", responseKey: "districts", targetKey: "waste_data" },
    { path: "grid", responseKey: "regions", targetKey: "energy_grid" },
  ],
  cultural_heritage: [
    { path: "visitors", responseKey: "venues", targetKey: "visitor_data" },
    { path: "sites", responseKey: "sites", targetKey: "heritage_sites" },
    { path: "exhibitions", responseKey: "exhibitions", targetKey: "exhibitions" },
    { path: "tours", responseKey: "tours", targetKey: "virtual_tours" },
  ],
  sme: [
    { path: "workflows", responseKey: "workflows", targetKey: "workflow_data" },
    { path: "documents", responseKey: "documents", targetKey: "document_queue" },
    { path: "support", responseKey: "tickets", targetKey: "support_tickets" },
    { path: "supply-chain", responseKey: "chains", targetKey: "supply_chain" },
  ],
};

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
        fetch(`/api/sector/${sectorId}/${tool.path}`, { cache: "no-store" })
          .then((r) => {
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
