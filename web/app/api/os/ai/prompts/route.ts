import { NextRequest, NextResponse } from "next/server";
import { demoPrompts } from "@/lib/demo-data";

const PYTHON_URL = process.env.AEON_PYTHON_URL;

export async function GET() {
  if (!PYTHON_URL) {
    return NextResponse.json(demoPrompts);
  }
  try {
    const res = await fetch(`${PYTHON_URL}/prompts`, { cache: "no-store" });
    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json(demoPrompts);
  }
}

export async function POST(req: NextRequest) {
  if (!PYTHON_URL) {
    return NextResponse.json({ ok: false, error: "AEON_PYTHON_URL not set" });
  }
  try {
    const body = await req.json();
    const res = await fetch(`${PYTHON_URL}/prompts`, {
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
