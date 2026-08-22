import { NextRequest, NextResponse } from "next/server";

const PYTHON_URL = process.env.AEON_PYTHON_URL;

export async function POST(req: NextRequest, context: { params: Promise<{ id: string }> }) {
  const params = await context.params;
  if (!PYTHON_URL) {
    return NextResponse.json({ ok: false, error: "AEON_PYTHON_URL not set" });
  }
  try {
    const body = await req.json();
    const res = await fetch(`${PYTHON_URL}/knowledge-bases/${params.id}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e?.message || String(e) });
  }
}

export async function GET(_req: NextRequest, context: { params: Promise<{ id: string }> }) {
  const params = await context.params;
  if (!PYTHON_URL) {
    return NextResponse.json({ ok: false, error: "AEON_PYTHON_URL not set" });
  }
  try {
    const res = await fetch(`${PYTHON_URL}/knowledge-bases/${params.id}/stats`, {
      cache: "no-store",
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e?.message || String(e) });
  }
}
