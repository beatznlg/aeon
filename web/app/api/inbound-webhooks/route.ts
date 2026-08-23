import { NextRequest, NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend-fetch";
import { withBackendSessionHeaders } from "@/lib/backend-session";

export const dynamic = "force-dynamic";

const AEON_URL = process.env.AEON_PYTHON_URL || "http://127.0.0.1:5000";

export async function GET(req: NextRequest) {
  return backendFetch(req, "/inbound-webhooks");
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    await withBackendSessionHeaders(headers);
    const authHeader = req.headers.get("authorization");
    if (authHeader) headers["Authorization"] = authHeader;

    const res = await fetch(`${AEON_URL}/inbound-webhooks`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    });
    const text = await res.text();
    let data: any;
    try {
      data = JSON.parse(text);
    } catch {
      data = { message: text };
    }
    return NextResponse.json(data, { status: res.status });
  } catch (err: any) {
    return NextResponse.json({ ok: false, error: err.message }, { status: 500 });
  }
}
