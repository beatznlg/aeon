import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/auth";

const AEON_URL = process.env.AEON_PYTHON_URL || "http://127.0.0.1:5000";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const session = await auth();
    const headers: Record<string, string> = { "Content-Type": "application/json" };

    if (session?.user && (session.user as any)?.token) {
      headers["Authorization"] = `Bearer ${(session.user as any).token}`;
    }

    const res = await fetch(`${AEON_URL}/llm/switch`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err: any) {
    return NextResponse.json({ ok: false, error: err.message }, { status: 500 });
  }
}
