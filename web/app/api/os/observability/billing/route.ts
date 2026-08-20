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
  const days = Math.min(365, Math.max(1, Number(searchParams.get("days") || 30)));

  const url = pythonUrl();
  if (!url) {
    return NextResponse.json({
      ok: true,
      billing: {
        workspace_id: workspaceId,
        plan: {
          id: "free",
          name: "Free",
          limits: { requests: 1000, tokens: 100000, workflows: 10, integrations: 5 },
        },
        credits: 0,
        usage: { requests: 0, tokens: 0, workflows: 0, integrations: 0 },
        estimated_cost: 0,
        remaining_credits: 0,
        quota_usage_pct: {},
      },
    });
  }

  try {
    const headers: Record<string, string> = {};
    const authorization = req.headers.get("authorization");
    if (authorization) headers.Authorization = authorization;
    const res = await fetch(`${url}/billing/${encodeURIComponent(workspaceId)}?days=${days}`, {
      headers,
      cache: "no-store",
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e?.message || String(e) }, { status: 503 });
  }
}
