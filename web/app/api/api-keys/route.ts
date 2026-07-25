import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/auth";
import { pythonUrl } from "@/lib/kernel";

export const dynamic = "force-dynamic";

export async function GET() {
  const session = await auth();
  const workspaceId = ((session?.user as any)?.workspaceId as string) || "default";
  const url = pythonUrl();
  if (!url) {
    return NextResponse.json({ ok: true, keys: [], workspace_id: workspaceId });
  }
  try {
    const res = await fetch(`${url}/api-keys?workspace_id=${encodeURIComponent(workspaceId)}`, {
      cache: "no-store",
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e?.message || String(e) }, { status: 503 });
  }
}

export async function POST(req: NextRequest) {
  const session = await auth();
  const url = pythonUrl();
  if (!url) {
    return NextResponse.json({ ok: false, error: "AEON_PYTHON_URL not set" }, { status: 503 });
  }
  try {
    const body = await req.json();
    const res = await fetch(`${url}/api-keys`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e?.message || String(e) }, { status: 503 });
  }
}
