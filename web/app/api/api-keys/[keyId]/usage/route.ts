import { NextRequest, NextResponse } from "next/server";
import { pythonUrl } from "@/lib/kernel";

export const dynamic = "force-dynamic";

export async function GET(_req: NextRequest, { params }: { params: { keyId: string } }) {
  const url = pythonUrl();
  if (!url) {
    return NextResponse.json({
      ok: true,
      usage: { total_calls: 0, errors: 0, error_rate: 0, by_key: [], by_endpoint: {} },
    });
  }
  try {
    const res = await fetch(`${url}/api-keys/${encodeURIComponent(params.keyId)}/usage`, {
      cache: "no-store",
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e?.message || String(e) }, { status: 503 });
  }
}
