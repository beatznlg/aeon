import { redirect } from "next/navigation";
import { auth } from "@/auth";
import { isModuleEnabled, isWorkspaceAdmin, ThemeConfig } from "@/lib/theme-config";
import AppPageClient from "./AppPageClient";

interface BrandingResponse {
  ok: boolean;
  workspace_id?: string;
  branding?: Partial<ThemeConfig>;
}

async function getWorkspaceBranding(workspaceId: string): Promise<Partial<ThemeConfig> | null> {
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

interface PageProps {
  params: Promise<{ appId: string }>;
}

export default async function AppPage({ params }: PageProps) {
  const { appId } = await params;
  const session = await auth();
  const user = session?.user as
    { id?: string; email?: string; role?: string; workspaceId?: string } | undefined;

  const role = user?.role;
  const workspaceId = user?.workspaceId;

  const branding = workspaceId ? await getWorkspaceBranding(workspaceId) : null;
  const enabled = isModuleEnabled(branding ?? undefined, appId, true);

  if (!enabled && !isWorkspaceAdmin(role)) {
    redirect("/os");
  }

  return <AppPageClient />;
}
