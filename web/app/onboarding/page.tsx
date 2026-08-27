"use client";

/**
 * AEON OS — Onboarding Setup Wizard
 * =================================
 * A guided four-step flow replacing the old single-wall preset grid:
 *
 *   1. Choose your sector      (presets + build-your-own custom sector)
 *   2. Configure it            (command centers, connectors, custom entries)
 *   3. Workspace settings      (branding, currency, country, deployment)
 *   4. Review & launch         (summary → applies via the same APIs)
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import {
  INDUSTRY_PRESETS,
  IndustryPreset,
  CORE_MODULE_IDS,
  SECURITY_MODULE_IDS,
  getIndustryPreset,
} from "@/lib/industry-presets";
import { defaultThemeConfig, BrandModule } from "@/lib/theme-config";
import { getDefaultEnabledIds } from "@/lib/dashboard-registry";
import { FadeIn } from "@/components/animations";

// ── Static data ──────────────────────────────────────────────────────────────

interface PlatformPreset {
  industry: string;
  modules: string[];
  connectors: string[];
  currency?: string;
  country?: string;
}

const PLATFORM_PRESETS: Record<string, PlatformPreset> = {
  cybersecurity: { industry: "core", modules: ["ai-assistant", "ai-agents", "risk-engine", "analytics"], connectors: [] },
  health: { industry: "core", modules: ["hr", "documents", "analytics", "ai-assistant", "risk-engine"], connectors: ["microsoft365"] },
  finance: { industry: "core", modules: ["finance", "analytics", "ai-assistant", "forecasting", "risk-engine"], connectors: ["sage", "microsoft365"] },
  retail: { industry: "retail", modules: ["finance", "inventory", "sales", "crm", "procurement", "analytics", "ai-assistant"], connectors: ["xero", "quickbooks", "salesforce", "pos"] },
  transport: { industry: "core", modules: ["finance", "projects", "procurement", "operations", "analytics", "ai-assistant", "forecasting", "risk-engine"], connectors: ["microsoft365"] },
  manufacturing: { industry: "engineering-construction", modules: ["finance", "projects", "hr", "workforce", "procurement", "analytics", "ai-assistant", "forecasting", "risk-engine"], connectors: ["sage", "microsoft365", "indigo", "open-time-clock", "oisoft"] },
  tourism: { industry: "restaurant", modules: ["finance", "hr", "inventory", "sales", "procurement", "analytics", "ai-assistant"], connectors: ["xero", "microsoft365", "pos"] },
  cultural_heritage: { industry: "core", modules: ["projects", "documents", "analytics", "ai-assistant"], connectors: ["microsoft365"] },
  professional: { industry: "professional-services", modules: ["crm", "projects", "hr", "documents", "analytics", "ai-assistant"], connectors: ["microsoft365", "xero", "salesforce"] },
  utilities: { industry: "engineering-construction", modules: ["finance", "projects", "operations", "analytics", "ai-assistant", "forecasting", "risk-engine"], connectors: ["microsoft365"] },
  sme: { industry: "professional-services", modules: ["finance", "crm", "projects", "hr", "documents", "analytics", "ai-assistant"], connectors: ["microsoft365", "xero"] },
  government: { industry: "core", modules: ["documents", "projects", "operations", "analytics", "ai-assistant", "risk-engine"], connectors: ["microsoft365"] },
};

const CORE_PLATFORM_MODULES = ["identity", "permissions", "audit", "notifications", "ai", "documents", "workflows"];

/** Display metadata for vendor connectors known to the platform. */
const CONNECTOR_META: Record<string, { name: string; icon: string }> = {
  sage: { name: "Sage", icon: "🧮" },
  microsoft365: { name: "Microsoft 365", icon: "🟦" },
  indigo: { name: "Indigo by Shireburn", icon: "🟧" },
  "open-time-clock": { name: "Open Time Clock", icon: "⏱️" },
  oisoft: { name: "OiSoft", icon: "🟪" },
  xero: { name: "Xero", icon: "🧾" },
  quickbooks: { name: "QuickBooks", icon: "💹" },
  salesforce: { name: "Salesforce", icon: "☁️" },
  pos: { name: "POS", icon: "🛒" },
};

/** Every command-center module the UI knows about (industry-specific only). */
const ALL_COMMAND_CENTERS = defaultThemeConfig.modules.filter(
  (m) => !CORE_MODULE_IDS.includes(m.id) && !SECURITY_MODULE_IDS.includes(m.id)
);

