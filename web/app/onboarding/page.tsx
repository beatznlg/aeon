"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { INDUSTRY_PRESETS, IndustryPreset, CORE_MODULE_IDS, SECURITY_MODULE_IDS, getIndustryPreset } from "@/lib/industry-presets";
import { defaultThemeConfig, BrandModule } from "@/lib/theme-config";
import { getDefaultEnabledIds } from "@/lib/dashboard-registry";
import { FadeIn, StaggerContainer, StaggerItem, ScaleOnHover } from "@/components/animations";

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

/** Display metadata for the vendor connectors enabled by each preset. */
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

const connectorMeta = (id: string) => CONNECTOR_META[id] ?? { name: id, icon: "🔌" };

const moduleMeta = (id: string) => {
  const found = defaultThemeConfig.modules.find((m) => m.id === id);
  return found ? { label: found.label, icon: found.icon } : { label: id, icon: "🧩" };
};

type CardEdits = Record<string, { modules: string[]; connectors: string[] }>;

const EDITS_KEY = "aeon.onboarding.card-edits.v1";

const loadCardEdits = (): CardEdits => {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(EDITS_KEY);
    if (!raw) return {};
    const parsed: unknown = JSON.parse(raw);
    if (parsed && typeof parsed === "object") return parsed as CardEdits;
    return {};
  } catch {
    return {};
  }
};

