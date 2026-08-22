import { NextRequest, NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend-fetch";

export const dynamic = "force-dynamic";

const PYTHON_URL = process.env.AEON_PYTHON_URL;

export async function GET(req: NextRequest) {
  return backendFetch(req, "/workflows");
}

export async function POST(req: NextRequest) {
  if (!PYTHON_URL) {
    return NextResponse.json({ ok: false, error: "AEON_PYTHON_URL not set" }, { status: 503 });
  }
  try {
    const body = await req.json();
    const res = await fetch(`${PYTHON_URL}/workflows`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch (e) {
    return NextResponse.json({ ok: false, error: String(e) }, { status: 503 });
  }
}
