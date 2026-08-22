import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/auth";
import { pythonUrl } from "@/lib/kernel";
import { backendFetch } from "@/lib/backend-fetch";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  return backendFetch(req, "/governance/retention");
}

export async function POST(req: Request) {
  const session = await auth();
  const body = await req.json().catch(() => ({}));
  const workspaceId =
    body.workspace_id || ((session?.user as any)?.workspaceId as string) || "default";
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
