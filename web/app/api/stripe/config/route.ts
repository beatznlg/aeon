import { NextResponse } from "next/server";
import { pythonUrl } from "@/lib/kernel";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const url = pythonUrl();
  if (!url) {
    return NextResponse.json({ ok: false, error: "AEON_PYTHON_URL not set" }, { status: 503 });
  }

  try {
    const authorization = req.headers.get("authorization");
    const res = await fetch(`${url}/stripe/config`, {
      headers: authorization ? { Authorization: authorization } : undefined,
      cache: "no-store",
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: "proxy error" }, { status: 503 });
  }
}
