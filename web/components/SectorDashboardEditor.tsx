"use client";

import { useState, useCallback } from "react";
import SectorInlineEditor from "./SectorInlineEditor";

// ─── Tool definitions for each sector ────────────────────────────────────────

const SECTOR_TOOLS: Record<string, { path: string; label: string; icon: string; color: string }[]> =
  {
    cybersecurity: [
      { path: "threats", label: "Threat Intelligence", icon: "⚠️", color: "#ef4444" },
      { path: "vulnerabilities", label: "Vulnerability Scan", icon: "🔓", color: "#ef4444" },
      { path: "compliance", label: "Compliance Posture", icon: "✓", color: "#ef4444" },
      { path: "ip-reputation", label: "IP Reputation", icon: "🌐", color: "#ef4444" },
      { path: "news", label: "Security News", icon: "📰", color: "#ef4444" },
    ],
    health: [
      { path: "diagnostics", label: "Diagnostic Analysis", icon: "🔬", color: "#22c55e" },
      { path: "vitals", label: "Patient Vitals", icon: "📈", color: "#22c55e" },
      { path: "drug-interactions", label: "Drug Interactions", icon: "💊", color: "#22c55e" },
      { path: "telehealth", label: "Telehealth Triage", icon: "📹", color: "#22c55e" },
    ],
    finance: [
      { path: "risk", label: "Risk Assessment", icon: "📊", color: "#f59e0b" },
      { path: "market", label: "Market Forecast", icon: "📈", color: "#f59e0b" },
      { path: "fraud", label: "Fraud Detection", icon: "🔍", color: "#f59e0b" },
      { path: "credit", label: "Credit Scoring", icon: "💳", color: "#f59e0b" },
      { path: "payments", label: "Payment Analysis", icon: "💸", color: "#f59e0b" },
    ],
    retail: [
      { path: "forecast", label: "Demand Forecast", icon: "📊", color: "#a855f7" },
      { path: "inventory", label: "Inventory Status", icon: "📋", color: "#a855f7" },
      { path: "suppliers", label: "Supplier Risk", icon: "🚚", color: "#a855f7" },
      { path: "pricing", label: "Price Elasticity", icon: "🏷️", color: "#a855f7" },
    ],
    transport: [
      { path: "traffic", label: "Traffic Zones", icon: "🚦", color: "#3b82f6" },
      { path: "fleet", label: "Fleet Scheduling", icon: "🚛", color: "#3b82f6" },
      { path: "routes", label: "Route Planning", icon: "🗺️", color: "#3b82f6" },
    ],
    manufacturing: [
      { path: "maintenance", label: "Machine Health", icon: "⚙️", color: "#f97316" },
      { path: "quality", label: "Quality Control", icon: "✓", color: "#f97316" },
      { path: "logistics", label: "Smart Logistics", icon: "🚚", color: "#f97316" },
    ],
    tourism: [
      { path: "bookings", label: "Booking Optimization", icon: "📅", color: "#ec4899" },
      { path: "pricing", label: "Dynamic Pricing", icon: "💰", color: "#ec4899" },
      { path: "concierge", label: "Concierge Triage", icon: "🤵", color: "#ec4899" },
      { path: "visitors", label: "Visitor Analytics", icon: "👥", color: "#ec4899" },
    ],
    utilities: [
      { path: "resources", label: "Resource Optimization", icon: "💧", color: "#06b6d4" },
      { path: "services", label: "Public Services KPI", icon: "🏛️", color: "#06b6d4" },
      { path: "waste", label: "Waste Management", icon: "♻️", color: "#06b6d4" },
      { path: "grid", label: "Energy Grid", icon: "🔌", color: "#06b6d4" },
    ],
    cultural_heritage: [
      { path: "visitors", label: "Visitor Engagement", icon: "👥", color: "#14b8a6" },
      { path: "sites", label: "Heritage Sites", icon: "🏛️", color: "#14b8a6" },
      { path: "exhibitions", label: "Exhibition Planning", icon: "🖼️", color: "#14b8a6" },
      { path: "tours", label: "Virtual Tours", icon: "🎧", color: "#14b8a6" },
    ],
    sme: [
      { path: "workflows", label: "Workflow Automation", icon: "🤖", color: "#6366f1" },
      { path: "documents", label: "Document Processing", icon: "📄", color: "#6366f1" },
      { path: "support", label: "AI Support Desk", icon: "🎧", color: "#6366f1" },
      { path: "supply-chain", label: "Supply Chain", icon: "🔗", color: "#6366f1" },
    ],
    telecom: [
      { path: "network", label: "Network Health", icon: "📡", color: "#0ea5e9" },
      { path: "capacity", label: "Capacity Planning", icon: "📊", color: "#0ea5e9" },
      { path: "faults", label: "Fault Triage", icon: "🚨", color: "#0ea5e9" },
    ],
    agriculture: [
      { path: "yield", label: "Yield Forecast", icon: "🌾", color: "#84cc16" },
      { path: "irrigation", label: "Irrigation Schedule", icon: "💧", color: "#84cc16" },
      { path: "pests", label: "Pest Risk", icon: "🐛", color: "#84cc16" },
    ],
    education: [
      { path: "at-risk", label: "At-Risk Students", icon: "⚠️", color: "#6366f1" },
      { path: "interventions", label: "Intervention Plans", icon: "📋", color: "#6366f1" },
      { path: "outcomes", label: "Program Outcomes", icon: "📈", color: "#6366f1" },
    ],
    public_safety: [
      { path: "incidents", label: "Incident Priority", icon: "🚨", color: "#dc2626" },
      { path: "dispatch", label: "Resource Dispatch", icon: "🚓", color: "#dc2626" },
      { path: "briefs", label: "Ops Briefs", icon: "📰", color: "#dc2626" },
    ],
    real_estate: [
      { path: "valuations", label: "Property Valuations", icon: "🏠", color: "#b45309" },
      { path: "market", label: "Market Trends", icon: "📈", color: "#b45309" },
      { path: "comparables", label: "Comparables", icon: "🗂️", color: "#b45309" },
    ],
  };

