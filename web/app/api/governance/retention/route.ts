import { NextResponse } from "next/server";
import { auth } from "@/auth";
import { pythonUrl } from "@/lib/kernel";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const session = await auth();
  const { searchParams } = new URL(req.url);
  const workspaceId = searchParams.get("workspace_id") || ((session?.user as any)?.workspaceId as string) || "default";

  const url = pythonUrl();
  if (!url) {
    return NextResponse.json({
      ok: true,
      policy: { workspace_id: workspaceId, retention_days: 365, action: "archive" },
    });
  }

  try {
    const res = await fetch(
      `${url}/governance/retention?workspace_id=${encodeURIComponent(workspaceId)}`,
      { cache: "no-store" }
    );
    const data = await res.json();
    return NextResponse.json(data);
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e?.message || String(e) }, { status: 503 });
  }
}

export async function POST(req: Request) {
  const session = await auth();
  const body = await req.json().catch(() => ({}));
  const workspaceId = body.workspace_id || ((session?.user as any)?.workspaceId as string) || "default";
  const retentionDays = Math.max(1, Number(body.retention_days || 365));
  const action = ["delete", "archive"].includes(body.action) ? body.action : "archive";

  const url = pythonUrl();
  if (!url) {
    return NextResponse.json({ ok: false, error: "AEON kernel not configured" }, { status: 503 });
  }

  try {
    const res = await fetch(`${url}/governance/retention`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        workspace_id: workspaceId,
        retention_days: retentionDays,
        action,
      }),
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e?.message || String(e) }, { status: 503 });
  }
}
