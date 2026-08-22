import { NextRequest, NextResponse } from "next/server";

const AEON_URL = process.env.AEON_PYTHON_URL || "http://127.0.0.1:5000";

export async function GET(req: NextRequest, context: { params: Promise<{ workspaceId: string }> }) {
  const params = await context.params;
  try {
    const authHeader = req.headers.get("authorization");
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (authHeader) {
      headers["Authorization"] = authHeader;
    }

    const limit = req.nextUrl.searchParams.get("limit") || "50";
    const res = await fetch(`${AEON_URL}/workspaces/${params.workspaceId}/history?limit=${limit}`, {
      headers,
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err: any) {
    return NextResponse.json({ ok: false, error: err.message }, { status: 500 });
  }
}