// ─── ID field detection ──────────────────────────────────────────────────────

const ID_FIELD_CANDIDATES = [
  "id",
  "cve",
  "sku",
  "supplier",
  "transaction_id",
  "applicant_id",
  "account_id",
  "zone",
  "depot",
  "stops",
  "machine_id",
  "batch_id",
  "route_id",
  "property",
  "room",
  "guest_id",
  "venue",
  "resource",
  "service",
  "district",
  "region",
  "site",
  "theme",
  "process",
  "document_type",
  "query",
  "chain_id",
  "analyzed_symptoms",
  "patient_id",
  "medications",
  "symptoms",
  "indicator",
  "element",
  "node",
  "field",
  "zone",
  "student_id",
  "program",
  "incident_id",
  "unit_id",
  "title",
  "property",
  "comparable_address",
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
  "threats",
  "vulnerabilities",
  "diagnostics",
  "vitals",
  "interactions",
  "triage",
  "fraud_cases",
  "applications",
  "accounts",
  "forecast",
  "suppliers",
  "zones",
  "fleet",
  "routes",
  "machines",
  "batches",
  "shipments",
  "bookings",
  "pricing",
  "requests",
  "venues",
  "resources",
  "services",
  "districts",
  "regions",
  "sites",
  "exhibitions",
  "tours",
  "workflows",
  "documents",
  "tickets",
  "chains",
  "network",
  "capacity",
  "faults",
  "yield",
  "irrigation",
  "pests",
  "students",
  "plans",
  "outcomes",
  "incidents",
  "dispatch",
  "briefs",
  "valuations",
  "market",
  "comparables",
];

function detectDataKey(data: Record<string, unknown>): string {
  for (const candidate of DATA_KEY_CANDIDATES) {
    if (candidate in data && Array.isArray(data[candidate])) return candidate;
  }
  return "data";
}

function getColumnKeys(records: Record<string, unknown>[]): string[] {
  const keys = new Set<string>();
  for (const record of records) {
    for (const key of Object.keys(record)) {
      const val = record[key];
      if (typeof val !== "object" || val === null || typeof val === "boolean") {
        keys.add(key);
      }
    }
    if (keys.size >= 10) break;
  }
  return Array.from(keys);
}

// ─── Editor Panel ────────────────────────────────────────────────────────────

