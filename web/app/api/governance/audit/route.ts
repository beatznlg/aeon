import { NextResponse } from "next/server";
import { auth } from "@/auth";
import { pythonUrl } from "@/lib/kernel";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const session = await auth();
  const { searchParams } = new URL(req.url);
  const workspaceId = searchParams.get("workspace_id") || ((session?.user as any)?.workspaceId as string) || "default";
  const action = searchParams.get("action") || undefined;
  const moduleName = searchParams.get("module") || undefined;
  const limit = Math.min(1000, Math.max(1, Number(searchParams.get("limit") || 100)));
  const offset = Math.max(0, Number(searchParams.get("offset") || 0));

  const url = pythonUrl();
  if (!url) {
    return NextResponse.json({ ok: true, rows: [], count: 0, limit, offset });
  }

  const query = new URLSearchParams({
    workspace_id: workspaceId,
    limit: String(limit),
    offset: String(offset),
  });
  if (action) query.set("action", action);
  if (moduleName) query.set("module", moduleName);

  try {
    const res = await fetch(`${url}/governance/audit?${query.toString()}`, { cache: "no-store" });
    const data = await res.json();
    return NextResponse.json(data);
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e?.message || String(e) }, { status: 503 });
  }
}