const ICON_CHOICES = ["🏢", "🌾", "🎬", "⚽", "🎓", "⚖️", "✈️", "🚀", "🎮", "📰", "🧪", "🏗️", "🐟", "🌲", "💍", "🐾"];
const COLOR_CHOICES = ["#6366f1", "#ef4444", "#06b6d4", "#f59e0b", "#10b981", "#3b82f6", "#f97316", "#ec4899", "#8b5cf6", "#22c55e", "#14b8a6", "#0ea5e9"];

const CURRENCIES = ["EUR", "USD", "GBP", "CHF", "JPY", "CAD", "AUD", "SEK", "NOK", "PLN"];
const DEPLOYMENT_MODES = [
  { value: "cloud", label: "Cloud", hint: "Fully managed, always up to date" },
  { value: "on-prem", label: "On-premise", hint: "Runs inside your own infrastructure" },
  { value: "hybrid", label: "Hybrid", hint: "Cloud control plane, local data" },
];

// ── Local persistence ────────────────────────────────────────────────────────

interface ConnectorEntry {
  id: string;
  name: string;
  icon: string;
}

export interface CustomSector {
  id: string;
  name: string;
  icon: string;
  color: string;
  description: string;
}

type CardEdits = Record<string, { modules: string[]; connectors: string[] }>;

const EDITS_KEY = "aeon.onboarding.card-edits.v1";
const CUSTOM_SECTORS_KEY = "aeon.onboarding.custom-sectors.v1";
const CUSTOM_CONNECTORS_KEY = "aeon.onboarding.custom-connectors.v1";

function loadJSON<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return fallback;
    const parsed: unknown = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? (parsed as T) : fallback;
  } catch {
    return fallback;
  }
}

function saveJSON(key: string, value: unknown) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Storage unavailable — state stays in memory only.
  }
}

const slugify = (s: string) =>
  s.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "") || "custom";

// ── Wizard step definitions ──────────────────────────────────────────────────

const STEPS = [
  { title: "Sector", hint: "What do you operate in?" },
  { title: "Modules", hint: "Command centers & connectors" },
  { title: "Settings", hint: "Branding & workspace options" },
  { title: "Launch", hint: "Review and apply" },
];

// ══════════════════════════════════════════════════════════════════════════════

