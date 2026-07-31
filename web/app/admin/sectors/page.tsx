"use client";

import { useEffect, useState, useMemo, useCallback, useRef } from "react";
import { useSession } from "next-auth/react";
import { redirect } from "next/navigation";
import Link from "next/link";
import { KPICard, Badge, DataTable, Widget } from "@/components/AeonOSDashboard";
import SectorInlineEditor from "@/components/SectorInlineEditor";
import { FadeIn, StaggerContainer, StaggerItem, ScaleOnHover, motion } from "@/components/animations";

// ─── Sector definitions ──────────────────────────────────────────────────────

interface SectorDef {
  id: string;
  name: string;
  icon: string;
  color: string;
  description: string;
  tools: { path: string; label: string; icon: string }[];
}

const SECTORS: SectorDef[] = [
  {
    id: "cybersecurity", name: "Cybersecurity", icon: "🛡️", color: "#ef4444",
    description: "Threat intelligence, vulnerability scanning, compliance & IP reputation",
    tools: [
      { path: "threats", label: "Threat Intelligence", icon: "⚠️" },
      { path: "vulnerabilities", label: "Vulnerability Scan", icon: "🔓" },
      { path: "compliance", label: "Compliance Posture", icon: "✓" },
      { path: "ip-reputation", label: "IP Reputation", icon: "🌐" },
      { path: "news", label: "Security News", icon: "📰" },
    ],
  },
  {
    id: "health", name: "Healthcare", icon: "🏥", color: "#22c55e",
    description: "AI diagnostics, patient vitals, drug interactions & telehealth",
    tools: [
      { path: "diagnostics", label: "Diagnostic Analysis", icon: "🔬" },
      { path: "vitals", label: "Patient Vitals", icon: "📈" },
      { path: "drug-interactions", label: "Drug Interactions", icon: "💊" },
      { path: "telehealth", label: "Telehealth Triage", icon: "📹" },
    ],
  },
  {
    id: "finance", name: "Finance", icon: "💰", color: "#f59e0b",
    description: "Risk analysis, market forecasting, fraud detection & credit scoring",
    tools: [
      { path: "risk", label: "Risk Assessment", icon: "📊" },
      { path: "market", label: "Market Forecast", icon: "📈" },
      { path: "fraud", label: "Fraud Detection", icon: "🔍" },
      { path: "credit", label: "Credit Scoring", icon: "💳" },
      { path: "payments", label: "Payment Analysis", icon: "💸" },
    ],
  },
  {
    id: "retail", name: "Retail & E-commerce", icon: "📦", color: "#a855f7",
    description: "Demand forecasting, inventory optimization & supplier risk",
    tools: [
      { path: "forecast", label: "Demand Forecast", icon: "📊" },
      { path: "inventory", label: "Inventory Status", icon: "📋" },
      { path: "suppliers", label: "Supplier Risk", icon: "🚚" },
      { path: "pricing", label: "Price Elasticity", icon: "🏷️" },
    ],
  },
  {
    id: "transport", name: "Transport & Logistics", icon: "🚚", color: "#3b82f6",
    description: "Traffic management, fleet scheduling & route optimization",
    tools: [
      { path: "traffic", label: "Traffic Zones", icon: "🚦" },
      { path: "fleet", label: "Fleet Scheduling", icon: "🚛" },
      { path: "routes", label: "Route Planning", icon: "🗺️" },
    ],
  },
  {
    id: "manufacturing", name: "Manufacturing", icon: "🏭", color: "#f97316",
    description: "Predictive maintenance, quality control & smart logistics",
    tools: [
      { path: "maintenance", label: "Machine Health", icon: "⚙️" },
      { path: "quality", label: "Quality Control", icon: "✓" },
      { path: "logistics", label: "Smart Logistics", icon: "🚚" },
    ],
  },
  {
    id: "tourism", name: "Tourism & Hospitality", icon: "🏨", color: "#ec4899",
    description: "Booking optimization, dynamic pricing & automated concierge",
    tools: [
      { path: "bookings", label: "Booking Optimization", icon: "📅" },
      { path: "pricing", label: "Dynamic Pricing", icon: "💰" },
      { path: "concierge", label: "Concierge Triage", icon: "🤵" },
      { path: "visitors", label: "Visitor Analytics", icon: "👥" },
    ],
  },
  {
    id: "utilities", name: "Utilities & Public Sector", icon: "⚡", color: "#06b6d4",
    description: "Resource optimization, public services, waste & energy grid",
    tools: [
      { path: "resources", label: "Resource Optimization", icon: "💧" },
      { path: "services", label: "Public Services KPI", icon: "🏛️" },
      { path: "waste", label: "Waste Management", icon: "♻️" },
      { path: "grid", label: "Energy Grid", icon: "🔌" },
    ],
  },
  {
    id: "cultural_heritage", name: "Cultural Heritage", icon: "🎭", color: "#14b8a6",
    description: "Visitor engagement, heritage sites, exhibitions & virtual tours",
    tools: [
      { path: "visitors", label: "Visitor Engagement", icon: "👥" },
      { path: "sites", label: "Heritage Sites", icon: "🏛️" },
      { path: "exhibitions", label: "Exhibition Planning", icon: "🖼️" },
      { path: "tours", label: "Virtual Tours", icon: "🎧" },
    ],
  },
  {
    id: "sme", name: "SME Business Suite", icon: "🏢", color: "#6366f1",
    description: "Workflow automation, document processing, AI support & supply chain",
    tools: [
      { path: "workflows", label: "Workflow Automation", icon: "🤖" },
      { path: "documents", label: "Document Processing", icon: "📄" },
      { path: "support", label: "AI Support Desk", icon: "🎧" },
      { path: "supply-chain", label: "Supply Chain", icon: "🔗" },
    ],
  },
];

