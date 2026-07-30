import type { Metadata } from "next";
import "./globals.css";
import { auth } from "@/auth";
import Providers from "@/components/Providers";
import AppSidebar from "@/components/AppSidebar";
import { ThemeConfig } from "@/lib/theme-config";

export const metadata: Metadata = {
  title: "AEON OS — Enterprise AI Operating System",
  description:
    "AEON OS: Autonomous AI operating system for government and enterprise.",
};

interface Health {
  ok: boolean;
  backend?: string;
}

interface BrandingResponse {
  ok: boolean;
  workspace_id?: string;
  branding?: Partial<ThemeConfig>;
}

async function getHealth(): Promise<Health | null> {
  try {
    const res = await fetch("/api/health", { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as Health;
  } catch {
    return null;
  }
}

async function getWorkspaceBranding(workspaceId: string): Promise<Partial<ThemeConfig> | null> {
  try {
    const backendUrl = process.env.AEON_PYTHON_URL || "http://127.0.0.1:5000";
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 2000);
    const res = await fetch(`${backendUrl}/workspaces/${encodeURIComponent(workspaceId)}/branding`, {
      cache: "no-store",
      signal: controller.signal,
    });
    clearTimeout(timeout);
    if (!res.ok) return null;
    const data = (await res.json()) as BrandingResponse;
    return data.branding || null;
  } catch {
    return null;
  }
}

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const health = await getHealth();
  const session = await auth();
  const workspaceId = session?.user?.workspaceId as string | undefined;
  const branding = workspaceId ? await getWorkspaceBranding(workspaceId) : null;

  return (
    <html lang="en">
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </head>
      <body>
        <Providers sidebar={<AppSidebar health={health} branding={branding ?? undefined} userRole={(session?.user as any)?.role} />} initialConfig={branding ?? undefined}>
          {children}
        </Providers>
      </body>
    </html>
  );
}
