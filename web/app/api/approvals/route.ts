import { NextRequest, NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend-fetch";
import { withBackendSessionHeaders } from "@/lib/backend-session";
import { sanitizeApprovalResponse } from "@/lib/approval-response";

const AEON_URL = process.env.AEON_PYTHON_URL || "http://127.0.0.1:5000";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  return backendFetch(req, "/approvals");
}

export async function POST(req: NextRequest) {
  try {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    await withBackendSessionHeaders(headers);
    const authHeader = req.headers.get("authorization");
    if (authHeader) headers.Authorization = authHeader;

    const res = await fetch(`${AEON_URL}/approvals`, {
      method: "POST",
      headers,
      body: await req.text(),
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
    return NextResponse.json(
      { ok: false, error: error instanceof Error ? error.message : "Approval service unavailable" },
      { status: 503 }
    );
  }
}
