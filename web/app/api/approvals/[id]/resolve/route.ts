import { NextRequest, NextResponse } from "next/server";
import { sanitizeApprovalResponse } from "@/lib/approval-response";

const AEON_URL = process.env.AEON_PYTHON_URL || "http://127.0.0.1:5000";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest, context: { params: Promise<{ id: string }> }) {
  const params = await context.params;
  try {
    const body = await req.text();
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    const authHeader = req.headers.get("authorization");
    if (authHeader) headers.Authorization = authHeader;
    const res = await fetch(`${AEON_URL}/approvals/${encodeURIComponent(params.id)}/resolve`, {
      method: "POST",
      headers,
      body,
      cache: "no-store",
    });
    const text = await res.text();
    let data: unknown;
    try {
      data = JSON.parse(text);
    } catch {
      data = { ok: false, error: text || "Approval service returned an invalid response" };
    }
    return NextResponse.json(sanitizeApprovalResponse(data), { status: res.status });
  } catch (error) {
    return NextResponse.json({ ok: false, error: error instanceof Error ? error.message : "Approval service unavailable" }, { status: 503 });
  }
}
