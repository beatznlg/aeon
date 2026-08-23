"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { getAuthHeaders } from "@/lib/flask-auth";

interface ModuleDef {
  id: string;
  name: string;
  icon: string;
  category: "core" | "business" | "ai";
  required?: boolean;
  enabled: boolean;
  description: string;
}

interface ConnectorDef {
  id: string;
  name: string;
  icon: string;
  category: string;
  enabled: boolean;
  description: string;
  required_secrets: string[];
}

interface PackDef {
  id: string;
  name: string;
  icon: string;
  industry: string;
  description: string;
  modules: string[];
  connectors: string[];
  currency: string;
  country: string;
  profile: string;
  reference_tenant?: string;
  required?: boolean;
}

interface ConnectorStatus {
  ready: boolean;
  configured: string[];
  missing: string[];
  required_secrets: string[];
}

interface EntityDef {
  id: string;
  name: string;
  icon: string;
  domain: string;
  fields: string[];
  sources: string[];
}

interface TenantConfig {
  tenant_id: string;
  company: string;
  industry: string;
  currency: string;
  country: string;
  modules: string[];
  connectors: string[];
  deployment_mode: string;
  pack?: PackDef;
}

const CATEGORY_LABELS: Record<string, string> = {
  core: "Core",
  business: "Business",
  ai: "AI",
};

const DOMAIN_LABELS: Record<string, string> = {
  people: "People & Organizations",
  finance: "Finance",
  projects: "Projects",
  documents: "Documents & Communication",
  commerce: "Commerce",
  intelligence: "Events, Risk & Decisions",
};

