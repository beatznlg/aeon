import { NextRequest, NextResponse } from "next/server";

const AEON_URL = process.env.AEON_PYTHON_URL || "http://127.0.0.1:5000";

export async function POST(
  req: NextRequest,
  { params }: { params: { workspaceId: string } }
) {
  try {
    const body = await req.json();
    const { query, provider, ...rest } = body;

    const payload: Record<string, any> = { query, ...rest };
    const activeProvider = provider || req.headers.get("x-aeon-provider") || null;
    if (activeProvider) {
      payload.provider = activeProvider;
    }

    const authHeader = req.headers.get("authorization");
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (authHeader) {
      headers["Authorization"] = authHeader;
    }

    const res = await fetch(`${AEON_URL}/workspaces/${params.workspaceId}/chat`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
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
