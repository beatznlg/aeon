import { NextResponse } from "next/server";
import { auth } from "@/auth";
import { pythonUrl } from "@/lib/kernel";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const session = await auth();
  const { searchParams } = new URL(req.url);
  const workspaceId =
    searchParams.get("workspace_id") ||
    ((session?.user as any)?.workspaceId as string) ||
    "default";
  const checkType = searchParams.get("check_type") || "pii_scan";

  const url = pythonUrl();
  if (!url) {
    return NextResponse.json({
      ok: true,
      check_type: checkType,
      status: "warning",
      findings: [],
      note: "AEON kernel not configured",
    });
  }

  const query = new URLSearchParams({ check_type: checkType, workspace_id: workspaceId });
  try {
    const res = await fetch(`${url}/governance/compliance?${query.toString()}`, {
      cache: "no-store",
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e?.message || String(e) }, { status: 503 });
  }
}

export async function POST(req: Request) {
  const session = await auth();
  const body = await req.json().catch(() => ({}));
  const workspaceId =
    body.workspace_id || ((session?.user as any)?.workspaceId as string) || "default";
  const checkType = body.check_type || "pii_scan";

  const url = pythonUrl();
  if (!url) {
    return NextResponse.json({
      ok: true,
      check_type: checkType,
      status: "warning",
      findings: [],
      note: "AEON kernel not configured",
    });
  }

  try {
    const res = await fetch(`${url}/governance/compliance`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ check_type: checkType, workspace_id: workspaceId }),
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e?.message || String(e) }, { status: 503 });
  }
}