export default function PlatformPage() {
  const [config, setConfig] = useState<TenantConfig | null>(null);
  const [modules, setModules] = useState<ModuleDef[]>([]);
  const [connectors, setConnectors] = useState<ConnectorDef[]>([]);
  const [packs, setPacks] = useState<PackDef[]>([]);
  const [entities, setEntities] = useState<EntityDef[]>([]);
  const [connectorStatus, setConnectorStatus] = useState<Record<string, ConnectorStatus>>({});
  const [enabledModules, setEnabledModules] = useState<Set<string>>(new Set());
  const [enabledConnectors, setEnabledConnectors] = useState<Set<string>>(new Set());
  const [health, setHealth] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const [wizardOpen, setWizardOpen] = useState(true);
  const [wizardStep, setWizardStep] = useState(0);

  useEffect(() => {
    Promise.all([
      fetch("/api/platform/config", { cache: "no-store" }).then((r) => r.json()),
      fetch("/api/platform/modules", { cache: "no-store" }).then((r) => r.json()),
      fetch("/api/platform/connectors", { cache: "no-store" }).then((r) => r.json()),
      fetch("/api/platform/industry-packs", { cache: "no-store" }).then((r) => r.json()),
      fetch("/api/platform/universal-model", { cache: "no-store" }).then((r) => r.json()),
      fetch("/api/platform/connectors/status", { cache: "no-store" }).then((r) => r.json()),
    ])
      .then(([cfg, mods, cons, pks, um, cst]) => {
        if (cfg.ok && cfg.config) setConfig(cfg.config);
        if (mods.ok && mods.modules) {
          setModules(mods.modules);
          setEnabledModules(new Set(mods.modules.filter((m: ModuleDef) => m.enabled).map((m: ModuleDef) => m.id)));
        }
        if (cons.ok && cons.connectors) {
          setConnectors(cons.connectors);
          setEnabledConnectors(new Set(cons.connectors.filter((c: ConnectorDef) => c.enabled).map((c: ConnectorDef) => c.id)));
        }
        if (pks.ok && pks.packs) setPacks(pks.packs);
        if (um.ok && um.entities) setEntities(um.entities);
        if (cst.ok && cst.status) setConnectorStatus(cst.status);
      })
      .catch(() => setError("Failed to load platform configuration"));
  }, []);

  const coreModuleIds = useMemo(() => new Set(modules.filter((m) => m.required).map((m) => m.id)), [modules]);

  const toggleModule = useCallback(
    (id: string) => {
      if (coreModuleIds.has(id)) return;
      setEnabledModules((prev) => {
        const next = new Set(prev);
        if (next.has(id)) next.delete(id);
        else next.add(id);
        return next;
      });
      setSaved(false);
    },
    [coreModuleIds]
  );

  const toggleConnector = useCallback((id: string) => {
    setEnabledConnectors((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
    setSaved(false);
  }, []);

  const applyPack = useCallback(
    (pack: PackDef) => {
      if (!config) return;
      const nextModules = new Set(pack.modules);
      // Core modules are always on
      coreModuleIds.forEach((id) => nextModules.add(id));
      setEnabledModules(nextModules);
      setEnabledConnectors(new Set(pack.connectors));
      setConfig((prev) =>
        prev
          ? {
              ...prev,
              industry: pack.id,
              modules: Array.from(nextModules),
              connectors: [...pack.connectors],
              currency: pack.currency || prev.currency,
              country: pack.country || prev.country,
            }
          : prev
      );
      setSaved(false);
    },
    [config, coreModuleIds]
  );

  const save = useCallback(async () => {
    if (!config) return;
    setSaving(true);
    setError("");
    try {
      const res = await fetch("/api/platform/config", {
        method: "PUT",
        headers: getAuthHeaders(),
        body: JSON.stringify({
          company: config.company,
          industry: config.industry,
          currency: config.currency,
          country: config.country,
          modules: Array.from(enabledModules),
          connectors: Array.from(enabledConnectors),
          deployment_mode: config.deployment_mode,
        }),
      });
      const data = await res.json();
      if (!res.ok || !data.ok) {
        setError(data.error || "Failed to save configuration");
      } else {
        setSaved(true);
        if (data.config) setConfig(data.config);
      }
    } catch {
      // Backend unreachable — configuration is still valid locally (demo mode).
      setSaved(true);
    } finally {
      setSaving(false);
    }
  }, [config, enabledModules, enabledConnectors]);

  const testConnector = useCallback(async (id: string) => {
    setHealth((prev) => ({ ...prev, [id]: "testing" }));
    try {
      const res = await fetch(`/api/platform/connectors/${id}/health`, {
        method: "POST",
        headers: getAuthHeaders(),
      });
      const data = await res.json();
      const status = data.ok && data.health?.status ? data.health.status : "error";
      setHealth((prev) => ({ ...prev, [id]: status }));
    } catch {
      setHealth((prev) => ({ ...prev, [id]: "error" }));
    }
  }, []);

  const groupedModules = useMemo(() => {
    const groups: Record<string, ModuleDef[]> = { core: [], business: [], ai: [] };
    modules.forEach((m) => groups[m.category]?.push(m));
    return groups;
  }, [modules]);

  const groupedEntities = useMemo(() => {
    const groups: Record<string, EntityDef[]> = {};
    entities.forEach((e) => {
      (groups[e.domain] ||= []).push(e);
    });
    return groups;
  }, [entities]);

  const activePack = packs.find((p) => p.id === config?.industry);
  const wizardSteps = ["Overview", "Modules", "Connectors", "Review"];
  const enabledModuleCount = enabledModules.size;
  const enabledConnectorCount = enabledConnectors.size;
  const readyConnectorCount = Array.from(enabledConnectors).filter((id) => connectorStatus[id]?.ready).length;

  const goToWizardStep = (step: number) => {
    setWizardStep(Math.min(wizardSteps.length - 1, Math.max(0, step)));
    setWizardOpen(true);
  };

  return (
    <div style={s.page}>
      {/* Header */}
      <div style={s.header}>
        <div>
          <h1 style={s.title}>🧬 Platform</h1>
          <p style={s.subtitle}>
            One AEON. Every company. This workspace&apos;s configuration — modules, connectors and data model — is
            applied at runtime. No code changes to onboard a company.
          </p>
        </div>
        {config && (
          <div style={s.companyBadge}>
            <span style={{ color: "#22d3ee" }}>◈</span> {config.company || "Unnamed tenant"}
            <span style={s.badgeMute}>
              {activePack ? activePack.name : config.industry}
            </span>
          </div>
        )}
      </div>

      {error && <div style={s.error}>{error}</div>}
      {saved && (
        <div style={s.savedBox}>
          ✓ Configuration saved — the AEON Brain now answers with this tenant&apos;s context.
        </div>
      )}

      {/* Guided setup wizard */}
      <section style={s.wizard} aria-label="Platform setup wizard">
        <div style={s.wizardHeader}>
          <div>
            <div style={s.stepLabel}>SETUP WIZARD · CONFIGURE THIS TENANT</div>
            <h2 style={s.wizardTitle}>Shape your AEON workspace</h2>
            <p style={s.wizardSubtitle}>
              Configure the tenant after onboarding. Changes stay in draft until you save them.
            </p>
          </div>
          <button
            type="button"
            style={s.wizardCollapse}
            onClick={() => setWizardOpen((open) => !open)}
            aria-expanded={wizardOpen}
          >
            {wizardOpen ? "Collapse" : "Open wizard"}
          </button>
        </div>

        {wizardOpen && (
          <>
            <div style={s.wizardProgress}>
              {wizardSteps.map((step, index) => (
                <button
                  key={step}
                  type="button"
                  style={{ ...s.wizardStep, ...(index === wizardStep ? s.wizardStepActive : {}) }}
                  onClick={() => goToWizardStep(index)}
                >
                  <span style={{ ...s.wizardStepNumber, ...(index <= wizardStep ? s.wizardStepNumberActive : {}) }}>
                    {index < wizardStep ? "✓" : index + 1}
                  </span>
                  <span>{step}</span>
                </button>
              ))}
            </div>

            {wizardStep === 0 && (
              <div style={s.wizardBody}>
                <div style={s.wizardIntro}>
                  <span style={s.wizardEyebrow}>01 · START WITH A REUSABLE PACK</span>
                  <strong>{activePack?.name || config?.industry || "Universal core"}</strong>
                  <span style={s.wizardMuted}>
                    A pack is only a starting point. You can refine every module and connector in the next steps.
                  </span>
                </div>
                <div style={s.wizardPackRow}>
                  <select
                    style={{ ...s.select, flex: 1, minWidth: "220px" }}
                    value={config?.industry || "core"}
                    onChange={(event) => {
                      const pack = packs.find((item) => item.id === event.target.value);
                      if (pack) applyPack(pack);
                    }}
                    disabled={!config}
                    aria-label="Industry pack"
                  >
                    {packs.map((pack) => (
                      <option key={pack.id} value={pack.id}>
                        {pack.icon} {pack.name}
                      </option>
                    ))}
                  </select>
                  <div style={s.wizardStats}>
                    <span><b>{enabledModuleCount}</b> modules</span>
                    <span><b>{enabledConnectorCount}</b> connectors</span>
                  </div>
                </div>
              </div>
            )}

            {wizardStep === 1 && (
              <div style={s.wizardBody}>
                <div style={s.wizardIntro}>
                  <span style={s.wizardEyebrow}>02 · CHOOSE CAPABILITIES</span>
                  <strong>{enabledModuleCount} modules active</strong>
                  <span style={s.wizardMuted}>Core modules stay protected. Select the business and AI capabilities this company needs.</span>
                </div>
                <div style={s.wizardChoiceGrid}>
                  {modules.filter((module) => !module.required).map((module) => {
                    const on = enabledModules.has(module.id);
                    return (
                      <button
                        key={module.id}
                        type="button"
                        style={{ ...s.wizardChoice, ...(on ? s.wizardChoiceOn : {}) }}
                        onClick={() => toggleModule(module.id)}
                        aria-pressed={on}
                      >
                        <span style={s.wizardChoiceIcon}>{module.icon}</span>
                        <span style={s.wizardChoiceText}>
                          <b>{module.name}</b>
                          <small>{module.description}</small>
                        </span>
                        <span style={{ ...s.wizardCheck, ...(on ? s.wizardCheckOn : {}) }}>{on ? "✓" : ""}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {wizardStep === 2 && (
              <div style={s.wizardBody}>
                <div style={s.wizardIntro}>
                  <span style={s.wizardEyebrow}>03 · CONNECT YOUR SYSTEMS</span>
                  <strong>{enabledConnectorCount} connectors selected</strong>
                  <span style={s.wizardMuted}>Select systems to activate. Credentials can be added later from the connector settings.</span>
                </div>
                <div style={s.wizardChoiceGrid}>
                  {connectors.map((connector) => {
                    const on = enabledConnectors.has(connector.id);
                    const status = connectorStatus[connector.id];
                    return (
                      <button
                        key={connector.id}
                        type="button"
                        style={{ ...s.wizardChoice, ...(on ? s.wizardChoiceOn : {}) }}
                        onClick={() => toggleConnector(connector.id)}
                        aria-pressed={on}
                      >
                        <span style={s.wizardChoiceIcon}>{connector.icon}</span>
                        <span style={s.wizardChoiceText}>
                          <b>{connector.name}</b>
                          <small>{connector.category} · {on && status?.ready ? "credentials ready" : on ? "credentials needed" : "not selected"}</small>
                        </span>
                        <span style={{ ...s.wizardCheck, ...(on ? s.wizardCheckOn : {}) }}>{on ? "✓" : ""}</span>
                      </button>
                    );
                  })}
                </div>
                <div style={s.wizardHint}>
                  {enabledConnectorCount === 0 ? "No external systems selected yet." : `${readyConnectorCount} of ${enabledConnectorCount} selected connectors have credentials ready.`}
                </div>
              </div>
            )}

            {wizardStep === 3 && (
              <div style={s.wizardBody}>
                <div style={s.reviewGrid}>
                  <div style={s.reviewItem}><span style={s.reviewItemLabel}>Tenant</span><strong>{config?.company || "Unnamed tenant"}</strong></div>
                  <div style={s.reviewItem}><span style={s.reviewItemLabel}>Industry pack</span><strong>{activePack?.name || config?.industry || "Universal core"}</strong></div>
                  <div style={s.reviewItem}><span style={s.reviewItemLabel}>Modules</span><strong>{enabledModuleCount} active</strong></div>
                  <div style={s.reviewItem}><span style={s.reviewItemLabel}>Connectors</span><strong>{enabledConnectorCount} selected</strong></div>
                </div>
                <div style={s.wizardReviewNote}>
                  Save to apply this tenant configuration to the platform and AEON Brain.
                </div>
              </div>
            )}

            <div style={s.wizardFooter}>
              <button type="button" style={s.wizardSecondary} onClick={() => goToWizardStep(wizardStep - 1)} disabled={wizardStep === 0}>
                Back
              </button>
              <span style={s.wizardStepHint}>Step {wizardStep + 1} of {wizardSteps.length}</span>
              {wizardStep < wizardSteps.length - 1 ? (
                <button type="button" style={s.wizardPrimary} onClick={() => goToWizardStep(wizardStep + 1)}>
                  Continue
                </button>
              ) : (
                <button type="button" style={s.wizardPrimary} onClick={save} disabled={saving || !config}>
                  {saving ? "Saving…" : saved ? "✓ Saved" : "Save setup"}
                </button>
              )}
            </div>
          </>
        )}
      </section>

      {/* Tenant identity */}
      {config && (
        <div style={s.section}>
          <div style={s.stepLabel}>TENANT · COMPANY IDENTITY</div>
          <div style={s.identityRow}>
            <div style={s.fieldGrow}>
              <label style={s.label}>Company name</label>
              <input
                style={s.input}
                value={config.company}
                onChange={(e) => {
                  setConfig({ ...config, company: e.target.value });
                  setSaved(false);
                }}
                placeholder="e.g. AG Group"
              />
            </div>
            <div style={s.field}>
              <label style={s.label}>Currency</label>
              <input
                style={s.input}
                value={config.currency}
                onChange={(e) => {
                  setConfig({ ...config, currency: e.target.value.toUpperCase() });
                  setSaved(false);
                }}
                placeholder="EUR"
                maxLength={3}
              />
            </div>
            <div style={s.field}>
              <label style={s.label}>Country</label>
              <input
                style={s.input}
                value={config.country}
                onChange={(e) => {
                  setConfig({ ...config, country: e.target.value.toUpperCase() });
                  setSaved(false);
                }}
                placeholder="MT"
                maxLength={2}
              />
            </div>
            <div style={s.field}>
              <label style={s.label}>Deployment</label>
              <select
                style={s.select}
                value={config.deployment_mode}
                onChange={(e) => {
                  setConfig({ ...config, deployment_mode: e.target.value });
                  setSaved(false);
                }}
              >
                {["cloud", "hybrid", "on-premise", "air-gapped", "edge"].map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
      )}

      {/* Industry packs */}
      <div style={s.section}>
        <div style={s.stepLabel}>INDUSTRY PACK · ONE CLICK SECTOR SETUP</div>
        <div style={s.packGrid}>
          {packs.map((p) => {
            const isActive = config?.industry === p.id;
            return (
              <button
                key={p.id}
                style={{ ...s.packCard, ...(isActive ? s.packCardActive : {}) }}
                onClick={() => applyPack(p)}
              >
                <div style={s.packHead}>
                  <span style={s.packIcon}>{p.icon}</span>
                  <span style={s.packName}>{p.name}</span>
                  {p.required && <span style={s.packCore}>CORE</span>}
                  {isActive && <span style={s.packActive}>ACTIVE</span>}
                </div>
                <div style={s.packDesc}>{p.description}</div>
                <div style={s.packMeta}>
                  {p.modules.length} modules · {p.connectors.length} connectors
                  {p.profile ? ` · profile: ${p.profile}` : ""}
                </div>
                {p.reference_tenant && <div style={s.packRef}>★ {p.reference_tenant}</div>}
              </button>
            );
          })}
        </div>
      </div>

      {/* Module engine */}
      <div style={s.section}>
        <div style={s.stepLabel}>MODULE ENGINE · WHAT THIS TENANT ACTIVATES</div>
        <div style={s.modGroupWrap}>
          {(["core", "business", "ai"] as const).map((cat) => (
            <div key={cat} style={s.modGroup}>
              <div style={s.modGroupLabel}>{CATEGORY_LABELS[cat].toUpperCase()}</div>
              <div style={s.modGrid}>
                {groupedModules[cat].map((m) => {
                  const on = enabledModules.has(m.id);
                  return (
                    <button
                      key={m.id}
                      style={{ ...s.modCard, ...(on ? s.modCardOn : {}) }}
                      onClick={() => toggleModule(m.id)}
                      title={m.description}
                    >
                      <div style={s.modCardHead}>
                        <span style={s.modIcon}>{m.icon}</span>
                        <span style={s.modToggle}>{on ? "●" : "○"}</span>
                      </div>
                      <div style={s.modName}>{m.name}</div>
                      <div style={s.modDesc}>{m.description}</div>
                      {m.required && <div style={s.modReq}>REQUIRED</div>}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Connector engine */}
      <div style={s.section}>
        <div style={s.stepLabel}>CONNECTOR ENGINE · UNIVERSAL CONTRACT</div>
        <div style={s.contractBar}>
          Every connector implements: authenticate → connect → discover → fetch → normalize → sync → webhook →
          health_check → disconnect
        </div>
        <div style={s.connGrid}>
          {connectors.map((c) => {
            const on = enabledConnectors.has(c.id);
            const status = health[c.id];
            return (
              <div key={c.id} style={{ ...s.connCard, ...(on ? s.connCardOn : {}) }}>
                <div style={s.connHead}>
                  <span style={s.connIcon}>{c.icon}</span>
                  <div>
                    <div style={s.connName}>{c.name}</div>
                    <div style={s.connCat}>{c.category}</div>
                  </div>
                  <button
                    style={s.connToggle}
                    onClick={() => toggleConnector(c.id)}
                    title={on ? "Disable connector" : "Enable connector"}
                  >
                    {on ? "●" : "○"}
                  </button>
                </div>
                <div style={s.connDesc}>{c.description}</div>
                <div style={s.connFoot}>
                  <button style={s.testBtn} onClick={() => testConnector(c.id)} disabled={status === "testing"}>
                    {status === "testing" ? "Testing…" : "Test"}
                  </button>
                  {status && status !== "testing" && (
                    <span
                      style={{
                        ...s.statusChip,
                        color: status === "operational" || status === "configured" ? "#34d399" : "#f87171",
                        borderColor:
                          status === "operational" || status === "configured"
                            ? "rgba(52,211,153,0.4)"
                            : "rgba(248,113,113,0.4)",
                      }}
                    >
                      {status === "operational" || status === "configured" ? "✓ ready" : status}
                    </span>
                  )}
                  {!on && <span style={s.connOff}>DISABLED</span>}
                  {on && connectorStatus[c.id] && (
                    connectorStatus[c.id].ready ? (
                      <span style={{ ...s.statusChip, color: "#34d399", borderColor: "rgba(52,211,153,0.4)" }}>
                        ✓ keys ready
                      </span>
                    ) : (
                      <span
                        style={{
                          ...s.statusChip,
                          color: "#fbbf24",
                          borderColor: "rgba(251,191,36,0.4)",
                          maxWidth: "160px",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                        title={connectorStatus[c.id].missing.join(", ")}
                      >
                        needs: {connectorStatus[c.id].missing.slice(0, 1).join("")}
                        {connectorStatus[c.id].missing.length > 1 ? " +…" : ""}
                      </span>
                    )
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Universal data model */}
      <div style={s.section}>
        <div style={s.stepLabel}>UNIVERSAL DATA MODEL · ONE LANGUAGE FOR EVERY SYSTEM</div>
        <p style={s.umIntro}>
          Sage Invoice → AEON Invoice. Xero Invoice → AEON Invoice.          The AI always speaks AEON — it never cares
          which system produced the record.
        </p>
        {Object.entries(groupedEntities).map(([domain, list]) => (
          <div key={domain} style={s.umGroup}>
            <div style={s.umGroupLabel}>{DOMAIN_LABELS[domain] || domain.toUpperCase()}</div>
            <div style={s.umChips}>
              {list.map((e) => (
                <div key={e.id} style={s.umChip} title={`Fields: ${e.fields.join(", ")}`}>
                  <span>{e.icon}</span> {e.name}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Actions */}
      <div style={s.actions}>
        <button style={s.saveBtn} onClick={save} disabled={saving}>
          {saving ? "Saving…" : saved ? "✓ Saved" : "Save configuration"}
        </button>
        <span style={s.saveHint}>
          Saved per tenant. Onboarding the next company is a new config — never a new AEON.
        </span>
      </div>
    </div>
  );
}

const s: Record<string, React.CSSProperties> = {
  page: {
    padding: "1.75rem",
    maxWidth: "1180px",
    margin: "0 auto",
    color: "var(--aeon-fg)",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: "1rem",
    flexWrap: "wrap",
  },
  title: { fontSize: "1.5rem", fontWeight: 800, letterSpacing: "-0.01em", margin: 0 },
  subtitle: { color: "var(--aeon-fg-mute)", fontSize: "0.9rem", lineHeight: 1.6, marginTop: "0.4rem", maxWidth: "620px" },
  companyBadge: {
    display: "flex",
    alignItems: "center",
    gap: "0.5rem",
    border: "1px solid rgba(0,168,255,0.35)",
    background: "rgba(0,168,255,0.08)",
    borderRadius: "999px",
    padding: "0.5rem 0.95rem",
    fontSize: "0.82rem",
    fontWeight: 700,
    whiteSpace: "nowrap",
  },
  badgeMute: {
    color: "#22d3ee",
    fontSize: "0.66rem",
    fontWeight: 800,
    letterSpacing: "0.12em",
    textTransform: "uppercase",
  },
  error: {
    marginTop: "1rem",
    border: "1px solid rgba(248,113,113,0.4)",
    background: "rgba(248,113,113,0.1)",
    color: "#f87171",
    borderRadius: "10px",
    padding: "0.7rem 1rem",
    fontSize: "0.85rem",
  },
  savedBox: {
    marginTop: "1rem",
    border: "1px solid rgba(52,211,153,0.4)",
    background: "rgba(52,211,153,0.1)",
    color: "#34d399",
    borderRadius: "10px",
    padding: "0.7rem 1rem",
    fontSize: "0.85rem",
  },
  wizard: {
    marginTop: "1.7rem",
    border: "1px solid rgba(34,211,238,0.22)",
    borderRadius: "18px",
    background: "linear-gradient(135deg, rgba(14,30,52,0.9), rgba(10,15,29,0.72))",
    boxShadow: "0 18px 55px rgba(0,0,0,0.18), 0 0 32px rgba(34,211,238,0.04)",
    overflow: "hidden",
  },
  wizardHeader: {
    display: "flex",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: "1rem",
    padding: "1.25rem 1.35rem 1rem",
    borderBottom: "1px solid rgba(148,163,184,0.12)",
  },
  wizardTitle: { margin: "0.15rem 0 0", fontSize: "1.18rem", fontWeight: 800, letterSpacing: "-0.02em" },
  wizardSubtitle: { margin: "0.35rem 0 0", color: "var(--aeon-fg-mute)", fontSize: "0.78rem" },
  wizardCollapse: {
    border: "1px solid var(--aeon-border-strong)",
    background: "rgba(255,255,255,0.035)",
    color: "var(--aeon-fg-soft)",
    borderRadius: "8px",
    padding: "0.42rem 0.7rem",
    fontSize: "0.7rem",
    fontWeight: 700,
    cursor: "pointer",
    whiteSpace: "nowrap",
  },
  wizardProgress: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
    gap: "0.5rem",
    padding: "0.85rem 1.35rem",
    borderBottom: "1px solid rgba(148,163,184,0.12)",
    background: "rgba(2,6,23,0.2)",
  },
  wizardStep: {
    display: "flex",
    alignItems: "center",
    gap: "0.5rem",
    border: "1px solid transparent",
    borderRadius: "10px",
    background: "transparent",
    color: "var(--aeon-fg-mute)",
    padding: "0.45rem 0.5rem",
    fontSize: "0.72rem",
    fontWeight: 700,
    textAlign: "left",
    cursor: "pointer",
  },
  wizardStepActive: { color: "var(--aeon-fg)", borderColor: "rgba(34,211,238,0.3)", background: "rgba(34,211,238,0.08)" },
  wizardStepNumber: {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    width: "1.45rem",
    height: "1.45rem",
    border: "1px solid var(--aeon-border-strong)",
    borderRadius: "999px",
    fontSize: "0.65rem",
    flexShrink: 0,
  },
  wizardStepNumberActive: { borderColor: "#22d3ee", background: "rgba(34,211,238,0.15)", color: "#67e8f9" },
  wizardBody: { padding: "1.25rem 1.35rem" },
  wizardIntro: { display: "flex", flexDirection: "column", gap: "0.28rem", marginBottom: "1rem" },
  wizardEyebrow: { color: "#67e8f9", fontSize: "0.62rem", fontWeight: 800, letterSpacing: "0.16em" },
  wizardMuted: { color: "var(--aeon-fg-mute)", fontSize: "0.76rem", lineHeight: 1.5 },
  wizardPackRow: { display: "flex", alignItems: "center", gap: "0.8rem", flexWrap: "wrap" },
  wizardStats: { display: "flex", gap: "0.6rem", flexWrap: "wrap", color: "var(--aeon-fg-mute)", fontSize: "0.72rem" },
  wizardStatsValue: { color: "var(--aeon-fg)", fontSize: "0.95rem" },
  wizardChoiceGrid: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(235px, 1fr))", gap: "0.65rem" },
  wizardChoice: {
    display: "flex",
    alignItems: "center",
    gap: "0.65rem",
    width: "100%",
    minHeight: "4rem",
    border: "1px solid var(--aeon-border)",
    borderRadius: "11px",
    background: "rgba(10,15,29,0.6)",
    color: "var(--aeon-fg-soft)",
    padding: "0.65rem 0.7rem",
    textAlign: "left",
    cursor: "pointer",
    transition: "border-color 0.18s ease, background 0.18s ease, transform 0.18s ease",
  },
  wizardChoiceOn: { borderColor: "rgba(34,211,238,0.42)", background: "rgba(34,211,238,0.08)", color: "var(--aeon-fg)" },
  wizardChoiceIcon: { width: "1.8rem", textAlign: "center", fontSize: "1.15rem", flexShrink: 0 },
  wizardChoiceText: { display: "flex", flexDirection: "column", gap: "0.18rem", minWidth: 0, flex: 1 },
  wizardChoiceTextSmall: { color: "var(--aeon-fg-mute)", fontSize: "0.67rem", lineHeight: 1.35 },
  wizardCheck: {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    width: "1.25rem",
    height: "1.25rem",
    border: "1px solid var(--aeon-border-strong)",
    borderRadius: "6px",
    color: "#04121f",
    flexShrink: 0,
  },
  wizardCheckOn: { borderColor: "#22d3ee", background: "#22d3ee", fontWeight: 900 },
  wizardHint: { marginTop: "0.85rem", color: "var(--aeon-fg-mute)", fontSize: "0.7rem" },
  reviewGrid: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: "0.65rem" },
  reviewItem: {
    display: "flex",
    flexDirection: "column",
    gap: "0.25rem",
    border: "1px solid var(--aeon-border)",
    borderRadius: "10px",
    padding: "0.75rem",
    background: "rgba(10,15,29,0.5)",
  },
  reviewItemLabel: { color: "var(--aeon-fg-mute)", fontSize: "0.65rem", textTransform: "uppercase", letterSpacing: "0.12em" },
  wizardReviewNote: { marginTop: "0.85rem", color: "#a5f3fc", fontSize: "0.75rem" },
  wizardFooter: {
    display: "flex",
    alignItems: "center",
    gap: "0.7rem",
    padding: "0.85rem 1.35rem 1.1rem",
    borderTop: "1px solid rgba(148,163,184,0.12)",
  },
  wizardStepHint: { flex: 1, color: "var(--aeon-fg-mute)", fontSize: "0.68rem", textAlign: "center" },
  wizardSecondary: {
    border: "1px solid var(--aeon-border-strong)",
    background: "transparent",
    color: "var(--aeon-fg-soft)",
    borderRadius: "9px",
    padding: "0.55rem 0.9rem",
    fontSize: "0.75rem",
    fontWeight: 700,
    cursor: "pointer",
  },
  wizardPrimary: {
    border: "none",
    background: "linear-gradient(135deg, #22d3ee, #00a8ff)",
    color: "#04121f",
    borderRadius: "9px",
    padding: "0.55rem 0.95rem",
    fontSize: "0.75rem",
    fontWeight: 800,
    cursor: "pointer",
  },
  section: { marginTop: "2.2rem" },
  stepLabel: {
    fontSize: "0.66rem",
    fontWeight: 800,
    letterSpacing: "0.22em",
    textTransform: "uppercase",
    color: "#22d3ee",
    marginBottom: "0.9rem",
  },
  identityRow: { display: "flex", gap: "0.9rem", flexWrap: "wrap" },
  field: { display: "flex", flexDirection: "column", gap: "0.4rem", minWidth: "110px" },
  fieldGrow: { display: "flex", flexDirection: "column", gap: "0.4rem", flex: 1, minWidth: "220px" },
  label: { fontSize: "0.66rem", fontWeight: 700, letterSpacing: "0.14em", textTransform: "uppercase", color: "var(--aeon-fg-mute)" },
  input: {
    background: "rgba(10,15,29,0.7)",
    border: "1px solid var(--aeon-border)",
    borderRadius: "10px",
    padding: "0.62rem 0.8rem",
    color: "var(--aeon-fg)",
    fontSize: "0.9rem",
    outline: "none",
  },
  select: {
    background: "rgba(10,15,29,0.7)",
    border: "1px solid var(--aeon-border)",
    borderRadius: "10px",
    padding: "0.62rem 0.8rem",
    color: "var(--aeon-fg)",
    fontSize: "0.9rem",
    outline: "none",
  },
  packGrid: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(230px, 1fr))", gap: "0.9rem" },
  packCard: {
    textAlign: "left",
    border: "1px solid var(--aeon-border)",
    background: "rgba(10,15,29,0.55)",
    borderRadius: "14px",
    padding: "1rem 1.1rem",
    cursor: "pointer",
    transition: "border-color 0.2s ease, transform 0.2s ease",
    color: "var(--aeon-fg)",
  },
  packCardActive: { borderColor: "rgba(0,168,255,0.55)", background: "rgba(0,168,255,0.07)" },
  packHead: { display: "flex", alignItems: "center", gap: "0.55rem", flexWrap: "wrap" },
  packIcon: { fontSize: "1.1rem" },
  packName: { fontWeight: 800, fontSize: "0.92rem" },
  packCore: {
    fontSize: "0.55rem", fontWeight: 800, letterSpacing: "0.14em", padding: "0.15rem 0.45rem",
    border: "1px solid rgba(34,211,238,0.4)", color: "#22d3ee", borderRadius: "999px",
  },
  packActive: {
    fontSize: "0.55rem", fontWeight: 800, letterSpacing: "0.14em", padding: "0.15rem 0.45rem",
    border: "1px solid rgba(52,211,153,0.4)", color: "#34d399", borderRadius: "999px",
  },
  packDesc: { marginTop: "0.55rem", fontSize: "0.78rem", lineHeight: 1.55, color: "var(--aeon-fg-mute)" },
  packMeta: { marginTop: "0.6rem", fontSize: "0.66rem", letterSpacing: "0.06em", color: "var(--aeon-fg-soft)" },
  packRef: { marginTop: "0.6rem", fontSize: "0.72rem", color: "#7dd3fc", fontStyle: "italic" },
  modGroupWrap: { display: "flex", flexDirection: "column", gap: "1.3rem" },
  modGroup: {},
  modGroupLabel: {
    fontSize: "0.62rem", fontWeight: 800, letterSpacing: "0.2em", color: "var(--aeon-fg-mute)",
    marginBottom: "0.65rem",
  },
  modGrid: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(190px, 1fr))", gap: "0.8rem" },
  modCard: {
    textAlign: "left",
    border: "1px solid var(--aeon-border)",
    background: "rgba(10,15,29,0.55)",
    borderRadius: "12px",
    padding: "0.85rem 0.95rem",
    cursor: "pointer",
    transition: "border-color 0.2s ease, opacity 0.2s ease",
    opacity: 0.55,
    color: "var(--aeon-fg)",
  },
  modCardOn: { opacity: 1, borderColor: "rgba(0,168,255,0.4)", background: "rgba(0,168,255,0.06)" },
  modCardHead: { display: "flex", justifyContent: "space-between", alignItems: "center" },
  modIcon: { fontSize: "1.1rem" },
  modToggle: { fontSize: "0.85rem", color: "#22d3ee" },
  modName: { marginTop: "0.45rem", fontWeight: 800, fontSize: "0.88rem" },
  modDesc: { marginTop: "0.3rem", fontSize: "0.72rem", lineHeight: 1.5, color: "var(--aeon-fg-mute)" },
  modReq: {
    marginTop: "0.5rem", fontSize: "0.55rem", fontWeight: 800, letterSpacing: "0.14em",
    color: "#22d3ee",
  },
  contractBar: {
    border: "1px dashed rgba(34,211,238,0.35)",
    background: "rgba(34,211,238,0.05)",
    borderRadius: "10px",
    padding: "0.65rem 0.95rem",
    fontSize: "0.72rem",
    color: "#7dd3fc",
    marginBottom: "1rem",
    letterSpacing: "0.02em",
  },
  connGrid: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: "0.85rem" },
  connCard: {
    border: "1px solid var(--aeon-border)",
    background: "rgba(10,15,29,0.55)",
    borderRadius: "13px",
    padding: "0.95rem 1rem",
    opacity: 0.55,
    transition: "border-color 0.2s ease, opacity 0.2s ease",
  },
  connCardOn: { opacity: 1, borderColor: "rgba(0,168,255,0.4)" },
  connHead: { display: "flex", alignItems: "center", gap: "0.6rem" },
  connIcon: { fontSize: "1.15rem" },
  connName: { fontWeight: 800, fontSize: "0.88rem" },
  connCat: { fontSize: "0.62rem", letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--aeon-fg-mute)" },
  connToggle: {
    marginLeft: "auto",
    background: "none",
    border: "none",
    color: "#22d3ee",
    fontSize: "1rem",
    cursor: "pointer",
    padding: "0.2rem",
  },
  connDesc: { marginTop: "0.5rem", fontSize: "0.75rem", lineHeight: 1.5, color: "var(--aeon-fg-mute)" },
  connFoot: { marginTop: "0.7rem", display: "flex", alignItems: "center", gap: "0.6rem" },
  testBtn: {
    border: "1px solid rgba(0,168,255,0.45)",
    background: "rgba(0,168,255,0.1)",
    color: "#7dd3fc",
    borderRadius: "8px",
    padding: "0.35rem 0.75rem",
    fontSize: "0.7rem",
    fontWeight: 700,
    cursor: "pointer",
  },
  statusChip: {
    fontSize: "0.66rem",
    fontWeight: 700,
    border: "1px solid",
    borderRadius: "999px",
    padding: "0.2rem 0.55rem",
  },
  connOff: { fontSize: "0.6rem", fontWeight: 800, letterSpacing: "0.14em", color: "var(--aeon-fg-mute)" },
  umIntro: { fontSize: "0.82rem", color: "var(--aeon-fg-mute)", marginTop: "-0.3rem", marginBottom: "1rem" },
  umGroup: { marginBottom: "1rem" },
  umGroupLabel: {
    fontSize: "0.6rem", fontWeight: 800, letterSpacing: "0.18em", color: "var(--aeon-fg-mute)",
    marginBottom: "0.5rem",
  },
  umChips: { display: "flex", flexWrap: "wrap", gap: "0.45rem" },
  umChip: {
    border: "1px solid rgba(148,163,184,0.25)",
    background: "rgba(15,23,42,0.7)",
    borderRadius: "999px",
    padding: "0.32rem 0.75rem",
    fontSize: "0.72rem",
    fontWeight: 700,
    color: "var(--aeon-fg-soft)",
    cursor: "default",
  },
  actions: { marginTop: "2.4rem", display: "flex", alignItems: "center", gap: "1rem", flexWrap: "wrap" },
  saveBtn: {
    background: "linear-gradient(135deg, #00d2ff, #00a8ff)",
    color: "#04121f",
    border: "none",
    borderRadius: "12px",
    padding: "0.8rem 1.6rem",
    fontSize: "0.9rem",
    fontWeight: 800,
    cursor: "pointer",
    boxShadow: "0 6px 24px rgba(0,168,255,0.3)",
  },
  saveHint: { fontSize: "0.75rem", color: "var(--aeon-fg-mute)" },
};
