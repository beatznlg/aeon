import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/auth";

const AEON_URL = (process.env.AEON_PYTHON_URL || "").replace(/\/$/, "");

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const body = await req.json();
  const provider = body?.provider;
  const model = body?.model;

  // Try Flask backend first
  if (AEON_URL) {
    try {
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
    } catch {
      // Flask not reachable — fall through to local response
    }
  }

  // Standalone fallback: accept the switch and return success
  return NextResponse.json({
    ok: true,
    provider: provider || "stub",
    model: model || null,
    preference: { provider: provider || "stub", model: model || null, source: "frontend" },
  });
}
