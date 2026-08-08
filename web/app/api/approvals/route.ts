import { NextRequest, NextResponse } from "next/server";
import { sanitizeApprovalResponse } from "@/lib/approval-response";

const AEON_URL = process.env.AEON_PYTHON_URL || "http://127.0.0.1:5000";

export const dynamic = "force-dynamic";

function backendHeaders(req: NextRequest, includeBody = false): Record<string, string> {
  const headers: Record<string, string> = {};
  if (includeBody) headers["Content-Type"] = "application/json";
  const authHeader = req.headers.get("authorization");
  if (authHeader) headers.Authorization = authHeader;
  return headers;
}

async function forward(req: NextRequest, method: "GET" | "POST", body?: string) {
  try {
    const res = await fetch(`${AEON_URL}/approvals${method === "GET" ? `?status=${encodeURIComponent(req.nextUrl.searchParams.get("status") || "pending")}` : ""}`, {
      method,
      headers: backendHeaders(req, method === "POST"),
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

export async function GET(req: NextRequest) {
  return forward(req, "GET");
}

export async function POST(req: NextRequest) {
  return forward(req, "POST", await req.text());
}
