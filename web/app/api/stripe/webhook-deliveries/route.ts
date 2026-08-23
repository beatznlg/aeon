import { NextResponse } from "next/server";
import { withBackendSessionHeaders } from "@/lib/backend-session";
import { pythonUrl } from "@/lib/kernel";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const url = pythonUrl();
  if (!url) {
    return NextResponse.json({ ok: false, error: "AEON_PYTHON_URL not set" }, { status: 503 });
  }

  try {
    const authorization = req.headers.get("authorization");
    const limit = new URL(req.url).searchParams.get("limit") || "100";
    const headers = await withBackendSessionHeaders(
      authorization ? { Authorization: authorization } : {}
    );
    const res = await fetch(`${url}/stripe/webhook-deliveries?limit=${encodeURIComponent(limit)}`, {
      headers: Object.keys(headers).length > 0 ? headers : undefined,
      cache: "no-store",
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: "proxy error" }, { status: 503 });
  }
}
