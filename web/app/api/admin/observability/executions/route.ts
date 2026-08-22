import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/auth";
import { requireRole } from "@/lib/auth";
import { proxyApiRequest } from "@/lib/proxy";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  try {
    requireRole(await auth(), ["ADMIN"]);
    return await proxyApiRequest(request, { backendPath: "/ai/ledger/executions" });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return NextResponse.json({ ok: false, error: message }, { status: 403 });
  }
}
