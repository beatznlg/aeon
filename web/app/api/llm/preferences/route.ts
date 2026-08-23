import { NextRequest, NextResponse } from "next/server";
import { withBackendSessionHeaders } from "@/lib/backend-session";

const AEON_URL = process.env.AEON_PYTHON_URL || "http://127.0.0.1:5000";

export const dynamic = "force-dynamic";

async function backendHeaders(): Promise<Record<string, string>> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  await withBackendSessionHeaders(headers);
  return headers;
}

export async function GET() {
  try {
    const res = await fetch(`${AEON_URL}/llm/preferences`, {
      headers: await backendHeaders(),
      cache: "no-store",
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status, headers: { "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json(
      { ok: true, preference: { provider: process.env.AEON_LLM_PROVIDER || "stub", model: process.env.AEON_LLM_MODEL || null, source: "environment" } },
      { headers: { "Cache-Control": "no-store" } },
    );
  }
}

export async function PUT(req: NextRequest) {
  try {
    const res = await fetch(`${AEON_URL}/llm/preferences`, {
      method: "PUT",
      headers: await backendHeaders(),
      body: JSON.stringify(await req.json()),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status, headers: { "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ ok: false, error: "LLM preference service unavailable" }, { status: 502 });
  }
}
