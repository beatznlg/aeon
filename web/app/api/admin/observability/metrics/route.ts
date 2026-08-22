import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/auth";
import { requireRole } from "@/lib/auth";
import { proxyApiRequest } from "@/lib/proxy";

export const dynamic = "force-dynamic";

/**
 * Forward to the backend /metrics endpoint with format=json to get
 * usage summary data for the admin observability dashboard.
 */
export async function GET(request: NextRequest) {
  try {
    requireRole(await auth(), ["ADMIN"]);
    // Append format=json to the backend request
    const url = new URL(request.url);
    url.searchParams.set("format", "json");

    // Create a modified request with the format=json param
    const modifiedRequest = new NextRequest(url.toString(), {
      method: request.method,
      headers: request.headers,
    });

    return await proxyApiRequest(modifiedRequest, { backendPath: "/metrics" });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return NextResponse.json({ ok: false, error: message }, { status: 503 });
  }
}
