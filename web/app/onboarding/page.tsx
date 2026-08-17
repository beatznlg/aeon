"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { INDUSTRY_PRESETS, IndustryPreset } from "@/lib/industry-presets";
import { defaultThemeConfig, BrandModule } from "@/lib/theme-config";
import { getDefaultEnabledIds } from "@/lib/dashboard-registry";
import { FadeIn, StaggerContainer, StaggerItem, ScaleOnHover } from "@/components/animations";

export default function OnboardingPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const workspaceId = (session?.user as any)?.workspaceId as string | undefined;
  const [applying, setApplying] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

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

    const modules: BrandModule[] = defaultThemeConfig.modules.map((m) => ({
      id: m.id,
      label: m.label,
      icon: m.icon,
      enabled: preset.moduleIds.includes(m.id),
    }));

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
      const res = await fetch(`/api/workspaces/${encodeURIComponent(workspaceId)}/branding`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || `Save failed (${res.status})`);
      }
      setSuccess(`${preset.name} configured for ${preset.companyName}.`);
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
            Pick the sector you operate in — AEON OS will enable the right command centers,
            tools, and branding for your organization. You can fine-tune everything later in
            Settings → Branding.
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
          return (
            <StaggerItem key={preset.id}>
              <ScaleOnHover>
                <button
                  type="button"
                  onClick={() => applyPreset(preset)}
                  disabled={!!applying}
                  className="os-card w-full text-left cursor-pointer"
                  style={{ borderTopColor: preset.color, height: "100%" }}
                >
                  <div className="os-card-header">
                    <span
                      className="os-icon"
                      style={{ background: `${preset.color}20`, fontSize: "1.5rem" }}
                    >
                      {preset.icon}
                    </span>
                    <span className="os-status-pill active" style={{ color: preset.color }}>
                      {preset.moduleIds.length} modules
                    </span>
                  </div>
                  <h3>{preset.name}</h3>
                  <p className="os-category" style={{ color: preset.color }}>
                    {preset.companyName}
                  </p>
                  <p className="os-desc">{preset.description}</p>
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
