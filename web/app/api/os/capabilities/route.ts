import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const PYTHON_URL = process.env.AEON_PYTHON_URL || "http://127.0.0.1:5000";

function forwardedHeaders(req: NextRequest): Record<string, string> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const auth = req.headers.get("authorization");
  if (auth) headers.Authorization = auth;
  return headers;
}

async function proxy(req: NextRequest, method: "GET" | "POST", endpoint: string) {
  try {
    const res = await fetch(`${PYTHON_URL}${endpoint}`, {
      method,
      headers: forwardedHeaders(req),
      body: method === "POST" ? await req.text() : undefined,
      cache: "no-store",
    });
    const text = await res.text();
    let data: unknown;
    try {
      data = JSON.parse(text);
    } catch {
      data = { ok: false, error: text };
    }
    return NextResponse.json(data, { status: res.status });
  } catch (error) {
    return NextResponse.json({ ok: false, error: String(error) }, { status: 503 });
  }
}

export async function GET(req: NextRequest) {
  const isAudit = req.nextUrl.searchParams.get("audit") === "1";
  const query = new URLSearchParams(req.nextUrl.searchParams);
  query.delete("audit");
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return proxy(req, "GET", `${isAudit ? "/capabilities/audit" : "/capabilities"}${suffix}`);
}

export async function POST(req: NextRequest) {
  return proxy(req, "POST", "/capabilities/invoke");
}
