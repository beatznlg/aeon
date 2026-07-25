import { NextResponse } from "next/server";
import { auth } from "@/auth";
import { pythonUrl } from "@/lib/kernel";

export const dynamic = "force-dynamic";

export async function GET() {
  const session = await auth();
  const workspaceId = ((session?.user as any)?.workspaceId as string) || "default";
  const url = pythonUrl();
  if (!url) {
    return NextResponse.json({
      ok: true,
      usage: { total_calls: 0, errors: 0, error_rate: 0, total_keys: 0, active_keys: 0, by_key: [], by_endpoint: {} },
    });
  }
  try {
    const res = await fetch(`${url}/api-keys/usage/summary?workspace_id=${encodeURIComponent(workspaceId)}`, {
      cache: "no-store",
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e?.message || String(e) }, { status: 503 });
  }
}