// ─── Types ───────────────────────────────────────────────────────────────────

interface SectorToolState {
  label: string;
  icon: string;
  path: string;
  loading: boolean;
  error: string | null;
  data: unknown;
}

interface SectorState {
  expanded: boolean;
  loading: boolean;
  tools: Record<string, SectorToolState>;
}

type ViewMode = "grid" | "compact";

// ─── Helpers ─────────────────────────────────────────────────────────────────

function getRowCount(data: unknown): number {
  if (Array.isArray(data)) return data.length;
  if (data && typeof data === "object") {
    // Try common array keys
    for (const key of ["threats", "vulnerabilities", "diagnostics", "vitals", "interactions",
      "triage", "fraud_cases", "applications", "accounts", "forecast", "suppliers",
      "zones", "fleet", "routes", "machines", "batches", "shipments", "bookings",
      "pricing", "requests", "venues", "resources", "services", "districts",
      "regions", "sites", "exhibitions", "tours", "workflows", "documents",
      "tickets", "chains", "inventory", "risk", "market", "elasticity",
      "compliance", "ip_reputation", "news"]) {
      const val = (data as Record<string, unknown>)[key];
      if (Array.isArray(val)) return val.length;
    }
  }
  return 0;
}

function getStatusColor(sectorId: string): string {
  const sector = SECTORS.find((s) => s.id === sectorId);
  return sector?.color ?? "#6366f1";
}

// ─── Main Component ──────────────────────────────────────────────────────────

