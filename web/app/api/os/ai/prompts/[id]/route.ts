import { NextRequest, NextResponse } from "next/server";

const PYTHON_URL = process.env.AEON_PYTHON_URL;

export async function GET(_req: NextRequest, context: { params: Promise<{ id: string }> }) {
  const params = await context.params;
  if (!PYTHON_URL) {
    return NextResponse.json({ ok: false, error: "AEON_PYTHON_URL not set" });
  }
  try {
    const res = await fetch(`${PYTHON_URL}/prompts/${params.id}`, { cache: "no-store" });
    const data = await res.json();
    return NextResponse.json(data);
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e?.message || String(e) });
  }
}

export async function DELETE(_req: NextRequest, context: { params: Promise<{ id: string }> }) {
  const params = await context.params;
  if (!PYTHON_URL) {
    return NextResponse.json({ ok: false, error: "AEON_PYTHON_URL not set" });
  }
  try {
    const res = await fetch(`${PYTHON_URL}/prompts/${params.id}`, { method: "DELETE" });
    const data = await res.json();
    return NextResponse.json(data);
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e?.message || String(e) });
  }
}
