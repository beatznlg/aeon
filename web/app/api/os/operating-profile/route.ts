import { NextRequest, NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend-fetch";

export const dynamic = "force-dynamic";

const PYTHON_URL = process.env.AEON_PYTHON_URL || "http://127.0.0.1:5000";

export async function GET(req: NextRequest) {
  return backendFetch(req, "/workspace/operating-profile");
}

export async function PUT(req: NextRequest) {
  try {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    const auth = req.headers.get("authorization");
    if (auth) headers.Authorization = auth;

    const response = await fetch(`${PYTHON_URL}/workspace/operating-profile`, {
      method: "PUT",
      headers,
      body: await req.text(),
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
