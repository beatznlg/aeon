import { NextRequest, NextResponse } from "next/server";
import { pythonUrl } from "@/lib/kernel";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const url = pythonUrl();
  if (!url) {
    return NextResponse.json({ ok: false, error: "AEON_PYTHON_URL not set" }, { status: 503 });
  }

  try {
    const rawBody = await req.text();
    const signature = req.headers.get("Stripe-Signature") || "";
    const res = await fetch(`${url}/stripe/webhook`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Stripe-Signature": signature,
      },
      body: rawBody,
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e?.message || String(e) }, { status: 503 });
  }
}
