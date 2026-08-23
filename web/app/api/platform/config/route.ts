import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/auth";
import { demoPlatformConfig } from "@/lib/demo-data";
import { getAuthHeaders } from "@/lib/flask-auth";

export const dynamic = "force-dynamic";

const PYTHON_URL = process.env.AEON_PYTHON_URL || "http://127.0.0.1:5000";

function forwardHeaders(workspaceId: string, user: { id?: string; role?: string }) {
  const headers = new Headers({ Accept: "application/json", "Content-Type": "application/json" });
  const apiToken = process.env.AEON_API_TOKEN;
  if (apiToken) headers.set("X-API-Token", apiToken);
  headers.set("X-User-Id", user.id || "unknown");
  headers.set("X-User-Role", user.role || "VIEWER");
  headers.set("X-Workspace-Id", workspaceId);
  return headers;
}

export async function GET() {
  const session = await auth();
  const user = session?.user as { id?: string; email?: string | null; role?: string; workspaceId?: string } | undefined;
  try {
    const headers = user?.workspaceId
      ? forwardHeaders(user.workspaceId, user)
      : getAuthHeaders();
    const res = await fetch(`${PYTHON_URL}/platform/config`, {
      headers,
      cache: "no-store",
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json(demoPlatformConfig);
  }
}

export async function PUT(request: NextRequest) {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ ok: false, error: "unauthorized" }, { status: 401 });
  }

  const user = session.user as { id?: string; email?: string | null; role?: string; workspaceId?: string };
  const role = user.role || "VIEWER";
  const workspaceId = user.workspaceId;
  if (!workspaceId) {
    return NextResponse.json({ ok: false, error: "workspace not selected" }, { status: 400 });
  }
  if (!["ADMIN", "SUPER_ADMIN"].includes(role)) {
    return NextResponse.json({ ok: false, error: "forbidden" }, { status: 403 });
  }

  const body = await request.arrayBuffer();
  try {
    const upstream = await fetch(`${PYTHON_URL}/platform/config`, {
      method: "PUT",
      headers: forwardHeaders(workspaceId, user),
      body,
      cache: "no-store",
    });
    const responseBody = await upstream.arrayBuffer();
    return new Response(responseBody, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: { "Content-Type": upstream.headers.get("Content-Type") || "application/json" },
    });
  } catch {
    if (workspaceId === "demo-workspace" || user.email === "admin@demo.local") {
      let payload: Record<string, unknown> = {};
      try {
        payload = JSON.parse(new TextDecoder().decode(body));
      } catch {
        // The demo fallback only needs to acknowledge the setup mutation.
      }
      return NextResponse.json({
        ...demoPlatformConfig,
        demo: true,
        config: { ...demoPlatformConfig.config, ...payload, tenant_id: workspaceId },
      });
    }
    return NextResponse.json({ ok: false, error: "platform backend unavailable" }, { status: 503 });
  }
}
