import { NextRequest, NextResponse } from "next/server";
import { proxyApiRequest } from "@/lib/proxy";

export const dynamic = "force-dynamic";

/**
 * Proxy the browser's Flask JWT to the workspace-scoped incident API. The
 * backend remains responsible for authentication and workspace membership.
 */
export async function GET(request: NextRequest) {
  try {
    return await proxyApiRequest(request, { backendPath: "/incidents" });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return NextResponse.json({ ok: false, error: message }, { status: 503 });
  }
}
