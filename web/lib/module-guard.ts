import { redirect } from "next/navigation";
import { auth } from "@/auth";
import { isModuleEnabled, isWorkspaceAdmin, ThemeConfig } from "./theme-config";

export interface GuardResult {
  allowed: boolean;
  workspaceId?: string;
  branding: Partial<ThemeConfig> | null;
}

interface BrandingResponse {
  ok: boolean;
  workspace_id?: string;
  branding?: Partial<ThemeConfig>;
}

async function fetchWorkspaceBranding(workspaceId: string): Promise<Partial<ThemeConfig> | null> {
  try {
    const backendUrl = process.env.AEON_PYTHON_URL || "http://127.0.0.1:5000";
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 2000);
    const res = await fetch(
      `${backendUrl}/workspaces/${encodeURIComponent(workspaceId)}/branding`,
      {
        cache: "no-store",
        signal: controller.signal,
      }
    );
    clearTimeout(timeout);
    if (!res.ok) return null;
    const data = (await res.json()) as BrandingResponse;
    return data.branding || null;
  } catch {
    return null;
  }
}

/**
 * Server-side guard for module routes.
 * Redirects non-admin users to fallbackPath when the module is disabled.
 * Returns the session, workspaceId and branding for optional use by the page.
 */
export async function guardModuleRoute(
  moduleId: string,
  fallbackPath = "/os"
): Promise<GuardResult> {
  const session = await auth();
  const user = session?.user as
    { id?: string; email?: string; role?: string; workspaceId?: string } | undefined;

  const workspaceId = user?.workspaceId;
  const role = user?.role;

  const branding = workspaceId ? await fetchWorkspaceBranding(workspaceId) : null;
  const enabled = isModuleEnabled(branding ?? undefined, moduleId, true);

  if (!enabled && !isWorkspaceAdmin(role)) {
    redirect(fallbackPath);
  }

  return { allowed: true, workspaceId, branding };
}
