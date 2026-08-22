import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/auth";

const AEON_URL = (process.env.AEON_PYTHON_URL || "").replace(/\/$/, "");

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const body = await req.json();
  const provider = body?.provider || "stub";

  // Try Flask backend first
  if (AEON_URL) {
    try {
      const session = await auth();
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (session?.user && (session.user as any)?.token) {
        headers["Authorization"] = `Bearer ${(session.user as any).token}`;
      }
      const res = await fetch(`${AEON_URL}/llm/test`, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
      });
      const data = await res.json();
      return NextResponse.json(data, { status: res.status });
    } catch {
      // Flask not reachable — fall through
    }
  }

  // Standalone fallback: test stub provider directly
  if (provider === "stub") {
    return NextResponse.json({
      ok: true,
      backend: "stub",
      text: "Hello from AEON OS stub provider. The AEON backend is not running, but the UI is functional.",
      latency_s: 0.01,
      tokens_used: 12,
    });
  }

  // For real providers without Flask, inform the user
  return NextResponse.json({
    ok: false,
    error: `The AEON backend is not reachable. Deploy the Flask backend and set AEON_PYTHON_URL, or run locally with \`npm run dev:full\` from web/.`,
  });
}
