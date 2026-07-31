/**
 * Dashboard Component Registry
 * ==============================
 * Modular, toggleable dashboard components for AEON OS.
 * Each component is registered with an id, metadata, and visibility rules.
 * Components can be enabled/disabled per workspace via the branding config.
 */

/* ─── Dashboard Component Definition ─── */

export interface DashboardComponent {
  /** Unique identifier — used as the key in per-workspace config */
  id: string;
  /** Human-readable label shown in the editor UI */
  label: string;
  /** Short description of what this component shows */
  description: string;
  /** Emoji/icon for the picker */
  icon: string;
  /** Default enabled state when no workspace config exists */
  defaultEnabled: boolean;
  /** Minimum role required to see this component ("viewer" | "operator" | "admin") */
  minRole: "viewer" | "operator" | "admin";
  /** Which vertical/module this belongs to (or "core" for always-available) */
  category: "core" | "security" | "modules" | "platform";
  /** Section placement on the dashboard — components render in order */
  section: "status" | "stats" | "alerts" | "modules" | "health" | "features";
  /** CSS grid column span (1, 2, or "full") */
  span?: 1 | 2 | "full";
}

/* ─── Registry ─── */

const ALL_COMPONENTS: DashboardComponent[] = [
  // ═══ Core status (section: "status") ═══
  {
    id: "welcome_banner",
    label: "Welcome Banner",
    description: "Company name, product name, and quick action buttons",
    icon: "👋",
    defaultEnabled: true,
    minRole: "viewer",
    category: "core",
    section: "status",
    span: "full",
  },
  {
    id: "system_status_bar",
    label: "System Status Bar",
    description: "System status, active modules, tools count, LLM backend",
    icon: "📊",
    defaultEnabled: true,
    minRole: "viewer",
    category: "core",
    section: "status",
    span: "full",
  },

  // ═══ Live stats (section: "stats") ═══
  {
    id: "live_metrics",
    label: "Live Metrics",
    description: "Key performance indicators and live dashboard stats",
    icon: "📈",
    defaultEnabled: true,
    minRole: "viewer",
    category: "core",
    section: "stats",
    span: "full",
  },

  // ═══ Alerts (section: "alerts") ═══
  {
    id: "alerts",
    label: "Alerts Panel",
    description: "Active alerts, warnings, and notifications",
    icon: "🔔",
    defaultEnabled: true,
    minRole: "viewer",
    category: "security",
    section: "alerts",
    span: "full",
  },

  // ═══ Module grid (section: "modules") ═══
  {
    id: "command_centers",
    label: "Command Centers",
    description: "Industry-specific module cards that launch each vertical",
    icon: "⊞",
    defaultEnabled: true,
    minRole: "viewer",
    category: "modules",
    section: "modules",
    span: "full",
  },

  // ═══ Health panel (section: "health") ═══
  {
    id: "system_health",
    label: "System Health",
    description: "Real-time system health monitoring panel",
    icon: "",
    defaultEnabled: true,
    minRole: "viewer",
    category: "core",
    section: "health",
    span: "full",
  },

  // ═══ Platform features (section: "features") ═══
  {
    id: "platform_features",
    label: "Platform Capabilities",
    description: "Feature cards showing AEON capabilities (LLM agnostic, security, etc.)",
    icon: "🚀",
    defaultEnabled: false,
    minRole: "viewer",
    category: "platform",
    section: "features",
    span: "full",
  },
  {
    id: "anomaly_summary",
    label: "Anomaly Summary",
    description: "Quick-view card showing recent anomaly counts",
    icon: "⚠️",
    defaultEnabled: false,
    minRole: "operator",
    category: "security",
    section: "stats",
  },
  {
    id: "incident_summary",
    label: "Incident Summary",
    description: "Quick-view card showing recent incident counts",
    icon: "🚨",
    defaultEnabled: false,
    minRole: "operator",
    category: "security",
    section: "stats",
  },
  {
    id: "automation_status",
    label: "Automation Status",
    description: "Automation rule health and execution metrics",
    icon: "🤖",
    defaultEnabled: false,
    minRole: "operator",
    category: "core",
    section: "stats",
  },
];

/* ─── Accessors ─── */

export function getAllComponents(): DashboardComponent[] {
  return ALL_COMPONENTS;
}

export function getComponentsBySection(
  section: DashboardComponent["section"]
): DashboardComponent[] {
  return ALL_COMPONENTS.filter((c) => c.section === section);
}

export function getComponent(id: string): DashboardComponent | undefined {
  return ALL_COMPONENTS.find((c) => c.id === id);
}

export function getDefaultEnabledIds(): string[] {
  return ALL_COMPONENTS.filter((c) => c.defaultEnabled).map((c) => c.id);
}

export function getComponentsByCategory(
  category: DashboardComponent["category"]
): DashboardComponent[] {
  return ALL_COMPONENTS.filter((c) => c.category === category);
}

/**
 * Resolve the enabled component list for a workspace.
 * `config` is the theme/branding config that includes `dashboardComponents` array.
 * Falls back to defaultEnabled when no per-workspace config exists.
 */
export function resolveEnabledComponents(
  config: { dashboardComponents?: string[] } | null,
  role: string
): DashboardComponent[] {
  // Use per-workspace component list, or default to all default-enabled components
  const enabledIds = config?.dashboardComponents ?? getDefaultEnabledIds();
  const isAdmin = role === "admin" || role === "super_admin";

  return ALL_COMPONENTS.filter((comp) => {
    if (!enabledIds.includes(comp.id)) return false;
    // Role-based access
    if (comp.minRole === "admin" && !isAdmin) return false;
    if (comp.minRole === "operator" && !isAdmin && role !== "operator") return false;
    return true;
  });
}

/**
 * Build a dashboard preview config for the editor.
 * Returns ALL components with their current enabled state.
 */
export function getEditorComponentList(
  config: { dashboardComponents?: string[] } | null,
  role: string
): Array<DashboardComponent & { enabled: boolean }> {
  const enabledIds = config?.dashboardComponents ?? getDefaultEnabledIds();
  return ALL_COMPONENTS.map((comp) => ({
    ...comp,
    enabled: enabledIds.includes(comp.id),
  }));
}