export default function AdminSectorsPage() {
  const { data: session } = useSession();
  const role = (session?.user as any)?.role;
  const isAdmin = role === "ADMIN" || role === "SUPER_ADMIN";

  // Redirect non-admins
  if (session && !isAdmin) {
    redirect("/settings");
  }

  const [sectors, setSectors] = useState<Record<string, SectorState>>({});
  const [search, setSearch] = useState("");
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [globalLoading, setGlobalLoading] = useState(true);
  const [globalLoadAll, setGlobalLoadAll] = useState(false);
  const [expandedAll, setExpandedAll] = useState(false);
  const [managing, setManaging] = useState<Record<string, boolean>>({});
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [nextRefreshIn, setNextRefreshIn] = useState(30);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);

  // Initialize sector states
  useEffect(() => {
    const init: Record<string, SectorState> = {};
    for (const sector of SECTORS) {
      init[sector.id] = {
        expanded: false,
        loading: false,
        tools: {},
      };
      for (const tool of sector.tools) {
        init[sector.id].tools[tool.path] = {
          label: tool.label,
          icon: tool.icon,
          path: tool.path,
          loading: false,
          error: null,
          data: null,
        };
      }
    }
    setSectors(init);
    setGlobalLoading(false);
  }, []);

  const fetchToolData = useCallback(async (sectorId: string, toolPath: string) => {
    setSectors((prev) => ({
      ...prev,
      [sectorId]: {
        ...prev[sectorId],
        tools: {
          ...prev[sectorId].tools,
          [toolPath]: { ...prev[sectorId].tools[toolPath], loading: true, error: null },
        },
      },
    }));

    try {
      const res = await fetch(`/api/sector/${sectorId}/${toolPath}`, { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      setSectors((prev) => ({
        ...prev,
        [sectorId]: {
          ...prev[sectorId],
          tools: {
            ...prev[sectorId].tools,
            [toolPath]: { ...prev[sectorId].tools[toolPath], loading: false, data },
          },
        },
      }));
    } catch (err) {
      setSectors((prev) => ({
        ...prev,
        [sectorId]: {
          ...prev[sectorId],
          tools: {
            ...prev[sectorId].tools,
            [toolPath]: { ...prev[sectorId].tools[toolPath], loading: false, error: err instanceof Error ? err.message : String(err) },
          },
        },
      }));
    }
  }, []);

  const fetchSectorAll = useCallback(async (sectorId: string) => {
    setSectors((prev) => ({
      ...prev,
      [sectorId]: { ...prev[sectorId], loading: true, expanded: true },
    }));

    const sector = SECTORS.find((s) => s.id === sectorId);
    if (!sector) return;

    await Promise.all(sector.tools.map((tool) => fetchToolData(sectorId, tool.path)));

    setSectors((prev) => ({
      ...prev,
      [sectorId]: { ...prev[sectorId], loading: false },
    }));
  }, [fetchToolData]);

  // Keep a live ref to sectors so the polling interval always sees current state
  // without resetting the interval whenever sectors updates.
  const sectorsRef = useRef(sectors);
  useEffect(() => {
    sectorsRef.current = sectors;
  }, [sectors]);

  // Auto-polling: refreshes all expanded sectors every 30s
  useEffect(() => {
    if (!autoRefresh) return;

    const intervalId = setInterval(async () => {
      const expandedSectors = Object.entries(sectorsRef.current)
        .filter(([, s]) => s.expanded)
        .map(([id]) => id);
      if (expandedSectors.length > 0) {
        await Promise.all(expandedSectors.map((id) => fetchSectorAll(id)));
        setLastRefreshed(new Date());
      }
      setNextRefreshIn(30);
    }, 30_000);

    const countdownId = setInterval(() => {
      setNextRefreshIn((prev) => Math.max(0, prev - 1));
    }, 1000);

    return () => {
      clearInterval(intervalId);
      clearInterval(countdownId);
    };
  }, [autoRefresh, fetchSectorAll]);

  const fetchAllSectors = async () => {
    setGlobalLoadAll(true);
    setExpandedAll(true);
    await Promise.all(SECTORS.map((s) => fetchSectorAll(s.id)));
    setGlobalLoadAll(false);
  };

  const toggleSector = (sectorId: string) => {
    setSectors((prev) => {
      const isExpanded = prev[sectorId]?.expanded ?? false;
      if (!isExpanded) {
        // Fetch data on first expand
        fetchSectorAll(sectorId);
      }
      return {
        ...prev,
        [sectorId]: { ...prev[sectorId], expanded: !isExpanded },
      };
    });
  };

  // Filter sectors by search
  const filteredSectors = useMemo(() => {
    if (!search.trim()) return SECTORS;
    const q = search.toLowerCase();
    return SECTORS.filter(
      (s) =>
        s.name.toLowerCase().includes(q) ||
        s.description.toLowerCase().includes(q) ||
        s.tools.some((t) => t.label.toLowerCase().includes(q))
    );
  }, [search]);

  // Calculate global stats
  const globalStats = useMemo(() => {
    let totalRows = 0;
    let loadedSectors = 0;
    for (const sectorId of Object.keys(sectors)) {
      const sector = sectors[sectorId];
      if (!sector) continue;
      let hasData = false;
      for (const toolPath of Object.keys(sector.tools)) {
        const tool = sector.tools[toolPath];
        if (tool.data) {
          totalRows += getRowCount(tool.data);
          hasData = true;
        }
      }
      if (hasData) loadedSectors++;
    }
    return { totalRows, loadedSectors };
  }, [sectors]);

  if (!session) {
    return (
      <div className="os-page">
        <div style={{ color: "var(--fg-mute)", padding: 40, textAlign: "center" }}>Sign in to access admin panel</div>
      </div>
    );
  }

  return (
    <div className="os-page">
      {/* ── Header ── */}
      <header className="os-header">
        <div>
          <Link href="/admin" className="os-back">← Admin Panel</Link>
          <h1>🏢 Sector Data Manager</h1>
          <p className="dashboard-subtitle">
            Unified view of all 10 industry verticals — view threat intel, diagnostics, market data, and more from one dashboard
          </p>
        </div>
        <div className="os-app-meta">
          <span>📊 {globalStats.totalRows} data points</span>
          <span>🔵 {globalStats.loadedSectors}/{SECTORS.length} sectors loaded</span>
        </div>
      </header>

      {/* ── Controls Bar ── */}
      <div className="admin-sectors-controls">
        <div className="admin-search-wrapper">
          <span className="admin-search-icon">🔍</span>
          <input
            type="text"
            className="admin-search-input"
            placeholder="Search sectors, tools, or descriptions..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          {search && (
            <button className="admin-search-clear" onClick={() => setSearch("")}>×</button>
          )}
        </div>
        <div className="admin-controls-actions">
          <button
            className={`btn ${globalLoadAll ? "btn-loading" : ""}`}
            onClick={fetchAllSectors}
            disabled={globalLoadAll}
          >
            {globalLoadAll ? "⏳ Loading..." : "📥 Load All"}
          </button>
          <button
            className={`admin-refresh-toggle ${autoRefresh ? "active" : ""}`}
            onClick={() => setAutoRefresh((p) => !p)}
            title={autoRefresh ? "Auto-refresh on" : "Auto-refresh off"}
          >
            {autoRefresh ? "🔄" : "⏸️"}
            <span className="admin-refresh-label">
              {autoRefresh ? `${nextRefreshIn}s` : "Paused"}
            </span>
          </button>
          <div className="admin-view-toggle">
            <button
              className={`admin-view-btn ${viewMode === "grid" ? "active" : ""}`}
              onClick={() => setViewMode("grid")}
              title="Grid view"
            >⊞</button>
            <button
              className={`admin-view-btn ${viewMode === "compact" ? "active" : ""}`}
              onClick={() => setViewMode("compact")}
              title="Compact view"
            >≡</button>
          </div>
        </div>
      </div>

      {/* ── Global Stats Bar ── */}
      <div className="admin-global-stats">
        <div className="admin-stat-pill">
          <span>🛡️</span> <strong>{globalStats.loadedSectors}</strong> sectors loaded
        </div>
        <div className="admin-stat-pill">
          <span>📊</span> <strong>{globalStats.totalRows}</strong> data points
        </div>
        <div className="admin-stat-pill">
          <span>📡</span> <strong>{40}</strong> API endpoints
        </div>
        <div className="admin-stat-pill">
          <span>👁️</span> <strong>{filteredSectors.length}/{SECTORS.length}</strong> visible
        </div>
        <div className="admin-stat-pill admin-refresh-indicator" title={lastRefreshed ? `Last refreshed: ${lastRefreshed.toLocaleTimeString()}` : ""}>
          {autoRefresh ? (
            <>
              <span className="admin-refresh-spinner">↻</span>
              <strong>{nextRefreshIn}s</strong> auto-refresh
            </>
          ) : (
            <>
              <span>⏸️</span>
              <strong>Paused</strong>
            </>
          )}
          {lastRefreshed && (
            <span className="admin-refresh-time">{lastRefreshed.toLocaleTimeString()}</span>
          )}
        </div>
      </div>

      {/* ── Sector Grid ── */}
      {globalLoading ? (
        <div className="loading-spinner">Loading sectors...</div>
      ) : filteredSectors.length === 0 ? (
        <div className="empty-state">
          <p>🔍 No sectors match &quot;{search}&quot;</p>
          <button className="btn btn-sm" onClick={() => setSearch("")}>Clear search</button>
        </div>
      ) : (
        <StaggerContainer className={`admin-sector-grid ${viewMode === "compact" ? "compact" : ""}`}>
          {filteredSectors.map((sector) => {
            const state = sectors[sector.id];
            const isExpanded = state?.expanded ?? false;
            const isSectorLoading = state?.loading ?? false;

            // Count total rows for this sector
            let sectorRows = 0;
            let loadedTools = 0;
            let totalTools = sector.tools.length;
            if (state) {
              for (const toolPath of Object.keys(state.tools)) {
                const tool = state.tools[toolPath];
                if (tool.data) {
                  sectorRows += getRowCount(tool.data);
                  loadedTools++;
                }
              }
            }

            return (
              <StaggerItem key={sector.id}>
              <ScaleOnHover>
              <div
                className={`admin-sector-card ${isExpanded ? "expanded" : ""}`}
                style={{ borderColor: sector.color }}
              >
                {/* ── Sector Header (collapsed view) ── */}
                <button
                  className="admin-sector-header"
                  onClick={() => toggleSector(sector.id)}
                  style={{ borderLeft: `4px solid ${sector.color}` }}
                >
                  <div className="admin-sector-icon-wrapper" style={{ background: `${sector.color}20`, color: sector.color }}>
                    <span className="admin-sector-icon">{sector.icon}</span>
                  </div>
                  <div className="admin-sector-info">
                    <div className="admin-sector-name">{sector.name}</div>
                    <div className="admin-sector-desc">{sector.description}</div>
                  </div>
                  <div className="admin-sector-meta">
                    {isSectorLoading ? (
                      <span className="loading-dots">Loading</span>
                    ) : (
                      <>
                        <span className="admin-sector-tool-count">{loadedTools}/{totalTools} tools</span>
                        {sectorRows > 0 && <span className="admin-sector-row-count">{sectorRows} rows</span>}
                      </>
                    )}
                    <span className={`admin-sector-chevron ${isExpanded ? "open" : ""}`}>▾</span>
                  </div>
                </button>

                {/* ── Expanded Tool Data ── */}
                {isExpanded && (
                  <div className="admin-sector-body">
                    {totalTools === 0 ? (
                      <div className="empty-tools">No tools configured for this sector</div>
                    ) : (
                      <div className="admin-tools-grid">
                        {sector.tools.map((tool) => {
                          const toolState = state?.tools[tool.path];
                          const isLoading = toolState?.loading ?? false;
                          const error = toolState?.error ?? null;
                          const data = toolState?.data ?? null;
                          const dataRows = getRowCount(data);

                          return (
                            <div key={tool.path} className="admin-tool-card" style={{ borderLeft: `3px solid ${sector.color}` }}>
                              <div className="admin-tool-header">
                                <span className="admin-tool-icon">{tool.icon}</span>
                                <span className="admin-tool-name">{tool.label}</span>
                                {isLoading && <span className="loading-dots">Fetching</span>}
                                {!isLoading && data && (
                                  <>
                                    <span className="admin-tool-badge">{dataRows} items</span>
                                    <button
                                      className="admin-tool-manage"
                                      onClick={() =>
                                        setManaging((prev) => ({
                                          ...prev,
                                          [`${sector.id}/${tool.path}`]: !prev[`${sector.id}/${tool.path}`],
                                        }))
                                      }
                                    >
                                      {managing[`${sector.id}/${tool.path}`] ? "📋 View" : "✏️ Manage"}
                                    </button>
                                  </>
                                )}
                                {!isLoading && !data && !error && (
                                  <button
                                    className="btn btn-xs"
                                    onClick={() => fetchToolData(sector.id, tool.path)}
                                  >
                                    Load
                                  </button>
                                )}
                              </div>
                              {error && <div className="admin-tool-error">⚠ {error}</div>}
                              {data && (
                                <>
                                  <div className="admin-tool-preview">
                                    <ToolDataPreview
                                      data={data}
                                      sectorId={sector.id}
                                      toolPath={tool.path}
                                      accentColor={sector.color}
                                      editing={!!managing[`${sector.id}/${tool.path}`]}
                                      onToggleEdit={() =>
                                        setManaging((prev) => ({
                                          ...prev,
                                          [`${sector.id}/${tool.path}`]: !prev[`${sector.id}/${tool.path}`],
                                        }))
                                      }
                                      onDataChanged={() => fetchToolData(sector.id, tool.path)}
                                    />
                                  </div>
                                </>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}
              </div>
              </ScaleOnHover>
              </StaggerItem>
            );
          })}
        </StaggerContainer>
      )}
    </div>
  );
}

// ─── Tool Data Preview ────────────────────────────────────────────────────────

// Common ID field candidates across all 40 tools
const ID_FIELD_CANDIDATES = [
  "id", "cve", "sku", "supplier", "transaction_id",
  "applicant_id", "account_id", "zone", "depot", "stops", "machine_id",
  "batch_id", "route_id", "property", "room", "guest_id", "venue",
  "resource", "service", "district", "region", "site", "theme",
  "process", "document_type", "query", "chain_id", "analyzed_symptoms",
  "patient_id", "medications", "symptoms", "indicator",
];

function detectIdField(records: Record<string, unknown>[]): string {
  if (records.length === 0) return "id";
  const keys = Object.keys(records[0]);
  for (const candidate of ID_FIELD_CANDIDATES) {
    if (keys.includes(candidate)) return candidate;
  }
  return keys[0] || "id";
}

const DATA_KEY_CANDIDATES = [
  "threats", "vulnerabilities", "diagnostics", "vitals",
  "interactions", "triage", "fraud_cases", "applications", "accounts",
  "forecast", "suppliers", "zones", "fleet", "routes", "machines",
  "batches", "shipments", "bookings", "pricing", "requests", "venues",
  "resources", "services", "districts", "regions", "sites", "exhibitions",
  "tours", "workflows", "documents", "tickets", "chains",
];

function detectDataKey(data: Record<string, unknown>): string {
  for (const candidate of DATA_KEY_CANDIDATES) {
    if (candidate in data && Array.isArray(data[candidate])) return candidate;
  }
  return "data";
}

interface ToolDataPreviewProps {
  data: unknown;
  sectorId: string;
  toolPath: string;
  accentColor: string;
  editing: boolean;
  onToggleEdit: () => void;
  onDataChanged: () => void;
}

function ToolDataPreview({
  data,
  sectorId,
  toolPath,
  accentColor,
  editing,
  onToggleEdit,
  onDataChanged,
}: ToolDataPreviewProps) {
  // Try to find the primary array in the response
  const records = findRecords(data);

  // Detect id_field and data_key
  const dataObj = (data || {}) as Record<string, unknown>;
  const dataKey = detectDataKey(dataObj);
  const idField = records && records.length > 0 ? detectIdField(records) : "id";

  // Get column keys from the records
  const columns = records && records.length > 0 ? getColumnKeys(records) : [];

  // ── Edit mode: show the inline editor ──
  if (editing) {
    return (
      <SectorInlineEditor
        sectorId={sectorId}
        toolPath={toolPath}
        dataKey={dataKey}
        idField={idField}
        responseData={dataObj}
        records={records || []}
        columns={columns}
        onDataChanged={onDataChanged}
        accentColor={accentColor}
      />
    );
  }

  // ── Display mode: show the table or object preview ──
  if (!records || records.length === 0) {
    return <ObjectPreview data={data as Record<string, unknown>} />;
  }

  if (columns.length === 0) return <ObjectPreview data={data as Record<string, unknown>} />;

  return (
    <div className="admin-tool-table-wrapper">
      <table className="admin-tool-table">
        <thead>
          <tr>
            {columns.slice(0, 5).map((col) => (
              <th key={col}>{formatColumnName(col)}</th>
            ))}
            {columns.length > 5 && <th>+{columns.length - 5} more</th>}
          </tr>
        </thead>
        <tbody>
          {records.slice(0, 5).map((record, idx) => (
            <tr key={idx}>
              {columns.slice(0, 5).map((col) => (
                <td key={col}>{formatCellValue(record[col])}</td>
              ))}
              {columns.length > 5 && <td className="admin-tool-more">…</td>}
            </tr>
          ))}
        </tbody>
      </table>
      {records.length > 5 && (
        <div className="admin-tool-footer">
          Showing 5 of {records.length} records
        </div>
      )}
    </div>
  );
}

function findRecords(data: unknown): Record<string, unknown>[] | null {
  if (!data || typeof data !== "object") return null;

  const obj = data as Record<string, unknown>;

  // Direct array
  if (Array.isArray(data) && data.length > 0 && typeof data[0] === "object") {
    return data as Record<string, unknown>[];
  }

  // Search for array keys
  const arrayKeys = [
    "threats", "vulnerabilities", "diagnostics", "vitals", "interactions",
    "triage", "fraud_cases", "applications", "accounts", "forecast", "forecast",
    "inventory", "suppliers", "zones", "fleet", "routes", "machines",
    "batches", "shipments", "bookings", "pricing", "requests", "venues",
    "resources", "services", "districts", "regions", "sites", "exhibitions",
    "tours", "workflows", "documents", "tickets", "chains",
    "supply_chain", "visitor_data", "heritage_sites", "virtual_tours",
    "resource_data", "public_services", "waste_data", "energy_grid",
    "document_queue", "support_tickets", "supply_chain",
  ];

  for (const key of arrayKeys) {
    const val = obj[key];
    if (Array.isArray(val) && val.length > 0 && typeof val[0] === "object") {
      return val as Record<string, unknown>[];
    }
  }

  // Nested object with `data` key
  if (obj.data && Array.isArray(obj.data)) {
    return obj.data as Record<string, unknown>[];
  }

  return null;
}

function getColumnKeys(records: Record<string, unknown>[]): string[] {
  const keys = new Set<string>();
  for (const record of records) {
    for (const key of Object.keys(record)) {
      // Skip nested objects and arrays for table display
      const val = record[key];
      if (typeof val !== "object" || val === null || typeof val === "boolean") {
        keys.add(key);
      }
    }
    if (keys.size >= 10) break;
  }
  return Array.from(keys);
}

function formatColumnName(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .replace(/([a-z])([A-Z])/g, "$1 $2");
}

function formatCellValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "✓" : "✗";
  if (typeof value === "number") {
    if (Number.isInteger(value)) return value.toLocaleString();
    return value.toFixed(2);
  }
  if (typeof value === "string") {
    if (value.length > 30) return value.substring(0, 27) + "…";
    return value;
  }
  if (typeof value === "object") {
    if (Array.isArray(value)) {
      if (value.length === 0) return "[]";
      if (typeof value[0] === "string") return value.slice(0, 3).join(", ") + (value.length > 3 ? "…" : "");
      return `[${value.length} items]`;
    }
    return JSON.stringify(value).substring(0, 30) + "…";
  }
  return String(value);
}

function ObjectPreview({ data }: { data: Record<string, unknown> }) {
  // Extract top-level interesting keys
  const skipKeys = new Set(["ok"]);
  const entries = Object.entries(data).filter(([k]) => !skipKeys.has(k));
  if (entries.length === 0) return <div className="admin-empty-data">No data</div>;

  return (
    <div className="admin-object-preview">
      {entries.slice(0, 8).map(([key, value]) => (
        <div key={key} className="admin-kv-row">
          <span className="admin-kv-key">{formatColumnName(key)}</span>
          <span className="admin-kv-value">
            {typeof value === "object" ? (
              Array.isArray(value) ? (
                <span className="admin-array-indicator">{value.length} items</span>
              ) : value ? (
                <span>📊 {Object.keys(value as Record<string, unknown>).length} fields</span>
              ) : (
                "—"
              )
            ) : (
              formatCellValue(value)
            )}
          </span>
        </div>
      ))}
      {entries.length > 8 && <div className="admin-kv-more">+{entries.length - 8} more fields</div>}
    </div>
  );
}
