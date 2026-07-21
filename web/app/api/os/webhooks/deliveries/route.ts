import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const PYTHON_URL = process.env.AEON_PYTHON_URL;

export async function GET() {
  if (!PYTHON_URL) {
    return NextResponse.json({ ok: true, deliveries: [], note: "AEON_PYTHON_URL not set" });
  }
  try {
    const res = await fetch(`${PYTHON_URL}/webhooks/deliveries`, { cache: "no-store" });
    const data = await res.json();
    return NextResponse.json(data);
  } catch (e) {
    return NextResponse.json({ ok: false, error: String(e) }, { status: 503 });
  }
}