export default function OnboardingPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const workspaceId = (session?.user as any)?.workspaceId as string | undefined;
  const [applying, setApplying] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [edits, setEdits] = useState<CardEdits>(loadCardEdits);

  useEffect(() => {
    try {
      window.localStorage.setItem(EDITS_KEY, JSON.stringify(edits));
    } catch {
      // Storage unavailable (private mode, quota) — edits stay in memory only.
    }
  }, [edits]);

  const toggleCardItem = (presetId: string, kind: "modules" | "connectors", id: string) => {
    setEdits((prev) => {
      const preset = getIndustryPreset(presetId);
      const defaults = {
        modules: preset?.moduleIds ?? [],
        connectors: PLATFORM_PRESETS[presetId]?.connectors ?? [],
      };
      const current = prev[presetId] ?? defaults;
      const list = current[kind];
      const next = list.includes(id) ? list.filter((x) => x !== id) : [...list, id];
      return { ...prev, [presetId]: { ...current, [kind]: next } };
    });
  };

  const resetCard = (presetId: string) => {
    setEdits((prev) => {
      if (!(presetId in prev)) return prev;
      const next = { ...prev };
      delete next[presetId];
      return next;
    });
  };

  useEffect(() => {
    if (status === "loading") return;
    if (!session?.user) {
      router.replace("/login?callbackUrl=/onboarding");
    }
  }, [status, session, router]);

  const applyPreset = async (preset: IndustryPreset) => {
    if (!workspaceId) {
      setError("Could not determine your workspace. Try signing out and back in.");
      return;
    }
    setApplying(preset.id);
    setError(null);
    setSuccess(null);

    const activeModuleIds = edits[preset.id]?.modules ?? preset.moduleIds;
    const activeConnectors = edits[preset.id]?.connectors ?? PLATFORM_PRESETS[preset.id]?.connectors ?? [];
    const modules: BrandModule[] = defaultThemeConfig.modules.map((m) => ({
      id: m.id,
      label: m.label,
      icon: m.icon,
      enabled: activeModuleIds.includes(m.id),
    }));

    const platformPreset = PLATFORM_PRESETS[preset.id] || {
      industry: "core",
      modules: [],
      connectors: [],
    };
    const platformModules = Array.from(new Set([...CORE_PLATFORM_MODULES, ...platformPreset.modules]));

    const payload = {
      companyName: preset.companyName,
      productName: preset.productName,
      tagline: preset.tagline,
      primaryColor: preset.primaryColor,
      logoUrl: undefined,
      dashboardComponents: getDefaultEnabledIds(),
      modules,
    };

    try {
      const platformRes = await fetch("/api/platform/config", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          company: preset.companyName,
          industry: platformPreset.industry,
          currency: platformPreset.currency || "EUR",
          country: platformPreset.country || "",
          modules: platformModules,
          connectors: activeConnectors,
          deployment_mode: "cloud",
        }),
      });
      const platformData = await platformRes.json();
      if (!platformRes.ok || !platformData.ok) {
        throw new Error(platformData.error || `Platform setup failed (${platformRes.status})`);
      }

      const res = await fetch(`/api/workspaces/${encodeURIComponent(workspaceId)}/branding`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...payload, onboardingComplete: true }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || `Save failed (${res.status})`);
      }
      await fetch("/api/onboarding/status", { method: "POST" });
      setSuccess(`${preset.name} configured for ${preset.companyName}, including its AEON platform modules and connectors.`);
      setTimeout(() => router.push("/"), 900);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setApplying(null);
    }
  };

  if (status === "loading") {
    return (
      <div className="os-page flex items-center justify-center min-h-[60vh]">
        <div className="text-aeon-fg-mute">Loading your workspace…</div>
      </div>
    );
  }

  if (!session?.user) return null;

  return (
    <div className="os-page">
      <header className="os-header">
        <div>
          <h1
            style={{
              background: "var(--grad)",
              WebkitBackgroundClip: "text",
              backgroundClip: "text",
              color: "transparent",
            }}
          >
            🎯 Customize AEON OS for your industry
          </h1>
          <p className="dashboard-subtitle">
            Pick the sector you operate in, then tap the chips to adjust which command centers
            and connectors get enabled. Core and security modules always stay on — you can
            fine-tune everything later in Settings → Branding.
          </p>
        </div>
      </header>

      {error && (
        <div className="module-alert danger" style={{ marginBottom: 16 }}>
          {error}
        </div>
      )}
      {success && (
        <div className="module-alert" style={{ marginBottom: 16, borderColor: "#22c55e" }}>
          {success} Taking you to your dashboard…
        </div>
      )}

      <StaggerContainer className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {INDUSTRY_PRESETS.map((preset) => {
          const isApplying = applying === preset.id;
          const presetConnectors = PLATFORM_PRESETS[preset.id]?.connectors ?? [];
          const presetModules = preset.moduleIds.filter(
            (id) => !CORE_MODULE_IDS.includes(id) && !SECURITY_MODULE_IDS.includes(id)
          );
          const activeModules = edits[preset.id]?.modules ?? preset.moduleIds;
          const activeConnectors = edits[preset.id]?.connectors ?? presetConnectors;
          const activeModuleChips = presetModules.filter((m) => activeModules.includes(m));
          const activeConnectorChips = presetConnectors.filter((c) => activeConnectors.includes(c));
          return (
            <StaggerItem key={preset.id}>
              <ScaleOnHover>
                <button
                  type="button"
                  onClick={() => applyPreset(preset)}
                  disabled={!!applying}
                  className="os-card relative w-full text-left cursor-pointer"
                  style={{ borderTopColor: preset.color, height: "100%" }}
                >
                  {edits[preset.id] && (
                    <span
                      role="button"
                      tabIndex={0}
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        resetCard(preset.id);
                      }}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          e.stopPropagation();
                          resetCard(preset.id);
                        }
                      }}
                      title="Reset to preset defaults"
                      className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs cursor-pointer select-none"
                      style={{
                        position: "absolute",
                        top: 12,
                        right: 12,
                        background: "var(--aeon-bg-1)",
                        border: "1px solid var(--aeon-border)",
                        color: "var(--aeon-fg-soft)",
                      }}
                    >
                      ↺ Reset
                    </span>
                  )}
                  <div className="os-card-header">
                    <span
                      className="os-icon"
                      style={{ background: `${preset.color}20`, fontSize: "1.5rem" }}
                    >
                      {preset.icon}
                    </span>
                    <span className="os-status-pill active" style={{ color: preset.color }}>
                      {activeModules.length} modules · {activeConnectors.length} connectors
                    </span>
                  </div>
                  <h3>{preset.name}</h3>
                  <p className="os-category" style={{ color: preset.color }}>
                    {preset.companyName}
                  </p>
                  <p className="os-desc">{preset.description}</p>
                  <div className="mt-3 pt-3" style={{ borderTop: "1px solid var(--aeon-border)" }}>
                    <div className="flex items-center gap-2 mb-2">
                      <span
                        className="text-xs font-medium uppercase tracking-wide"
                        style={{ color: "var(--aeon-fg-mute)" }}
                      >
                        Command centers
                      </span>
                      <span
                        className="inline-flex items-center justify-center min-w-5 h-5 px-1.5 rounded-full text-xs font-semibold"
                        style={{
                          background: "var(--aeon-bg-1)",
                          border: "1px solid var(--aeon-border)",
                          color: "var(--aeon-fg-soft)",
                        }}
                      >
                        {activeModuleChips.length}
                      </span>
                    </div>
                    {presetModules.length > 0 ? (
                      <div className="flex flex-wrap gap-1.5">
                        {presetModules.map((mid) => {
                          const meta = moduleMeta(mid);
                          const on = activeModules.includes(mid);
                          return (
                            <span
                              key={mid}
                              role="switch"
                              aria-checked={on}
                              title={`${on ? "Disable" : "Enable"} ${meta.label}`}
                              onClick={(e) => {
                                e.preventDefault();
                                e.stopPropagation();
                                toggleCardItem(preset.id, "modules", mid);
                              }}
                              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs whitespace-nowrap cursor-pointer select-none"
                              style={{
                                background: "var(--aeon-bg-1)",
                                border: `1px solid ${on ? `${preset.color}88` : "var(--aeon-border)"}`,
                                color: "var(--aeon-fg-soft)",
                                opacity: on ? 1 : 0.45,
                                textDecoration: on ? "none" : "line-through",
                              }}
                            >
                              <span aria-hidden="true">{meta.icon}</span>
                              {meta.label}
                            </span>
                          );
                        })}
                      </div>
                    ) : (
                      <span className="text-xs italic" style={{ color: "var(--aeon-fg-mute)" }}>
                        Core platform only
                      </span>
                    )}
                  </div>
                  <div className="mt-3 pt-3" style={{ borderTop: "1px solid var(--aeon-border)" }}>
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-xs font-medium uppercase tracking-wide" style={{ color: "var(--aeon-fg-mute)" }}>
                        Enabled connectors
                      </span>
                      <span
                        className="inline-flex items-center justify-center min-w-5 h-5 px-1.5 rounded-full text-xs font-semibold"
                        style={{ background: "var(--aeon-bg-1)", border: "1px solid var(--aeon-border)", color: "var(--aeon-fg-soft)" }}
                      >
                        {activeConnectorChips.length}
                      </span>
                    </div>
                    {presetConnectors.length > 0 ? (
                      <div className="flex flex-wrap gap-1.5">
                        {presetConnectors.map((cid) => {
                          const meta = connectorMeta(cid);
                          const on = activeConnectors.includes(cid);
                          return (
                            <span
                              key={cid}
                              role="switch"
                              aria-checked={on}
                              title={`${on ? "Disable" : "Enable"} ${meta.name}`}
                              onClick={(e) => {
                                e.preventDefault();
                                e.stopPropagation();
                                toggleCardItem(preset.id, "connectors", cid);
                              }}
                              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs whitespace-nowrap cursor-pointer select-none"
                              style={{
                                background: "var(--aeon-bg-1)",
                                border: `1px solid ${on ? `${preset.color}88` : "var(--aeon-border)"}`,
                                color: "var(--aeon-fg-soft)",
                                opacity: on ? 1 : 0.45,
                                textDecoration: on ? "none" : "line-through",
                              }}
                            >
                              <span aria-hidden="true">{meta.icon}</span>
                              {meta.name}
                            </span>
                          );
                        })}
                      </div>
                    ) : (
                      <span className="text-xs italic" style={{ color: "var(--aeon-fg-mute)" }}>
                        No external systems
                      </span>
                    )}
                  </div>
                  <div className="os-card-actions">
                    <span className="btn btn-sm btn-primary w-full justify-center">
                      {isApplying ? (
                        <span className="inline-flex items-center gap-2">
                          <span className="inline-block w-3 h-3 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                          Configuring…
                        </span>
                      ) : (
                        `Use ${preset.name}`
                      )}
                    </span>
                  </div>
                </button>
              </ScaleOnHover>
            </StaggerItem>
          );
        })}
      </StaggerContainer>

      <FadeIn delay={0.2}>
        <div className="flex justify-center mt-8">
          <button
            type="button"
            className="btn btn-sm"
            onClick={() => router.push("/")}
            disabled={!!applying}
          >
            Skip for now — keep the default setup
          </button>
        </div>
      </FadeIn>
    </div>
  );
}
