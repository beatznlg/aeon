"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { getAuthHeaders } from "@/lib/flask-auth";

type Profile = {
  id: string;
  name: string;
  description: string;
  audience: string;
  sectors: string[];
  organization_types: string[];
  deployment_modes: string[];
  data_classifications: string[];
  compliance_frameworks: string[];
  default_plugins: string[];
  recommended_capabilities: string[];
  approval_required_for: string[];
  notes: string[];
};

type CurrentProfile = {
  profile_id: string;
  sector: string;
  organization_type: string;
  deployment_mode: string;
  data_classification: string;
  profile?: Profile;
  effective?: {
    plugins: string[];
    capabilities: string[];
    approval_required_for: string[];
    compliance_frameworks: string[];
    notes: string[];
  };
};

const SECTORS = ["general", "government", "health", "finance", "manufacturing", "utilities", "education", "cybersecurity", "defense", "retail", "transport", "heritage", "professional"];
const ORG_TYPES = ["startup", "sme", "enterprise", "nonprofit", "university", "healthcare-provider", "financial-institution", "manufacturer", "utility", "municipality", "government-agency", "defense-contractor", "public-safety-agency"];
const DEPLOYMENTS = ["cloud", "hybrid", "on-premise", "air-gapped", "edge"];
const CLASSIFICATIONS = ["public", "internal", "confidential", "restricted", "secret"];

