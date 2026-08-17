"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import Image from "next/image";
import Link from "next/link";
import { defaultThemeConfig, BrandModule, ThemeConfig } from "@/lib/theme-config";
import DashboardEditor from "@/components/DashboardEditor";
import { getDefaultEnabledIds } from "@/lib/dashboard-registry";

function isAdmin(role?: string) {
  return role === "ADMIN" || role === "SUPER_ADMIN";
}

export default function BrandingSettingsPage() {
  const { data: session, status } = useSession();
  const user = session?.user as
    { id?: string; email?: string; role?: string; workspaceId?: string } | undefined;
  const workspaceId = user?.workspaceId;

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [companyName, setCompanyName] = useState("");
  const [productName, setProductName] = useState("");
  const [tagline, setTagline] = useState("");
  const [primaryColor, setPrimaryColor] = useState("");
  const [logoUrl, setLogoUrl] = useState("");
  const [modules, setModules] = useState<BrandModule[]>([]);
  const [dashboardComponents, setDashboardComponents] = useState<string[]>(() =>
    getDefaultEnabledIds()
  );

  useEffect(() => {
    if (status === "loading") return;
    if (!workspaceId) {
      setLoading(false);
      return;
    }

    fetch(`/api/workspaces/${encodeURIComponent(workspaceId)}/branding`, {
      cache: "no-store",
    })
      .then(async (res) => {
        if (!res.ok) throw new Error(`Failed to load branding (${res.status})`);
        const data = await res.json();
        const branding = (data.branding ?? {}) as Partial<ThemeConfig>;

        setCompanyName(branding.companyName ?? defaultThemeConfig.companyName);
        setProductName(branding.productName ?? defaultThemeConfig.productName);
        setTagline(branding.tagline ?? defaultThemeConfig.tagline);
        setPrimaryColor(branding.primaryColor ?? defaultThemeConfig.primaryColor);
        setLogoUrl(branding.logoUrl ?? "");
        setDashboardComponents(branding.dashboardComponents ?? getDefaultEnabledIds());

        const incomingModules = branding.modules ?? [];
        const merged = defaultThemeConfig.modules.map((defaultMod) => {
          const found = incomingModules.find((m) => m.id === defaultMod.id);
          return found ? { ...defaultMod, ...found } : defaultMod;
        });
        // Keep any custom modules that are not in the defaults.
        const custom = incomingModules.filter(
          (m) => !defaultThemeConfig.modules.some((d) => d.id === m.id)
        );
        setModules([...merged, ...custom]);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => setLoading(false));
  }, [status, workspaceId]);

  const toggleModule = (id: string) => {
    setModules((prev) => prev.map((m) => (m.id === id ? { ...m, enabled: !m.enabled } : m)));
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!workspaceId) return;

    setSaving(true);
    setError(null);
    setSuccess(null);

    const payload: Partial<ThemeConfig> = {
      companyName: companyName.trim() || defaultThemeConfig.companyName,
      productName: productName.trim() || defaultThemeConfig.productName,
      tagline: tagline.trim() || defaultThemeConfig.tagline,
      primaryColor: primaryColor.trim() || defaultThemeConfig.primaryColor,
      logoUrl: logoUrl.trim() || undefined,
      dashboardComponents,
      modules,
    };

    try {
      const res = await fetch(`/api/workspaces/${encodeURIComponent(workspaceId)}/branding`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || `Save failed (${res.status})`);
      }
      setSuccess("Branding saved successfully.");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  if (status === "loading" || loading) {
    return (
      <div className="settings-page">
        <p className="text-aeon-fg-mute">Loading branding settings…</p>
      </div>
    );
  }

  if (!isAdmin(user?.role)) {
    return (
      <div className="settings-page">
        <h1>🎨 Workspace Branding</h1>
        <div className="settings-section">
          <p className="text-aeon-fg-mute">You must be a workspace admin to edit branding.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="settings-page">        <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1>🎨 Workspace Branding</h1>
          <p>Customize AEON OS for your company or organization.</p>
        </div>
        <div className="flex items-center gap-2">
          <Link href="/onboarding" className="btn btn-sm">
            🎯 Industry presets
          </Link>
          <Link href="/settings" className="btn btn-sm">
            ← Back to Settings
          </Link>
        </div>
      </div>

      {error && (
        <div className="settings-section" style={{ borderColor: "var(--danger)" }}>
          <p style={{ color: "var(--danger)" }}>⚠ {error}</p>
        </div>
      )}
      {success && (
        <div className="settings-section" style={{ borderColor: "var(--success)" }}>
          <p style={{ color: "var(--success)" }}>✓ {success}</p>
        </div>
      )}

      <form onSubmit={handleSave}>
        {/* Identity */}
        <div className="settings-section">
          <div className="settings-section-header">
            <span style={{ fontSize: "1.2rem" }}>🏢</span>
            <div>
              <h2>Identity</h2>
              <p>Company and product names shown throughout the UI</p>
            </div>
          </div>
          <div className="settings-item" style={{ display: "block" }}>
            <label className="settings-item-label" htmlFor="companyName">
              Company Name
            </label>
            <input
              id="companyName"
              className="input"
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              placeholder="Acme Corp"
              required
            />
          </div>
          <div className="settings-item" style={{ display: "block" }}>
            <label className="settings-item-label" htmlFor="productName">
              Product Name
            </label>
            <input
              id="productName"
              className="input"
              value={productName}
              onChange={(e) => setProductName(e.target.value)}
              placeholder="Acme OS"
              required
            />
          </div>
          <div className="settings-item" style={{ display: "block" }}>
            <label className="settings-item-label" htmlFor="tagline">
              Tagline
            </label>
            <input
              id="tagline"
              className="input"
              value={tagline}
              onChange={(e) => setTagline(e.target.value)}
              placeholder="Intelligence at work"
            />
          </div>
        </div>

        {/* Visuals */}
        <div className="settings-section">
          <div className="settings-section-header">
            <span style={{ fontSize: "1.2rem" }}>🎨</span>
            <div>
              <h2>Visuals</h2>
              <p>Logo and primary brand color</p>
            </div>
          </div>
          <div className="settings-item" style={{ display: "block" }}>
            <label className="settings-item-label" htmlFor="primaryColor">
              Primary Color
            </label>
            <div className="flex items-center gap-3">
              <input
                id="primaryColor"
                type="color"
                value={primaryColor}
                onChange={(e) => setPrimaryColor(e.target.value)}
                style={{ width: 48, height: 36, border: "none", padding: 0 }}
              />
              <input
                className="input"
                value={primaryColor}
                onChange={(e) => setPrimaryColor(e.target.value)}
                placeholder="#6366f1"
                pattern="^#[0-9A-Fa-f]{6}$"
                required
              />
            </div>
          </div>
          <div className="settings-item" style={{ display: "block" }}>
            <label className="settings-item-label" htmlFor="logoUrl">
              Logo URL
            </label>
            <input
              id="logoUrl"
              className="input"
              value={logoUrl}
              onChange={(e) => setLogoUrl(e.target.value)}
              placeholder="https://example.com/logo.svg"
              type="url"
            />
            <div className="settings-item-desc">Leave blank to use the default AEON glyph.</div>
          </div>
          {logoUrl && (
            <div className="settings-item">
              <div>
                <div className="settings-item-label">Logo preview</div>
              </div>
              <Image
                src={logoUrl}
                alt="Logo preview"
                unoptimized
                width={160}
                height={40}
                style={{
                  height: 40,
                  maxWidth: 160,
                  objectFit: "contain",
                  filter: "drop-shadow(0 0 2px rgba(0,0,0,0.2))",
                }}
              />
            </div>
          )}
        </div>

        {/* Modules */}
        <div className="settings-section">
          <div className="settings-section-header">
            <span style={{ fontSize: "1.2rem" }}>⊞</span>
            <div>
              <h2>Modules</h2>
              <p>Toggle features available to users in this workspace</p>
            </div>
          </div>
          {modules.length === 0 ? (
            <div className="settings-item">
              <div className="settings-item-label">No modules configured</div>
            </div>
          ) : (
            modules.map((mod) => (
              <div key={mod.id} className="settings-item">
                <div className="flex items-center gap-3">
                  <span>{mod.icon}</span>
                  <div>
                    <div className="settings-item-label">{mod.label}</div>
                    <div className="settings-item-desc">ID: {mod.id}</div>
                  </div>
                </div>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={mod.enabled}
                    onChange={() => toggleModule(mod.id)}
                  />
                  <span className="settings-item-desc">Enabled</span>
                </label>
              </div>
            ))
          )}
        </div>

        {/* Dashboard Components */}
        <div className="settings-section">
          <div className="settings-section-header">
            <span style={{ fontSize: "1.2rem" }}>📋</span>
            <div>
              <h2>Dashboard Components</h2>
              <p>
                Toggle which widgets appear on the main dashboard. Changes apply to all workspace
                members.
              </p>
            </div>
          </div>
          <DashboardEditor
            enabledComponents={dashboardComponents}
            onChange={setDashboardComponents}
            role={user?.role}
          />
        </div>

        {/* Actions */}
        <div className="settings-section" style={{ border: "none" }}>
          <div className="flex items-center gap-3">
            <button type="submit" className="btn btn-primary" disabled={saving}>
              {saving ? "Saving…" : "Save Branding"}
            </button>
            <Link href="/settings" className="btn">
              Cancel
            </Link>
          </div>
        </div>
      </form>
    </div>
  );
}
