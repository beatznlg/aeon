import { NextRequest, NextResponse } from "next/server";
import { withBackendSessionHeaders } from "@/lib/backend-session";

const PYTHON_URL = process.env.AEON_PYTHON_URL;

export async function POST(req: NextRequest) {
  if (!PYTHON_URL) {
    return NextResponse.json({ ok: false, error: "AEON_PYTHON_URL not set" });
  }
  try {
    const body = await req.json();
    const res = await fetch(`${PYTHON_URL}/rag/chat`, {
      method: "POST",
      headers: await withBackendSessionHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e?.message || String(e) });
  }
}
