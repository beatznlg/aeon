import { NextRequest, NextResponse } from "next/server";
import { withBackendSessionHeaders } from "@/lib/backend-session";

const AEON_URL = process.env.AEON_PYTHON_URL || "http://127.0.0.1:5000";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  try {
    const headers: Record<string, string> = { Accept: "application/json" };
    await withBackendSessionHeaders(headers);

    const query = req.nextUrl.searchParams.toString();
    const res = await fetch(`${AEON_URL}/llm/models${query ? `?${query}` : ""}`, {
      headers,
      cache: "no-store",
    });
    const data = await res.json();
    return NextResponse.json(data, {
      status: res.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return NextResponse.json(
      { ok: false, models: [], status: "unavailable", source: "provider_api" },
      { status: 502, headers: { "Cache-Control": "no-store" } },
    );
  }
}
