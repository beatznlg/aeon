/**
 * Server-only helper: map the NextAuth session onto the AEON Flask backend's
 * user-context headers.
 *
 * The Flask backend (`aeon_auth.require_auth`) authenticates requests via:
 *   1. `Authorization: Bearer <flask-jwt>` (issued by `/auth/login`)
 *   2. `X-API-Token` (service accounts; preserves X-User-* identity)
 *   3. `X-User-Id` / `X-User-Email` / `X-User-Role` / `X-Workspace-Id`
 *      (development header fallback; honored in production only when a valid
 *      X-API-Token accompanies it)
 *
 * NextAuth issues its own session JWT that Flask cannot decode, so every
 * Next.js API route that forwards to the Python backend must attach these
 * X-User-* headers to carry the authenticated identity across the bridge.
 */

import { auth } from "@/auth";

export interface BackendSessionUser {
  id?: string;
  email?: string | null;
  role?: string;
  workspaceId?: string;
}

/**
 * Return the backend user-context headers for the current NextAuth session.
 * Empty object when there is no session or auth() is unavailable.
 */
export async function backendSessionHeaders(): Promise<Record<string, string>> {
  try {
    const session = await auth();
    const user = session?.user as BackendSessionUser | undefined;
    if (!user?.id) return {};
    const headers: Record<string, string> = {};
    headers["X-User-Id"] = user.id;
    if (user.email) headers["X-User-Email"] = user.email;
    if (user.role) headers["X-User-Role"] = user.role;
    if (user.workspaceId) headers["X-Workspace-Id"] = user.workspaceId;
    return headers;
  } catch {
    // Middleware/edge contexts without a full session — proxy unauthenticated.
    return {};
  }
}

/**
 * Merge the session headers into an existing plain headers object (mutates and
 * returns it). Call inside route handlers after building their base headers.
 */
export async function withBackendSessionHeaders(
  headers: Record<string, string>
): Promise<Record<string, string>> {
  const sessionHeaders = await backendSessionHeaders();
  for (const [key, value] of Object.entries(sessionHeaders)) {
    if (!headers[key]) headers[key] = value;
  }
  return headers;
}
