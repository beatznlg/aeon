/**
 * AEON OS — Company Branding & Theme Configuration
 *
 * Edit this file to rebrand AEON for a specific company or sector.
 * All UI components consume these values via the ThemeProvider.
 */

export interface BrandModule {
  id: string;
  label: string;
  icon: string;
  enabled: boolean;
}

export interface ThemeConfig {
  /** Company/organization name */
  companyName: string;
  /** Product name displayed in the UI */
  productName: string;
  /** Short tagline shown under the logo */
  tagline: string;
  /** Primary brand color (hex) — also used for CSS injection */
  primaryColor: string;
  /** URL to company logo. Omit to use the default AEON glyph. */
  logoUrl?: string;
  /** Default theme mode */
  defaultMode: "dark" | "light";
  /** Feature flags / module toggles for vertical specialization */
  modules: BrandModule[];
  /** Toggleable dashboard component IDs for modular layout */
  dashboardComponents?: string[];
}

export const defaultThemeConfig: ThemeConfig = {
  companyName: "AEON",
  productName: "AEON OS",
  tagline: "Enterprise Intelligence",
  primaryColor: "#6366f1",
  defaultMode: "dark",
  modules: [
    { id: "dashboard", label: "Dashboard", icon: "\u25C8", enabled: true },
    { id: "chat", label: "Chat", icon: "\uD83D\uDCAC", enabled: true },
    { id: "os", label: "OS Modules", icon: "\u229E", enabled: true },
    { id: "automations", label: "Automations", icon: "\uD83E\uDD16", enabled: true },
    { id: "swarms", label: "Swarms", icon: "\uD83D\uDC1D", enabled: true },
    { id: "llm", label: "LLM Brain", icon: "\uD83E\uDDE0", enabled: true },
    { id: "apiKeys", label: "API Keys", icon: "\uD83D\uDD11", enabled: true },
    { id: "billing", label: "Billing & Plans", icon: "\uD83D\uDCB0", enabled: true },
    { id: "observability", label: "Observability", icon: "\uD83D\uDCCA", enabled: true },
    { id: "monitoring", label: "Monitoring", icon: "\uD83D\uDCC8", enabled: true },
    { id: "knowledge", label: "Knowledge", icon: "\uD83D\uDCDA", enabled: true },
    { id: "ragChat", label: "RAG Chat", icon: "\uD83E\uDDE0", enabled: true },
    { id: "aiStudio", label: "AI Studio", icon: "\u2728", enabled: true },
    { id: "notifications", label: "Notifications", icon: "\uD83D\uDD14", enabled: true },
    { id: "activity", label: "Activity", icon: "\u26A1", enabled: true },
    { id: "security", label: "Security & Ops", icon: "\uD83D\uDEE1\uFE0F", enabled: true },
    { id: "anomalies", label: "Anomalies", icon: "\uD83D\uDD0D", enabled: true },
    { id: "incidents", label: "Incidents", icon: "\uD83D\uDEA8", enabled: true },
    { id: "dr", label: "Disaster Recovery", icon: "\uD83D\uDEE1\uFE0F", enabled: true },
    {
      id: "integrations",
      label: "API Gateway & Integrations",
      icon: "\uD83D\uDD17",
      enabled: true,
    },
    { id: "governance", label: "Governance", icon: "\uD83D\uDEE1\uFE0F", enabled: true },
    // Industry command centers
    { id: "cybersecurity", label: "Security Command", icon: "\uD83D\uDEE1\uFE0F", enabled: true },
    { id: "health", label: "Health Command", icon: "\uD83C\uDFE5", enabled: true },
    { id: "finance", label: "Finance Command", icon: "\uD83D\uDCB0", enabled: true },
    { id: "retail", label: "Commerce Command", icon: "\uD83D\uDCE6", enabled: true },
    { id: "transport", label: "Transport Command", icon: "\uD83D\uDE8C", enabled: true },
    { id: "manufacturing", label: "Factory Command", icon: "\uD83C\uDFED", enabled: true },
    { id: "tourism", label: "Hospitality Command", icon: "\uD83C\uDFE8", enabled: true },
    {
      id: "cultural_heritage",
      label: "Cultural Command",
      icon: "\uD83C\uDFDB\uFE0F",
      enabled: true,
    },
    { id: "professional", label: "Professional Hub", icon: "\uD83D\uDCCB", enabled: true },
    { id: "utilities", label: "Utilities Command", icon: "\uD83D\uDCA1", enabled: true },
    { id: "sme", label: "SME Business Suite", icon: "\uD83C\uDFE2", enabled: true },
  ],
};

