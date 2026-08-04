import { NextRequest, NextResponse } from "next/server";
import { proxyApiRequest } from "@/lib/proxy";

export const dynamic = "force-dynamic";

/**
 * Forward the browser's existing Flask JWT to the tenant-scoped operations
 * snapshot endpoint. The proxy keeps the Python backend URL server-side and
 * lets Flask enforce workspace membership and viewer access.
 */
export async function GET(request: NextRequest) {
  try {
    return await proxyApiRequest(request, { backendPath: "/operations/snapshot" });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return NextResponse.json({ ok: false, error: message }, { status: 503 });
  }
}
