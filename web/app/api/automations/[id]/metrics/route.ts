import { NextRequest, NextResponse } from "next/server";

const AEON_URL = process.env.AEON_PYTHON_URL || "http://127.0.0.1:5000";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest, context: { params: Promise<{ id: string }> }) {
  const params = await context.params;
  try {
    const headers: Record<string, string> = {};
    const authHeader = req.headers.get("authorization");
    if (authHeader) headers["Authorization"] = authHeader;

    const { searchParams } = new URL(req.url);
    const query = searchParams.toString();
    const url = `${AEON_URL}/automations/${params.id}/metrics${query ? `?${query}` : ""}`;

    const res = await fetch(url, {
      method: "GET",
      headers,
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
