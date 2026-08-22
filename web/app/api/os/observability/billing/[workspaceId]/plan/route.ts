import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/auth";
import { pythonUrl } from "@/lib/kernel";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest, context: { params: Promise<{ workspaceId: string }> }) {
  const params = await context.params;
  const session = await auth();
  const url = pythonUrl();
  if (!url) {
    return NextResponse.json({ ok: false, error: "AEON_PYTHON_URL not set" }, { status: 503 });
  }

  try {
    const body = await req.json();
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    const authorization = req.headers.get("authorization");
    if (authorization) headers.Authorization = authorization;
    const res = await fetch(`${url}/billing/${encodeURIComponent(params.workspaceId)}/plan`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e?.message || String(e) }, { status: 503 });
  }
}
