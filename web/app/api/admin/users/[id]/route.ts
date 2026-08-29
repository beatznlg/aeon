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
 * Update a user's role or profile — proxied to the Flask backend
 * (PATCH /admin/users/:id, PostgreSQL-backed).
 */
export async function PATCH(req: NextRequest, context: { params: Promise<{ id: string }> }) {
  const gate = await requirePlatformAdmin();
  if (gate.error) return gate.error;
  const { id } = await context.params;
  return backendFetch(req, `/admin/users/${id}`, { method: "PATCH" });
}

/**
 * Reset a user's password — POST /admin/users/:id/password on the backend.
 * Body: { password } (min 6 chars, hashed server-side with werkzeug).
 */
export async function POST(req: NextRequest, context: { params: Promise<{ id: string }> }) {
  const gate = await requirePlatformAdmin();
  if (gate.error) return gate.error;
  const { id } = await context.params;
  return backendFetch(req, `/admin/users/${id}/password`, { method: "POST" });
}

/**
 * Delete a user and their memberships — proxied to the Flask backend
 * (DELETE /admin/users/:id).
 */
export async function DELETE(req: NextRequest, context: { params: Promise<{ id: string }> }) {
  const gate = await requirePlatformAdmin();
  if (gate.error) return gate.error;
  const { id } = await context.params;
  return backendFetch(req, `/admin/users/${id}`, { method: "DELETE" });
}
