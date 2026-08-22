import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/auth";
import { requireRole } from "@/lib/auth";
import { proxyApiRequest } from "@/lib/proxy";

export const dynamic = "force-dynamic";

/**
 * Forward the browser's Flask JWT to the tenant-scoped operations
 * snapshot endpoint. The admin page uses this to display system health,
 * AI execution metrics, dead letters, and worker queue status.
 */
export async function GET(request: NextRequest) {
  try {
    requireRole(await auth(), ["ADMIN"]);
    return await proxyApiRequest(request, { backendPath: "/operations/snapshot" });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return NextResponse.json({ ok: false, error: message }, { status: 503 });
  }
}
