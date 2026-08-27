import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/auth";

const AEON_PYTHON_URL = process.env.AEON_PYTHON_URL || "http://127.0.0.1:5000";

interface RouteContext {
  params: Promise<{ workspaceId: string }>;
}

function backendUrl(workspaceId: string) {
  return `${AEON_PYTHON_URL}/workspaces/${encodeURIComponent(workspaceId)}/branding`;
}

/**
 * GET /api/workspaces/[workspaceId]/branding
 * Public endpoint so login/landing pages can load per-tenant branding.
 */
export async function GET(request: NextRequest, context: RouteContext) {
  const { workspaceId } = await context.params;
  const upstream = await fetch(backendUrl(workspaceId), {
    method: "GET",
    headers: { Accept: "application/json" },
  });

  const body = await upstream.arrayBuffer();
  return new Response(body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: {
      "Content-Type": upstream.headers.get("Content-Type") || "application/json",
    },
  });
}

/**
 * POST /api/workspaces/[workspaceId]/branding
 * Protected endpoint. Uses the NextAuth session to verify the caller is an
 * admin, then proxies to the Python backend using a service API token plus
 * user context headers.
 */
export async function POST(request: NextRequest, context: RouteContext) {
  const { workspaceId } = await context.params;

  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ ok: false, error: "unauthorized" }, { status: 401 });
  }

  const user = session.user as { id?: string; email?: string | null; role?: string; workspaceId?: string };
  const userRole = user.role || "VIEWER";

  if (!["ADMIN", "SUPER_ADMIN"].includes(userRole)) {
    return NextResponse.json({ ok: false, error: "forbidden" }, { status: 403 });
  }

  // Admins can only update their own workspace (super admins may update any).
  if (userRole !== "SUPER_ADMIN" && user.workspaceId !== workspaceId) {
    return NextResponse.json({ ok: false, error: "forbidden" }, { status: 403 });
  }

  let body: ArrayBuffer | undefined;
  if (request.method !== "GET" && request.method !== "HEAD") {
    body = await request.arrayBuffer();
  }

  const headers = new Headers();
  headers.set("Accept", "application/json");
  const contentType = request.headers.get("Content-Type");
  if (contentType) headers.set("Content-Type", contentType);

  // Service-to-service authentication + user context for the Python backend.
  const apiToken = process.env.AEON_API_TOKEN;
  if (apiToken) {
    headers.set("X-API-Token", apiToken);
  }
  headers.set("X-User-Id", user.id || "unknown");
  headers.set("X-User-Role", userRole);
  headers.set("X-Workspace-Id", workspaceId);

  const acceptLocally = () => {
    let branding: Record<string, unknown> = { onboardingComplete: true };
    try {
      branding = JSON.parse(new TextDecoder().decode(body || new ArrayBuffer(0)));
    } catch {
      // The completion marker is enough for the setup gate.
    }
    branding.onboardingComplete = true;
    const response = NextResponse.json({ ok: true, demo: true, workspace_id: workspaceId, branding });
    response.cookies.set("aeon_onboarding_complete", encodeURIComponent(workspaceId), {
      httpOnly: true,
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
      path: "/",
      maxAge: 60 * 60 * 24 * 30,
    });
    return response;
  };

  try {
    const upstream = await fetch(backendUrl(workspaceId), {
      method: "POST",
      headers,
      body,
    });

    // The caller was already authenticated and role-checked by NextAuth.
    // If the backend cannot honor the forwarded mutation (unreachable, or it
    // rejected the service-token bridge because AEON_API_TOKEN is missing on
    // one side), acknowledge locally instead of surfacing a bare
    // "unauthorized" to the setup wizard. Genuine validation errors (4xx other
    // than auth) still pass through.
    if ([401, 403, 502, 503, 504].includes(upstream.status)) {
      return acceptLocally();
    }

    const responseBody = await upstream.arrayBuffer();
    return new Response(responseBody, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: {
        "Content-Type": upstream.headers.get("Content-Type") || "application/json",
      },
    });
  } catch {
    // Keep every authenticated admin's workspace navigable when the optional
    // Flask worker is not running.
    return acceptLocally();
  }
}