export default function SectorDashboardEditor({ sectorId }: { sectorId: string | undefined }) {
  const [open, setOpen] = useState(false);
  const [toolStates, setToolStates] = useState<
    Record<string, { data: Record<string, unknown> | null; loading: boolean }>
  >({});
  const [editingTool, setEditingTool] = useState<string | null>(null);

  const tools = SECTOR_TOOLS[sectorId || ""] || [];

  const loadTool = useCallback(
    async (toolPath: string) => {
      setToolStates((prev) => ({
        ...prev,
        [toolPath]: { data: prev[toolPath]?.data ?? null, loading: true },
      }));
      try {
        const res = await fetch(`/api/sector/${sectorId}/${toolPath}`, {
          cache: "no-store",
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        setToolStates((prev) => ({
          ...prev,
          [toolPath]: { data: data as Record<string, unknown>, loading: false },
        }));
      } catch {
        setToolStates((prev) => ({
          ...prev,
          [toolPath]: { data: null, loading: false },
        }));
      }
    },
    [sectorId]
  );

  const handleDataChanged = useCallback(
    (toolPath: string) => {
      loadTool(toolPath);
    },
    [loadTool]
  );

  // ── Render active editor for the selected tool ──
  if (editingTool && sectorId) {
    const meta = tools.find((t) => t.path === editingTool);
    const state = toolStates[editingTool];
    const data = state?.data;
    const records = data ? extractRecords(data) : [];
    const columns = records.length > 0 ? getColumnKeys(records) : [];
    const idField = records.length > 0 ? detectIdField(records) : "id";
    const dataKey = data ? detectDataKey(data) : "data";

    return (
      <div className="sector-dash-editor-active">
        <div className="sector-dash-editor-bar">
          <span>
            ✏️ Editing: <strong>{meta?.label || editingTool}</strong>
          </span>
          <button
            className="btn btn-xs"
            onClick={() => setEditingTool(null)}
            style={{ borderColor: meta?.color, color: meta?.color }}
          >
            Done Editing
          </button>
        </div>
        {state?.loading ? (
          <div className="sector-dash-editor-loading">Loading data...</div>
        ) : (
          <SectorInlineEditor
            sectorId={sectorId}
            toolPath={editingTool}
            dataKey={dataKey}
            idField={idField}
            responseData={data || {}}
            records={records}
            columns={columns}
            onDataChanged={() => handleDataChanged(editingTool)}
            accentColor={meta?.color || "#6366f1"}
          />
        )}
      </div>
    );
  }

  // ── Floating toggle button (closed state) ──
  if (!open) {
    return (
      <button
        className="sector-dash-edit-fab"
        onClick={() => setOpen(true)}
        title="Edit sector data"
      >
        ✏️
      </button>
    );
  }

  // ── Tool picker panel (open state) ──
  return (
    <div className="sector-dash-edit-panel">
      <div className="sector-dash-edit-panel-header">
        <h3>✏️ Edit Data Sources</h3>
        <button className="sector-dash-edit-close" onClick={() => setOpen(false)}>
          ×
        </button>
      </div>
      <p className="sector-dash-edit-panel-sub">
        Select a tool endpoint to view and edit its data. Changes are saved immediately via the API.
      </p>
      <div className="sector-dash-edit-tools">
        {tools.map((tool) => {
          const state = toolStates[tool.path];
          const isLoading = state?.loading ?? false;
          const records = state?.data ? extractRecords(state.data) : null;

          return (
            <button
              key={tool.path}
              className="sector-dash-edit-tool-btn"
              style={{ borderLeft: `3px solid ${tool.color}` }}
              onClick={async () => {
                if (!state?.data) await loadTool(tool.path);
                setEditingTool(tool.path);
              }}
              disabled={isLoading}
            >
              <span className="sector-dash-edit-tool-icon">{tool.icon}</span>
              <span className="sector-dash-edit-tool-label">
                {tool.label}
                {records && (
                  <span className="sector-dash-edit-tool-count">
                    {records.length} {records.length === 1 ? "item" : "items"}
                  </span>
                )}
              </span>
              <span className="sector-dash-edit-tool-arrow">→</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function extractRecords(data: Record<string, unknown>): Record<string, unknown>[] {
  if (!data) return [];
  // Direct array
  if (Array.isArray(data)) return data as Record<string, unknown>[];
  // Search for array keys
  for (const key of DATA_KEY_CANDIDATES) {
    const val = data[key];
    if (Array.isArray(val) && val.length > 0 && typeof val[0] === "object") {
      return val as Record<string, unknown>[];
    }
  }
  // Fallback: return first array found
  for (const val of Object.values(data)) {
    if (Array.isArray(val) && val.length > 0 && typeof val[0] === "object") {
      return val as Record<string, unknown>[];
    }
  }
  return [];
}
