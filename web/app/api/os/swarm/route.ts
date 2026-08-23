import { NextRequest, NextResponse } from "next/server";
import { withBackendSessionHeaders } from "@/lib/backend-session";

export const dynamic = "force-dynamic";

const PYTHON_URL = process.env.AEON_PYTHON_URL;

export async function POST(req: NextRequest) {
  if (!PYTHON_URL) {
    return NextResponse.json({ ok: false, error: "AEON_PYTHON_URL not set" }, { status: 503 });
  }
  try {
    const body = (await req.json().catch(() => ({}))) as { app_ids?: string[]; prompt?: string };
    const res = await fetch(`${PYTHON_URL}/swarm/run`, {
      method: "POST",
      headers: await withBackendSessionHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        app_ids: body.app_ids || [],
        prompt: body.prompt || "",
      }),
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch (e) {
    return NextResponse.json({ ok: false, error: String(e) }, { status: 503 });
  }
}
