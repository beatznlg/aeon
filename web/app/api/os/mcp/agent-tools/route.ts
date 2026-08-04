import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const PYTHON_URL = process.env.AEON_PYTHON_URL || "http://127.0.0.1:5000";

export async function GET(req: NextRequest) {
  try {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    const auth = req.headers.get("authorization");
    if (auth) headers["Authorization"] = auth;

    const res = await fetch(`${PYTHON_URL}/mcp/agent-tools`, { headers, cache: "no-store" });
    const text = await res.text();
    let data: unknown;
    try {
      data = JSON.parse(text);
    } catch {
      data = { message: text };
    }
    return NextResponse.json(data, { status: res.status });
  } catch (e) {
    return NextResponse.json({ ok: false, error: String(e) }, { status: 503 });
  }
}
