import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/auth";
import { isAdminRole } from "@/lib/auth";
import { backendFetch } from "@/lib/backend-fetch";

export const dynamic = "force-dynamic";

async function requirePlatformAdmin() {
  const session = await auth();
  if (!session?.user) {
    return { error: NextResponse.json({ ok: false, error: "unauthorized" }, { status: 401 }) };
  }
  if (!isAdminRole((session.user as any)?.role)) {
    return { error: NextResponse.json({ ok: false, error: "forbidden" }, { status: 403 }) };
  }
  return { session };
}

/**
 * Platform admin user list — proxies to the Flask backend's /admin/users
 * (PostgreSQL-backed, super-admin gated). backendFetch carries the auth
 * bridge (X-API-Token + X-User-* identity headers) and the demo fallback.
 */
export async function GET(req: NextRequest) {
  const gate = await requirePlatformAdmin();
  if (gate.error) return gate.error;
  return backendFetch(req, "/admin/users");
}

/**
 * Create a user with an explicit role (OWNER/SUPER_ADMIN/ADMIN/OPERATOR/VIEWER).
 * Body: { email, password, name?, role? } — proxied to the backend unchanged.
 */
export async function POST(req: NextRequest) {
  const gate = await requirePlatformAdmin();
  if (gate.error) return gate.error;
  return backendFetch(req, "/admin/users", { method: "POST" });
}
