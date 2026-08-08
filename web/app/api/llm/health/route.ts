import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/auth";

const AEON_URL = process.env.AEON_PYTHON_URL || "http://127.0.0.1:5000";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  try {
    const session = await auth();
    const headers: Record<string, string> = { Accept: "application/json" };

    if (session?.user && (session.user as any)?.token) {
      headers.Authorization = `Bearer ${(session.user as any).token}`;
    }

    const query = req.nextUrl.searchParams;
    const params = new URLSearchParams();
    const provider = query.get("provider");
    const model = query.get("model");
    if (provider) params.set("provider", provider);
    if (model) params.set("model", model);

    const suffix = params.toString() ? `?${params.toString()}` : "";
    const res = await fetch(`${AEON_URL}/llm/health${suffix}`, {
      headers,
      cache: "no-store",
    });
    const data = await res.json();
    return NextResponse.json(data, {
      status: res.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return NextResponse.json(
      {
        ok: false,
        ready: false,
        status: "unavailable",
        checked: false,
      },
      {
        status: 502,
        headers: { "Cache-Control": "no-store" },
      },
    );
  }
}