let runtimeConfig: ThemeConfig = { ...defaultThemeConfig };

export function setThemeConfig(config: Partial<ThemeConfig>) {
  runtimeConfig = { ...runtimeConfig, ...config };
}

export function getThemeConfig(): ThemeConfig {
  if (typeof window !== "undefined" && (window as any).__AEON_THEME__) {
    return { ...runtimeConfig, ...(window as any).__AEON_THEME__ };
  }
  return runtimeConfig;
}

/** Merge a partial (server-fetched) branding payload over the defaults. */
export function mergeThemeConfig(config: Partial<ThemeConfig>): ThemeConfig {
  return { ...defaultThemeConfig, ...config };
}

/** Return true if the supplied role is allowed to manage workspace settings. */
export function isWorkspaceAdmin(role?: string): boolean {
  return role === "ADMIN" || role === "SUPER_ADMIN";
}

/**
 * Check whether a module is enabled in the given branding config.
 * Falls back to the default config if the module is not present.
 */
export function isModuleEnabled(
  config: Partial<ThemeConfig> | undefined,
  moduleId: string,
  defaultEnabled = true
): boolean {
  const modules = config?.modules ?? defaultThemeConfig.modules;
  const mod = modules.find((m) => m.id === moduleId);
  if (!mod) return defaultEnabled;
  return mod.enabled;
}

/**
 * UI module ids that are platform-level and always visible regardless of the
 * tenant's business-module activation (Core modules of the Module Engine).
 */
const ALWAYS_VISIBLE_UI_MODULES = new Set([
  "dashboard",
  "os",
  "llm",
  "apiKeys",
  "notifications",
  "activity",
  "integrations",
  "governance",
  "operatingProfiles",
  "sectorAdmin",
]);

/**
 * Maps tenant Module Engine ids (finance, projects, risk-engine, …) to the UI
 * module ids that should become visible when the tenant activates them.
 * This is the bridge between the Platform configuration and the navigation.
 */
const TENANT_TO_UI_MODULES: Record<string, string[]> = {
  "ai-assistant": ["chat"],
  "ai-agents": ["swarms", "aiStudio"],
  automation: ["automations"],
  workflows: ["automations"],
  analytics: ["observability", "monitoring"],
  documents: ["knowledge", "ragChat"],
  finance: ["billing", "finance"],
  "risk-engine": ["security", "anomalies", "incidents", "dr", "cybersecurity"],
  sales: ["retail", "tourism"],
  inventory: ["retail"],
  crm: ["professional", "sme"],
  hr: ["professional", "health"],
  operations: ["manufacturing", "transport", "utilities"],
};

/**
 * Derive UI module visibility from a tenant's activated Module Engine ids.
 * Platform-level modules stay visible; business modules only show when their
 * tenant module is active; unmapped modules keep their current flag.
 */
export function applyTenantModuleConfig(
  config: Partial<ThemeConfig> | undefined,
  tenantModules: string[]
): Partial<ThemeConfig> {
  const active = new Set(tenantModules);
  const modules = (config?.modules ?? defaultThemeConfig.modules).map((m) => {
    if (ALWAYS_VISIBLE_UI_MODULES.has(m.id)) return { ...m, enabled: true };
    const requiredTenant = Object.entries(TENANT_TO_UI_MODULES)
      .filter(([, uiIds]) => uiIds.includes(m.id))
      .map(([tenantId]) => tenantId);
    if (requiredTenant.length === 0) return m; // unmapped → keep current state
    return { ...m, enabled: requiredTenant.some((id) => active.has(id)) };
  });
  return { ...config, modules };
}

/**
 * Fetch the per-workspace branding from the Next.js API proxy.
 * This is public so it can be called on login/landing pages before auth.
 */
export async function fetchWorkspaceBranding(workspaceId: string): Promise<Partial<ThemeConfig>> {
  const res = await fetch(`/api/workspaces/${encodeURIComponent(workspaceId)}/branding`, {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`Failed to load branding: ${res.status}`);
  }
  const data = await res.json();
  return (data.branding ?? {}) as Partial<ThemeConfig>;
}

/**
 * Update the per-workspace branding. Requires an Authorization header.
 */
export async function updateWorkspaceBranding(
  workspaceId: string,
  branding: Partial<ThemeConfig>,
  token: string
): Promise<Partial<ThemeConfig>> {
  const res = await fetch(`/api/workspaces/${encodeURIComponent(workspaceId)}/branding`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(branding),
  });
  if (!res.ok) {
    throw new Error(`Failed to update branding: ${res.status}`);
  }
  const data = await res.json();
  return (data.branding ?? {}) as Partial<ThemeConfig>;
}
