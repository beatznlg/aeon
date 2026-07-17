import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET() {
  return NextResponse.json({
    ok: true,
    ts: Date.now(),
    backend: process.env.AEON_HF_SPACE_URL ? "aeon-kernel" : "hf-inference",
  });
}
