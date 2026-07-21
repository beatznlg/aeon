import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const PYTHON_URL = process.env.AEON_PYTHON_URL;

export async function POST(req: NextRequest, { params }: { params: { id: string } }) {
  if (!PYTHON_URL) {
    return NextResponse.json({ ok: false, error: "AEON_PYTHON_URL not set" }, { status: 503 });
  }
  try {
    const { id } = params;
    const body = (await req.json().catch(() => ({}))) as {
      endpoint?: string;
      method?: string;
      payload?: unknown;
    };
    const res = await fetch(`${PYTHON_URL}/integrations/${encodeURIComponent(id)}/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        endpoint: body.endpoint || "",
        method: body.method || "GET",
        payload: body.payload,
      }),
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch (e) {
    return NextResponse.json({ ok: false, error: String(e) }, { status: 503 });
  }
}