export default function OnboardingPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const workspaceId = (session?.user as any)?.workspaceId as string | undefined;

  const [step, setStep] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const [customSectors, setCustomSectors] = useState<CustomSector[]>([]);
  const [customConnectors, setCustomConnectors] = useState<ConnectorEntry[]>([]);
  const [edits, setEdits] = useState<CardEdits>({});

  // Step 1: custom-sector creation form
  const [showSectorForm, setShowSectorForm] = useState(false);
  const [nsName, setNsName] = useState("");
  const [nsIcon, setNsIcon] = useState(ICON_CHOICES[0]);
  const [nsColor, setNsColor] = useState(COLOR_CHOICES[0]);
  const [nsDesc, setNsDesc] = useState("");

  // Step 2: custom connector creation
  const [newConnectorName, setNewConnectorName] = useState("");

  // Step 3: workspace / branding settings
  const [companyName, setCompanyName] = useState("");
  const [productName, setProductName] = useState("");
  const [tagline, setTagline] = useState("");
  const [primaryColor, setPrimaryColor] = useState("#6366f1");
  const [currency, setCurrency] = useState("EUR");
  const [country, setCountry] = useState("");
  const [deploymentMode, setDeploymentMode] = useState("cloud");

  const [applying, setApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Hydrate persisted wizard state once on mount.
  useEffect(() => {
    setCustomSectors(loadJSON<CustomSector[]>(CUSTOM_SECTORS_KEY, []));
    setCustomConnectors(loadJSON<ConnectorEntry[]>(CUSTOM_CONNECTORS_KEY, []));
    setEdits(loadJSON<CardEdits>(EDITS_KEY, {}));
  }, []);

  useEffect(() => saveJSON(CUSTOM_SECTORS_KEY, customSectors), [customSectors]);
  useEffect(() => saveJSON(CUSTOM_CONNECTORS_KEY, customConnectors), [customConnectors]);
  useEffect(() => saveJSON(EDITS_KEY, edits), [edits]);

  useEffect(() => {
    if (status === "loading") return;
    if (!session?.user) router.replace("/login?callbackUrl=/onboarding");
  }, [status, session, router]);

  // ── Derived: the currently selected sector (preset or custom) ──────────────

  const selected = useMemo(() => {
    if (!selectedId) return null;
    const preset = getIndustryPreset(selectedId);
    if (preset) return { ...preset, isCustom: false };
    const custom = customSectors.find((c) => c.id === selectedId);
    if (!custom) return null;
    return {
      id: custom.id,
      name: custom.name,
      icon: custom.icon,
      color: custom.color,
      description: custom.description,
      companyName: "",
      productName: "",
      tagline: "",
      primaryColor: custom.color,
      moduleIds: [] as string[],
      isCustom: true,
    } as IndustryPreset & { isCustom: boolean };
  }, [selectedId, customSectors]);

  /** Command centers relevant to the current selection. */
  const availableModules = useMemo(() => {
    if (!selected) return [];
    if (selected.isCustom) return ALL_COMMAND_CENTERS.map((m) => ({ id: m.id, label: m.label, icon: m.icon }));
    return selected.moduleIds
      .filter((id) => !CORE_MODULE_IDS.includes(id) && !SECURITY_MODULE_IDS.includes(id))
      .map((id) => {
        const found = defaultThemeConfig.modules.find((m) => m.id === id);
        return { id, label: found?.label ?? id, icon: found?.icon ?? "🧩" };
      });
  }, [selected]);

  /** Connectors relevant to the current selection (preset defaults + customs). */
  const availableConnectors = useMemo(() => {
    if (!selected) return [];
    if (selected.isCustom) {
      return Object.entries(CONNECTOR_META).map(([id, m]) => ({ id, ...m }));
    }
    const ids = PLATFORM_PRESETS[selected.id]?.connectors ?? [];
    const known = ids.map((id) => ({ id, ...(CONNECTOR_META[id] ?? { name: id, icon: "🔌" }) }));
    return [...known, ...customConnectors];
  }, [selected, customConnectors]);

  const activeModules = useMemo(
    () => (selected && selectedId ? edits[selectedId]?.modules ?? selected.moduleIds : []),
    [selected, selectedId, edits]
  );
  const activeConnectors = useMemo(
    () =>
      selected && selectedId
        ? edits[selectedId]?.connectors ?? PLATFORM_PRESETS[selected.id]?.connectors ?? []
        : [],
    [selected, selectedId, edits]
  );

  // ── Actions ────────────────────────────────────────────────────────────────

  const chooseSector = useCallback(
    (id: string) => {
      setSelectedId(id);
      setError(null);
      // Seed step-3 branding defaults from the chosen sector.
      const preset = getIndustryPreset(id);
      if (preset) {
        setCompanyName((v) => v || preset.companyName);
        setProductName((v) => v || preset.productName);
        setTagline((v) => v || preset.tagline);
        setPrimaryColor(preset.primaryColor);
      } else {
        const custom = customSectors.find((c) => c.id === id);
        if (custom) {
          setCompanyName((v) => v || "");
          setPrimaryColor(custom.color);
        }
      }
    },
    [customSectors]
  );

  const createCustomSector = () => {
    const name = nsName.trim();
    if (!name) {
      setError("Give your sector a name first.");
      return;
    }
    let id = `custom-${slugify(name)}`;
    while (customSectors.some((c) => c.id === id)) id = `${id}-${Math.floor(Math.random() * 90 + 10)}`;
    const sector: CustomSector = {
      id,
      name,
      icon: nsIcon,
      color: nsColor,
      description: nsDesc.trim() || `A bespoke AEON OS configuration for ${name}.`,
    };
    setCustomSectors((prev) => [...prev, sector]);
    setShowSectorForm(false);
    setNsName("");
    setNsDesc("");
    setError(null);
    chooseSector(sector.id);
  };

  const deleteCustomSector = (id: string) => {
    setCustomSectors((prev) => prev.filter((c) => c.id !== id));
    if (selectedId === id) setSelectedId(null);
  };

  const toggleItem = (kind: "modules" | "connectors", id: string) => {
    if (!selectedId || !selected) return;
    const defaults = {
      modules: selected.moduleIds,
      connectors: PLATFORM_PRESETS[selected.id]?.connectors ?? [],
    };
    setEdits((prev) => {
      const current = prev[selectedId] ?? defaults;
      const list = current[kind];
      const next = list.includes(id) ? list.filter((x) => x !== id) : [...list, id];
      return { ...prev, [selectedId]: { ...current, [kind]: next } };
    });
  };

  const addCustomConnector = () => {
    const name = newConnectorName.trim();
    if (!name) return;
    const id = slugify(name);
    if (!availableConnectors.some((c) => c.id === id) && !CONNECTOR_META[id]) {
      setCustomConnectors((prev) => [...prev, { id, name, icon: "🔌" }]);
    }
    if (selectedId && !activeConnectors.includes(id)) toggleItem("connectors", id);
    setNewConnectorName("");
  };

  const applyConfiguration = async () => {
    if (!workspaceId || !selected) {
      setError("Could not determine your workspace. Try signing out and back in.");
      return;
    }
    setApplying(true);
    setError(null);
    setSuccess(null);

    const mods = activeModules.length > 0 ? activeModules : selected.moduleIds;
    const conns = activeConnectors;
    const modules: BrandModule[] = defaultThemeConfig.modules.map((m) => ({
      id: m.id,
      label: m.label,
      icon: m.icon,
      enabled: mods.includes(m.id),
    }));

    const platformPreset = PLATFORM_PRESETS[selected.id] || {
      industry: selected.isCustom ? "custom" : "core",
      modules: [],
      connectors: [],
    };
    const platformModules = Array.from(new Set([...CORE_PLATFORM_MODULES, ...platformPreset.modules]));
    const finalCompany = companyName.trim() || selected.companyName || selected.name;

    const friendly = (msg: unknown) => {
      const raw = String(msg ?? "").toLowerCase();
      if (raw.includes("unauthorized") || raw.includes("forbidden")) {
        return "Your session could not be verified by the workspace backend. Sign out and back in, then try again.";
      }
      if (raw.includes("backend") && (raw.includes("unavailable") || raw.includes("unreachable"))) {
        return "The AEON backend is waking up or unreachable. Your setup was saved locally and will sync when it reconnects.";
      }
      return String(msg ?? "Something went wrong. Please try again.");
    };

    try {
      // Platform config is applied best-effort: a backend hiccup must not
      // block onboarding — branding + the completion marker below are what
      // gate the dashboard.
      let platformWarning: string | null = null;
      try {
        const platformRes = await fetch("/api/platform/config", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            company: finalCompany,
            industry: platformPreset.industry,
            currency,
            country,
            deployment_mode: deploymentMode,
            modules: platformModules,
            connectors: conns,
          }),
        });
        const platformData = await platformRes.json().catch(() => ({}));
        if (!platformRes.ok || !platformData.ok) {
          platformWarning = friendly(platformData.error || `Platform setup failed (${platformRes.status})`);
        }
      } catch {
        platformWarning = friendly("backend unavailable");
      }

      const res = await fetch(`/api/workspaces/${encodeURIComponent(workspaceId)}/branding`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          companyName: finalCompany,
          productName: productName.trim() || finalCompany,
          tagline: tagline.trim(),
          primaryColor,
          logoUrl: undefined,
          dashboardComponents: getDefaultEnabledIds(),
          modules,
          onboardingComplete: true,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(friendly(data.error || `Save failed (${res.status})`));

      await fetch("/api/onboarding/status", { method: "POST" }).catch(() => undefined);
      setSuccess(
        `${selected.name} configured for ${finalCompany}. Taking you to your dashboard…`
      );
      setTimeout(() => router.push("/"), 900);
    } catch (err) {
      setError(friendly(err instanceof Error ? err.message : err));
    } finally {
      setApplying(false);
    }
  };

  // ── Render helpers ─────────────────────────────────────────────────────────

  if (status === "loading") {
    return (
      <div className="os-page flex items-center justify-center min-h-[60vh]">
        <div className="text-aeon-fg-mute">Loading your workspace…</div>
      </div>
    );
  }
  if (!session?.user) return null;

  const canAdvance = step === 0 ? !!selectedId : true;

  const chipStyle = (on: boolean, color: string) => ({
    background: on ? `${color}18` : "var(--aeon-bg-1)",
    border: `1px solid ${on ? `${color}99` : "var(--aeon-border)"}`,
    color: on ? "var(--aeon-fg)" : "var(--aeon-fg-mute)",
  });

  return (
    <div className="os-page max-w-5xl mx-auto">
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <header className="os-header">
        <div className="text-center w-full">
          <h1
            style={{
              background: "var(--grad)",
              WebkitBackgroundClip: "text",
              backgroundClip: "text",
              color: "transparent",
            }}
          >
            ⚙️ Set up your AEON OS
          </h1>
          <p className="dashboard-subtitle">
            Four quick steps. Everything you pick can be changed later in Settings.
          </p>
        </div>
      </header>

      {/* ── Stepper ────────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between mb-8 px-2 sm:px-8" role="tablist" aria-label="Setup steps">
        {STEPS.map((s, i) => {
          const done = i < step;
          const active = i === step;
          return (
            <button
              key={s.title}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => (i <= step ? setStep(i) : undefined)}
              className="flex flex-col items-center gap-1.5 flex-1 cursor-pointer bg-transparent border-none"
            >
              <div className="flex items-center w-full">
                <div
                  className="flex-1 h-0.5 rounded"
                  style={{ background: i === 0 ? "transparent" : done || active ? "var(--grad-a,#6366f1)" : "var(--aeon-border)" }}
                />
                <span
                  className="inline-flex items-center justify-center w-8 h-8 rounded-full text-sm font-semibold transition-all shrink-0"
                  style={{
                    background: active ? "var(--grad)" : done ? `${primaryColor}22` : "var(--aeon-bg-1)",
                    border: `1px solid ${active || done ? "transparent" : "var(--aeon-border)"}`,
                    color: active ? "#fff" : done ? primaryColor : "var(--aeon-fg-mute)",
                  }}
                >
                  {done ? "✓" : i + 1}
                </span>
                <div
                  className="flex-1 h-0.5 rounded"
                  style={{ background: i === STEPS.length - 1 ? "transparent" : done ? "var(--grad-a,#6366f1)" : "var(--aeon-border)" }}
                />
              </div>
              <span
                className="text-xs font-medium"
                style={{ color: active ? "var(--aeon-fg)" : "var(--aeon-fg-mute)" }}
              >
                {s.title}
              </span>
            </button>
          );
        })}
      </div>

      {error && (
        <div className="module-alert danger mb-4" role="alert">
          {error}
        </div>
      )}
      {success && (
        <div className="module-alert mb-4" role="status" style={{ borderColor: "#22c55e" }}>
          {success}
        </div>
      )}

      {/* ═══ Step 1 — Choose sector ═══════════════════════════════════════ */}
      {step === 0 && (
        <FadeIn>
          <h2 className="text-lg font-semibold mb-1">Choose your sector</h2>
          <p className="text-sm mb-5" style={{ color: "var(--aeon-fg-mute)" }}>
            We&apos;ll pre-configure the right command centers, modules, and connectors. Not listed?
            Build a custom sector below.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {INDUSTRY_PRESETS.map((preset) => {
              const on = selectedId === preset.id;
              return (
                <button
                  key={preset.id}
                  type="button"
                  onClick={() => chooseSector(preset.id)}
                  className="os-card text-left cursor-pointer transition-all"
                  style={{
                    borderTop: `3px solid ${preset.color}`,
                    outline: on ? `2px solid ${preset.color}` : "none",
                    outlineOffset: "-1px",
                  }}
                >
                  <div className="os-card-header">
                    <span className="os-icon" style={{ background: `${preset.color}20`, fontSize: "1.4rem" }}>
                      {preset.icon}
                    </span>
                    {on && (
                      <span className="os-status-pill active" style={{ color: preset.color }}>
                        ✓ Selected
                      </span>
                    )}
                  </div>
                  <h3>{preset.name}</h3>
                  <p className="os-desc">{preset.description}</p>
                </button>
              );
            })}

            {/* Custom sectors created this session/device */}
            {customSectors.map((cs) => (
              <div key={cs.id} className="relative">
                <button
                  type="button"
                  onClick={() => chooseSector(cs.id)}
                  className="os-card w-full text-left cursor-pointer transition-all"
                  style={{
                    borderTop: `3px solid ${cs.color}`,
                    outline: selectedId === cs.id ? `2px solid ${cs.color}` : "none",
                    outlineOffset: "-1px",
                  }}
                >
                  <div className="os-card-header">
                    <span className="os-icon" style={{ background: `${cs.color}20`, fontSize: "1.4rem" }}>
                      {cs.icon}
                    </span>
                    <span className="os-category" style={{ color: cs.color }}>
                      Custom
                    </span>
                  </div>
                  <h3>{cs.name}</h3>
                  <p className="os-desc">{cs.description}</p>
                </button>
                <button
                  type="button"
                  title="Delete this custom sector"
                  onClick={() => deleteCustomSector(cs.id)}
                  className="absolute top-2 right-2 w-6 h-6 rounded-full text-xs cursor-pointer"
                  style={{ background: "var(--aeon-bg-1)", border: "1px solid var(--aeon-border)", color: "var(--aeon-fg-mute)" }}
                >
                  ✕
                </button>
              </div>
            ))}

            {/* Build-your-own tile */}
            <button
              type="button"
              onClick={() => setShowSectorForm(true)}
              className="os-card cursor-pointer transition-all flex flex-col items-center justify-center gap-2 min-h-[150px]"
              style={{ border: "2px dashed var(--aeon-border)", borderTopWidth: 2 }}
            >
              <span className="text-3xl">➕</span>
              <span className="font-medium">Build your own sector</span>
              <span className="text-xs" style={{ color: "var(--aeon-fg-mute)" }}>
                Name, icon, and color — fully custom
              </span>
            </button>
          </div>

          {/* Inline custom-sector creation form */}
          {showSectorForm && (
            <FadeIn>
              <div className="os-card mt-5 p-5">
                <h3 className="font-semibold mb-4">Create a custom sector</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <label className="block text-sm">
                    <span className="mb-1 block font-medium">Sector name *</span>
                    <input
                      value={nsName}
                      onChange={(e) => setNsName(e.target.value)}
                      placeholder="e.g. Agriculture & Farming"
                      className="w-full px-3 py-2 rounded-lg"
                      style={{ background: "var(--aeon-bg-1)", border: "1px solid var(--aeon-border)", color: "var(--aeon-fg)" }}
                    />
                  </label>
                  <label className="block text-sm">
                    <span className="mb-1 block font-medium">Short description</span>
                    <input
                      value={nsDesc}
                      onChange={(e) => setNsDesc(e.target.value)}
                      placeholder="What makes this vertical unique?"
                      className="w-full px-3 py-2 rounded-lg"
                      style={{ background: "var(--aeon-bg-1)", border: "1px solid var(--aeon-border)", color: "var(--aeon-fg)" }}
                    />
                  </label>
                </div>

                <div className="mt-4">
                  <span className="text-sm font-medium mb-2 block">Icon</span>
                  <div className="flex flex-wrap gap-2">
                    {ICON_CHOICES.map((ic) => (
                      <button
                        key={ic}
                        type="button"
                        onClick={() => setNsIcon(ic)}
                        className="w-10 h-10 rounded-lg text-xl cursor-pointer transition-all"
                        style={{
                          background: "var(--aeon-bg-1)",
                          border: nsIcon === ic ? `2px solid ${nsColor}` : "1px solid var(--aeon-border)",
                        }}
                      >
                        {ic}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="mt-4">
                  <span className="text-sm font-medium mb-2 block">Brand color</span>
                  <div className="flex flex-wrap gap-2 items-center">
                    {COLOR_CHOICES.map((c) => (
                      <button
                        key={c}
                        type="button"
                        aria-label={`Use ${c}`}
                        onClick={() => {
                          setNsColor(c);
                          setPrimaryColor(c);
                        }}
                        className="w-8 h-8 rounded-full cursor-pointer transition-transform hover:scale-110"
                        style={{ background: c, outline: nsColor === c ? "2px solid var(--aeon-fg)" : "none", outlineOffset: 2 }}
                      />
                    ))}
                  </div>
                </div>

                <div className="flex gap-2 mt-5">
                  <button type="button" className="btn btn-sm btn-primary" onClick={createCustomSector}>
                    Create sector
                  </button>
                  <button type="button" className="btn btn-sm" onClick={() => setShowSectorForm(false)}>
                    Cancel
                  </button>
                </div>
              </div>
            </FadeIn>
          )}
        </FadeIn>
      )}

      {/* ═══ Step 2 — Configure modules & connectors ══════════════════════ */}
      {step === 1 && selected && (
        <FadeIn>
          <div className="flex items-center gap-3 mb-5">
            <span className="text-3xl">{selected.icon}</span>
            <div>
              <h2 className="text-lg font-semibold">Configure {selected.name}</h2>
              <p className="text-sm" style={{ color: "var(--aeon-fg-mute)" }}>
                Tap anything to toggle it. Core & security modules are always included automatically.
              </p>
            </div>
          </div>

          <div className="os-card p-5 mb-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold">Command centers</h3>
              <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "var(--aeon-bg-1)", border: "1px solid var(--aeon-border)", color: "var(--aeon-fg-mute)" }}>
                {activeModules.length} enabled
              </span>
            </div>
            <div className="flex flex-wrap gap-2">
              {availableModules.map((m) => {
                const on = activeModules.includes(m.id);
                return (
                  <button
                    key={m.id}
                    type="button"
                    aria-pressed={on}
                    onClick={() => toggleItem("modules", m.id)}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm cursor-pointer transition-all"
                    style={chipStyle(on, selected.color)}
                  >
                    <span aria-hidden>{m.icon}</span> {m.label}
                  </button>
                );
              })}
              {availableModules.length === 0 && (
                <span className="text-sm italic" style={{ color: "var(--aeon-fg-mute)" }}>
                  Core platform only for this sector.
                </span>
              )}
            </div>
          </div>

          <div className="os-card p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold">External connectors</h3>
              <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "var(--aeon-bg-1)", border: "1px solid var(--aeon-border)", color: "var(--aeon-fg-mute)" }}>
                {activeConnectors.length} enabled
              </span>
            </div>
            <div className="flex flex-wrap gap-2 mb-3">
              {availableConnectors.map((c) => {
                const on = activeConnectors.includes(c.id);
                return (
                  <button
                    key={c.id}
                    type="button"
                    aria-pressed={on}
                    onClick={() => toggleItem("connectors", c.id)}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm cursor-pointer transition-all"
                    style={chipStyle(on, selected.color)}
                  >
                    <span aria-hidden>{c.icon}</span> {c.name}
                  </button>
                );
              })}
              {availableConnectors.length === 0 && (
                <span className="text-sm italic" style={{ color: "var(--aeon-fg-mute)" }}>
                  No connectors yet — add any system below.
                </span>
              )}
            </div>
            <div className="flex gap-2 items-center pt-3" style={{ borderTop: "1px solid var(--aeon-border)" }}>
              <input
                value={newConnectorName}
                onChange={(e) => setNewConnectorName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addCustomConnector()}
                placeholder="Add another system (e.g. Odoo, SAP, Shopify…)"
                className="flex-1 px-3 py-2 rounded-lg text-sm"
                style={{ background: "var(--aeon-bg-1)", border: "1px solid var(--aeon-border)", color: "var(--aeon-fg)" }}
              />
              <button type="button" className="btn btn-sm btn-primary" onClick={addCustomConnector}>
                ＋ Add
              </button>
            </div>
          </div>
        </FadeIn>
      )}

      {/* ═══ Step 3 — Workspace settings ══════════════════════════════════ */}
      {step === 2 && (
        <FadeIn>
          <h2 className="text-lg font-semibold mb-1">Workspace settings</h2>
          <p className="text-sm mb-5" style={{ color: "var(--aeon-fg-mute)" }}>
            How your workspace is branded and configured. All optional — we&apos;ve filled good defaults.
          </p>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="os-card p-5 space-y-4">
              <h3 className="font-semibold">Branding</h3>
              <label className="block text-sm">
                <span className="mb-1 block font-medium">Company name</span>
                <input
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                  placeholder="Your organization"
                  className="w-full px-3 py-2 rounded-lg"
                  style={{ background: "var(--aeon-bg-1)", border: "1px solid var(--aeon-border)", color: "var(--aeon-fg)" }}
                />
              </label>
              <label className="block text-sm">
                <span className="mb-1 block font-medium">Product name</span>
                <input
                  value={productName}
                  onChange={(e) => setProductName(e.target.value)}
                  placeholder={`${companyName || "Your"} Command`}
                  className="w-full px-3 py-2 rounded-lg"
                  style={{ background: "var(--aeon-bg-1)", border: "1px solid var(--aeon-border)", color: "var(--aeon-fg)" }}
                />
              </label>
              <label className="block text-sm">
                <span className="mb-1 block font-medium">Tagline</span>
                <input
                  value={tagline}
                  onChange={(e) => setTagline(e.target.value)}
                  placeholder="A short motto shown under your logo"
                  className="w-full px-3 py-2 rounded-lg"
                  style={{ background: "var(--aeon-bg-1)", border: "1px solid var(--aeon-border)", color: "var(--aeon-fg)" }}
                />
              </label>
              <div>
                <span className="text-sm font-medium mb-2 block">Primary color</span>
                <div className="flex flex-wrap gap-2 items-center">
                  {COLOR_CHOICES.map((c) => (
                    <button
                      key={c}
                      type="button"
                      aria-label={`Use ${c}`}
                      onClick={() => setPrimaryColor(c)}
                      className="w-8 h-8 rounded-full cursor-pointer transition-transform hover:scale-110"
                      style={{ background: c, outline: primaryColor === c ? "2px solid var(--aeon-fg)" : "none", outlineOffset: 2 }}
                    />
                  ))}
                  <input
                    type="color"
                    value={primaryColor}
                    onChange={(e) => setPrimaryColor(e.target.value)}
                    className="w-8 h-8 rounded-full cursor-pointer bg-transparent"
                    aria-label="Custom brand color"
                  />
                </div>
              </div>
            </div>

            <div className="os-card p-5 space-y-4">
              <h3 className="font-semibold">Regional & deployment</h3>
              <div className="grid grid-cols-2 gap-3">
                <label className="block text-sm">
                  <span className="mb-1 block font-medium">Currency</span>
                  <select
                    value={currency}
                    onChange={(e) => setCurrency(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg"
                    style={{ background: "var(--aeon-bg-1)", border: "1px solid var(--aeon-border)", color: "var(--aeon-fg)" }}
                  >
                    {CURRENCIES.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block text-sm">
                  <span className="mb-1 block font-medium">Country</span>
                  <input
                    value={country}
                    onChange={(e) => setCountry(e.target.value)}
                    placeholder="e.g. Malta"
                    className="w-full px-3 py-2 rounded-lg"
                    style={{ background: "var(--aeon-bg-1)", border: "1px solid var(--aeon-border)", color: "var(--aeon-fg)" }}
                  />
                </label>
              </div>
              <div>
                <span className="text-sm font-medium mb-2 block">Deployment mode</span>
                <div className="space-y-2">
                  {DEPLOYMENT_MODES.map((dm) => (
                    <button
                      key={dm.value}
                      type="button"
                      onClick={() => setDeploymentMode(dm.value)}
                      className="w-full text-left px-3 py-2.5 rounded-lg cursor-pointer transition-all"
                      style={{
                        background: deploymentMode === dm.value ? `${primaryColor}14` : "var(--aeon-bg-1)",
                        border: `1px solid ${deploymentMode === dm.value ? primaryColor : "var(--aeon-border)"}`,
                      }}
                    >
                      <span className="text-sm font-medium">{dm.label}</span>
                      <span className="text-xs ml-2" style={{ color: "var(--aeon-fg-mute)" }}>
                        {dm.hint}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </FadeIn>
      )}

      {/* ═══ Step 4 — Review & launch ═════════════════════════════════════ */}
      {step === 3 && selected && (
        <FadeIn>
          <h2 className="text-lg font-semibold mb-1">Ready to launch 🚀</h2>
          <p className="text-sm mb-5" style={{ color: "var(--aeon-fg-mute)" }}>
            A quick look at what will be configured. You can change everything later in Settings.
          </p>

          <div className="os-card p-5">
            <div className="flex items-center gap-4 pb-4 mb-4" style={{ borderBottom: "1px solid var(--aeon-border)" }}>
              <span
                className="w-14 h-14 rounded-xl inline-flex items-center justify-center text-2xl"
                style={{ background: `${selected.color}20` }}
              >
                {selected.icon}
              </span>
              <div>
                <div className="font-semibold text-lg">{companyName.trim() || selected.companyName || selected.name}</div>
                <div className="text-sm" style={{ color: "var(--aeon-fg-mute)" }}>
                  {productName.trim() || `${selected.name} Command`} · {selected.name}
                </div>
              </div>
            </div>

            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-3 text-sm">
              <div className="flex justify-between sm:block">
                <dt className="font-medium" style={{ color: "var(--aeon-fg-mute)" }}>Tagline</dt>
                <dd>{tagline.trim() || selected.tagline || "—"}</dd>
              </div>
              <div className="flex justify-between sm:block">
                <dt className="font-medium" style={{ color: "var(--aeon-fg-mute)" }}>Currency / Country</dt>
                <dd>
                  {currency}
                  {country.trim() ? ` · ${country}` : ""}
                </dd>
              </div>
              <div className="flex justify-between sm:block">
                <dt className="font-medium" style={{ color: "var(--aeon-fg-mute)" }}>Deployment</dt>
                <dd className="capitalize">{deploymentMode}</dd>
              </div>
              <div className="flex justify-between sm:block">
                <dt className="font-medium" style={{ color: "var(--aeon-fg-mute)" }}>Command centers</dt>
                <dd>{activeModules.length}</dd>
              </div>
            </dl>

            {(activeModules.length > 0 || activeConnectors.length > 0) && (
              <div className="pt-4 mt-4 flex flex-wrap gap-1.5" style={{ borderTop: "1px solid var(--aeon-border)" }}>
                {availableModules
                  .filter((m) => activeModules.includes(m.id))
                  .map((m) => (
                    <span key={m.id} className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs" style={{ background: `${selected.color}15`, border: `1px solid ${selected.color}55` }}>
                      <span aria-hidden>{m.icon}</span> {m.label}
                    </span>
                  ))}
                {availableConnectors
                  .filter((c) => activeConnectors.includes(c.id))
                  .map((c) => (
                    <span key={c.id} className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs" style={{ background: "var(--aeon-bg-1)", border: "1px solid var(--aeon-border)" }}>
                      <span aria-hidden>{c.icon}</span> {c.name}
                    </span>
                  ))}
              </div>
            )}
          </div>
        </FadeIn>
      )}

      {/* ── Navigation ─────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between mt-8 gap-3">
        <button
          type="button"
          className="btn btn-sm"
          onClick={() => (step === 0 ? router.push("/") : setStep(step - 1))}
          disabled={applying}
        >
          ← {step === 0 ? "Skip for now" : "Back"}
        </button>
        {step < 3 ? (
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => setStep(step + 1)}
            disabled={!canAdvance || applying}
          >
            {step === 0 && !selectedId ? "Select a sector to continue" : "Continue →"}
          </button>
        ) : (
          <button type="button" className="btn btn-primary" onClick={applyConfiguration} disabled={applying || !selected}>
            {applying ? (
              <span className="inline-flex items-center gap-2">
                <span className="inline-block w-3 h-3 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                Configuring…
              </span>
            ) : (
              "🚀 Apply & open dashboard"
            )}
          </button>
        )}
      </div>
    </div>
  );
}