function label(value: string) {
  return value.replaceAll("-", " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

export default function OperatingProfilesPage() {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [current, setCurrent] = useState<CurrentProfile | null>(null);
  const [selectedId, setSelectedId] = useState("general-business");
  const [sector, setSector] = useState("general");
  const [organizationType, setOrganizationType] = useState("enterprise");
  const [deploymentMode, setDeploymentMode] = useState("cloud");
  const [classification, setClassification] = useState("internal");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const headers = getAuthHeaders();
      const [catalogResponse, currentResponse] = await Promise.all([
        fetch("/api/os/operating-profiles", { headers, cache: "no-store" }),
        fetch("/api/os/operating-profile", { headers, cache: "no-store" }),
      ]);
      const catalog = await catalogResponse.json();
      const active = await currentResponse.json();
      if (!catalogResponse.ok || !catalog.ok) throw new Error(catalog.error || "Unable to load operating profiles");
      if (!currentResponse.ok || !active.ok) throw new Error(active.error || "Unable to load workspace profile");
      setProfiles(catalog.profiles || []);
      setCurrent(active);
      setSelectedId(active.profile_id || "general-business");
      setSector(active.sector || "general");
      setOrganizationType(active.organization_type || "enterprise");
      setDeploymentMode(active.deployment_mode || "cloud");
      setClassification(active.data_classification || "internal");
    } catch (loadError) {
      setError(String(loadError));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return profiles.filter((profile) => {
      if (!normalized) return true;
      return `${profile.name} ${profile.description} ${profile.audience} ${profile.sectors.join(" ")}`.toLowerCase().includes(normalized);
    });
  }, [profiles, query]);

  const selected = profiles.find((profile) => profile.id === selectedId) || current?.profile;

  const save = async () => {
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const response = await fetch("/api/os/operating-profile", {
        method: "PUT",
        headers: getAuthHeaders(),
        body: JSON.stringify({
          profile_id: selectedId,
          sector,
          organization_type: organizationType,
          deployment_mode: deploymentMode,
          data_classification: classification,
        }),
      });
      const body = await response.json();
      if (!response.ok || !body.ok) throw new Error(body.error || "Profile selection failed");
      setCurrent(body);
      setMessage("Operating profile saved. Permissions and approvals remain governed by workspace policy.");
    } catch (saveError) {
      setError(String(saveError));
    } finally {
      setSaving(false);
    }
  };

  return (
    <main className="module-page" style={{ maxWidth: 1240, margin: "0 auto", padding: "32px 24px" }}>
      <header className="module-page-header">
        <div className="eyebrow">ADAPTIVE OPERATING FABRIC</div>
        <h1 className="module-title">Operating Profiles</h1>
        <p className="module-subtitle">Configure AEON for a company, sector, or government deployment without changing the core platform.</p>
      </header>

      {error && <div className="notice notice-error" style={{ marginTop: 20 }}>{error}</div>}
      {message && <div className="notice" style={{ marginTop: 20 }}>{message}</div>}

      <section className="module-widget" style={{ marginTop: 24 }}>
        <div className="eyebrow">WORKSPACE CONTEXT</div>
        <h2 style={{ margin: "8px 0 4px" }}>Governed selection</h2>
        <p className="text-muted" style={{ margin: 0 }}>Profiles recommend plugins and controls; they do not grant permissions or certify compliance.</p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12, marginTop: 18 }}>
          <label className="input-label">Profile<select className="input" value={selectedId} onChange={(event) => setSelectedId(event.target.value)}>{profiles.map((profile) => <option key={profile.id} value={profile.id}>{profile.name}</option>)}</select></label>
          <label className="input-label">Sector<select className="input" value={sector} onChange={(event) => setSector(event.target.value)}>{SECTORS.map((value) => <option key={value} value={value}>{label(value)}</option>)}</select></label>
          <label className="input-label">Organization type<select className="input" value={organizationType} onChange={(event) => setOrganizationType(event.target.value)}>{ORG_TYPES.map((value) => <option key={value} value={value}>{label(value)}</option>)}</select></label>
          <label className="input-label">Deployment<select className="input" value={deploymentMode} onChange={(event) => setDeploymentMode(event.target.value)}>{DEPLOYMENTS.map((value) => <option key={value} value={value}>{label(value)}</option>)}</select></label>
          <label className="input-label">Data classification<select className="input" value={classification} onChange={(event) => setClassification(event.target.value)}>{CLASSIFICATIONS.map((value) => <option key={value} value={value}>{label(value)}</option>)}</select></label>
        </div>
        <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 16 }}><button className="btn btn-primary" onClick={save} disabled={saving || loading}>{saving ? "Saving…" : "Apply workspace profile"}</button></div>
      </section>

      {current?.effective && <section className="module-widgets-grid" style={{ marginTop: 20 }}>
        <div className="module-widget"><div className="eyebrow">ACTIVE PROFILE</div><div className="stat-value" style={{ marginTop: 8 }}>{label(current.profile_id)}</div><div className="stat-label">{label(current.deployment_mode)} deployment · {label(current.data_classification)} data</div></div>
        <div className="module-widget"><div className="eyebrow">RECOMMENDED PLUGINS</div><div className="stat-value" style={{ marginTop: 8 }}>{current.effective.plugins.length}</div><div className="stat-label">Available as governed recommendations</div></div>
        <div className="module-widget"><div className="eyebrow">APPROVAL GATES</div><div className="stat-value" style={{ marginTop: 8 }}>{current.effective.approval_required_for.length}</div><div className="stat-label">Human review areas</div></div>
      </section>}

      <section style={{ marginTop: 28 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", flexWrap: "wrap", marginBottom: 14 }}><div><div className="eyebrow">PROFILE CATALOG</div><h2 style={{ margin: "8px 0 0" }}>Built for every operating environment</h2></div><input className="input" placeholder="Search profiles…" value={query} onChange={(event) => setQuery(event.target.value)} style={{ maxWidth: 280 }} /></div>
        {loading ? <div className="module-widget">Loading profile catalog…</div> : <div className="module-widgets-grid">{filtered.map((profile) => <button key={profile.id} className="module-widget" onClick={() => setSelectedId(profile.id)} style={{ textAlign: "left", cursor: "pointer", border: selectedId === profile.id ? "1px solid var(--aeon-primary)" : undefined }}><div style={{ display: "flex", justifyContent: "space-between", gap: 10, alignItems: "center" }}><span className="badge">{label(profile.audience)}</span><span className="text-muted" style={{ fontSize: 12 }}>{profile.id}</span></div><h3 style={{ margin: "14px 0 8px" }}>{profile.name}</h3><p className="text-muted" style={{ minHeight: 44, margin: 0 }}>{profile.description}</p><div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 14 }}>{profile.compliance_frameworks.slice(0, 4).map((framework) => <span className="badge" key={framework}>{framework}</span>)}</div><div className="text-muted" style={{ fontSize: 12, marginTop: 12 }}>{profile.default_plugins.length} plugins · {profile.approval_required_for.length} approval gates</div></button>)}</div>}
      </section>

      {selected && <section className="module-widget" style={{ marginTop: 22 }}><div className="eyebrow">SELECTED PROFILE DETAILS</div><h2 style={{ margin: "8px 0" }}>{selected.name}</h2><p className="text-muted">{selected.description}</p><div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 16, marginTop: 16 }}><div><strong>Supported deployments</strong><div className="text-muted" style={{ marginTop: 6 }}>{selected.deployment_modes.map(label).join(" · ")}</div></div><div><strong>Data classifications</strong><div className="text-muted" style={{ marginTop: 6 }}>{selected.data_classifications.map(label).join(" · ")}</div></div><div><strong>Approval areas</strong><div className="text-muted" style={{ marginTop: 6 }}>{selected.approval_required_for.map(label).join(" · ") || "None declared"}</div></div></div>{selected.notes.length > 0 && <div className="notice" style={{ marginTop: 16 }}>{selected.notes.join(" ")}</div>}</section>}
    </main>
  );
}
