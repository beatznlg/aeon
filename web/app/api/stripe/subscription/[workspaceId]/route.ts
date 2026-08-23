import { NextRequest, NextResponse } from "next/server";
import { withBackendSessionHeaders } from "@/lib/backend-session";
import { pythonUrl } from "@/lib/kernel";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest, context: { params: Promise<{ workspaceId: string }> }) {
  const params = await context.params;
  const url = pythonUrl();
  if (!url) {
    return NextResponse.json({ ok: false, error: "AEON_PYTHON_URL not set" }, { status: 503 });
  }

  try {
    const res = await fetch(
      `${url}/stripe/subscription/${encodeURIComponent(params.workspaceId)}`,
      {
        headers: await withBackendSessionHeaders(
          req.headers.get("authorization")
            ? { Authorization: req.headers.get("authorization") as string }
            : {}
        ),
        cache: "no-store",
      }
    );
    const data = await res.json();
    return NextResponse.json(data);
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e?.message || String(e) }, { status: 503 });
  }
}
