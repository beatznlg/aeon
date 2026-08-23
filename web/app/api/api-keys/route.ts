import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/auth";
import { withBackendSessionHeaders } from "@/lib/backend-session";
import { pythonUrl } from "@/lib/kernel";
import { demoApiKeys } from "@/lib/demo-data";

export const dynamic = "force-dynamic";

export async function GET() {
  const session = await auth();
  const workspaceId = ((session?.user as any)?.workspaceId as string) || "default";
  const url = pythonUrl();
  if (!url) {
    // No backend configured — serve demo API keys so the page renders populated.
    return NextResponse.json({ ...demoApiKeys, workspace_id: workspaceId, demo: true });
  }
  try {
    const res = await fetch(`${url}/api-keys?workspace_id=${encodeURIComponent(workspaceId)}`, {
      cache: "no-store",
      headers: await withBackendSessionHeaders({}),
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    // Backend unreachable — serve demo API keys so the page renders populated.
    return NextResponse.json({ ...demoApiKeys, workspace_id: workspaceId, demo: true });
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
      headers: await withBackendSessionHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e?.message || String(e) }, { status: 503 });
  }
}
