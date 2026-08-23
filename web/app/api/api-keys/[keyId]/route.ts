import { NextRequest, NextResponse } from "next/server";
import { withBackendSessionHeaders } from "@/lib/backend-session";
import { pythonUrl } from "@/lib/kernel";

export const dynamic = "force-dynamic";

export async function DELETE(_req: NextRequest, context: { params: Promise<{ keyId: string }> }) {
  const params = await context.params;
  const url = pythonUrl();
  if (!url) {
    return NextResponse.json({ ok: false, error: "AEON_PYTHON_URL not set" }, { status: 503 });
  }
  try {
    const res = await fetch(`${url}/api-keys/${encodeURIComponent(params.keyId)}`, {
      method: "DELETE",
      headers: await withBackendSessionHeaders({}),
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e?.message || String(e) }, { status: 503 });
  }
}

export async function PATCH(req: NextRequest, context: { params: Promise<{ keyId: string }> }) {
  const params = await context.params;
  const url = pythonUrl();
  if (!url) {
    return NextResponse.json({ ok: false, error: "AEON_PYTHON_URL not set" }, { status: 503 });
  }
  try {
    const body = await req.json();
    const res = await fetch(`${url}/api-keys/${encodeURIComponent(params.keyId)}`, {
      method: "PATCH",
      headers: await withBackendSessionHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e?.message || String(e) }, { status: 503 });
  }
}
