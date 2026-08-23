import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/auth";

export const dynamic = "force-dynamic";

const PYTHON_URL = (process.env.AEON_PYTHON_URL || "http://127.0.0.1:5000").replace(/\/$/, "");
const SETUP_COOKIE = "aeon_onboarding_complete";

function backendHeaders(user: { id?: string; email?: string; role?: string; workspaceId?: string }) {
  const headers = new Headers({ Accept: "application/json" });
  const apiToken = process.env.AEON_API_TOKEN;
  if (apiToken) headers.set("X-API-Token", apiToken);
  if (user.id) headers.set("X-User-Id", user.id);
  if (user.email) headers.set("X-User-Email", user.email);
  if (user.role) headers.set("X-User-Role", user.role);
  if (user.workspaceId) headers.set("X-Workspace-Id", user.workspaceId);
  return headers;
}

async function getStatus() {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ ok: false, error: "unauthorized" }, { status: 401 });
  }

  const user = session.user as { id?: string; email?: string; role?: string; workspaceId?: string };
  const workspaceId = user.workspaceId;
  if (!workspaceId) {
    return NextResponse.json({ ok: true, complete: false, needsSetup: true, workspaceId: null });
  }

  const cookieStore = await cookies();
  const cookieValue = cookieStore.get(SETUP_COOKIE)?.value || "";
  const cookieComplete = cookieValue === encodeURIComponent(workspaceId);
  let platformConfigured = false;
  let brandingConfigured = false;

  try {
    const [platformResponse, brandingResponse] = await Promise.all([
      fetch(`${PYTHON_URL}/platform/config`, {
        headers: backendHeaders(user),
        cache: "no-store",
      }),
      fetch(`${PYTHON_URL}/workspaces/${encodeURIComponent(workspaceId)}/branding`, {
        headers: backendHeaders(user),
        cache: "no-store",
      }),
    ]);

    if (platformResponse.ok) {
      const platform = await platformResponse.json();
      platformConfigured = Boolean(platform?.ok && platform?.config?.company);
    }
    if (brandingResponse.ok) {
      const branding = await brandingResponse.json();
      brandingConfigured = Boolean(branding?.branding?.onboardingComplete);
    }
  } catch {
    // A prior setup cookie keeps demo/frontend-only mode usable while Flask is
    // unavailable. Real workspace config remains the source of truth otherwise.
  }

  const complete = cookieComplete || (platformConfigured && brandingConfigured);
  return NextResponse.json({
    ok: true,
    complete,
    needsSetup: !complete,
    workspaceId,
    source: cookieComplete ? "setup-cookie" : "workspace-config",
  });
}

export async function GET() {
  return getStatus();
}

export async function POST(_request: NextRequest) {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ ok: false, error: "unauthorized" }, { status: 401 });
  }

  const workspaceId = (session.user as { workspaceId?: string }).workspaceId;
  if (!workspaceId) {
    return NextResponse.json({ ok: false, error: "workspace not selected" }, { status: 400 });
  }

  const cookieStore = await cookies();
  cookieStore.set(SETUP_COOKIE, encodeURIComponent(workspaceId), {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 24 * 30,
  });
  return NextResponse.json({ ok: true, complete: true });
}
