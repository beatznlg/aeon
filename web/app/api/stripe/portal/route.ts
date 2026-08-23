import { NextRequest, NextResponse } from "next/server";
import { withBackendSessionHeaders } from "@/lib/backend-session";
import { pythonUrl } from "@/lib/kernel";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const url = pythonUrl();
  if (!url) {
    return NextResponse.json({ ok: false, error: "AEON_PYTHON_URL not set" }, { status: 503 });
  }

  try {
    const body = await req.json();
    const res = await fetch(`${url}/stripe/portal`, {
      method: "POST",
      headers: await withBackendSessionHeaders({
        "Content-Type": "application/json",
        ...(req.headers.get("authorization")
          ? { Authorization: req.headers.get("authorization") as string }
          : {}),
      }),
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e?.message || String(e) }, { status: 503 });
  }
}
