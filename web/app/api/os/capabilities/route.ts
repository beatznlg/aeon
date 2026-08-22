import { NextRequest, NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend-fetch";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const isAudit = req.nextUrl.searchParams.get("audit") === "1";
  const query = new URLSearchParams(req.nextUrl.searchParams);
  query.delete("audit");
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return backendFetch(req, `${isAudit ? "/capabilities/audit" : "/capabilities"}${suffix}`);
}

export async function POST(req: NextRequest) {
  const result = await backendFetch(req, "/capabilities/invoke", { method: "POST" });
  const data = await result.clone().json().catch(() => null);
  if (data?.backend_down) {
    return NextResponse.json(
      { ok: false, error: "AEON backend unreachable — capability invocation requires the backend", backend_down: true },
      { status: 503 }
    );
  }
  return result;
}
