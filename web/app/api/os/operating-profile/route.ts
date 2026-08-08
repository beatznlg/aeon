import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const PYTHON_URL = process.env.AEON_PYTHON_URL || "http://127.0.0.1:5000";

function forwardedHeaders(req: NextRequest): Record<string, string> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const auth = req.headers.get("authorization");
  if (auth) headers.Authorization = auth;
  return headers;
}

export async function GET(req: NextRequest) {
  return forward(req, "GET");
}

export async function PUT(req: NextRequest) {
  return forward(req, "PUT");
}

async function forward(req: NextRequest, method: "GET" | "PUT") {
  try {
    const response = await fetch(`${PYTHON_URL}/workspace/operating-profile`, {
      method,
      headers: forwardedHeaders(req),
      body: method === "PUT" ? await req.text() : undefined,
      cache: "no-store",
    });
    const text = await response.text();
    let data: unknown;
    try {
      data = JSON.parse(text);
    } catch {
      data = { ok: false, error: text };
    }
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    return NextResponse.json({ ok: false, error: String(error) }, { status: 503 });
  }
}
