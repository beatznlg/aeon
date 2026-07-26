import { NextRequest, NextResponse } from "next/server";
import { broadcastEvent } from "@/lib/events";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

/**
 * Internal broadcast endpoint.
 * The Python backend (or any trusted internal service) can POST events here
 * and they will be forwarded to connected SSE clients.
 *
 * Authentication: Authorization: Bearer <AEON_INTERNAL_SECRET>
 */

const INTERNAL_SECRET = process.env.AEON_INTERNAL_SECRET;

export async function POST(req: NextRequest) {
  const authHeader = req.headers.get("Authorization");
  const token = authHeader?.replace("Bearer ", "").trim();

  if (!INTERNAL_SECRET) {
    return NextResponse.json(
      { ok: false, error: "Broadcasting is not configured" },
      { status: 503 }
    );
  }

  if (!token || token !== INTERNAL_SECRET) {
    return NextResponse.json({ ok: false, error: "unauthorized" }, { status: 401 });
  }

  try {
    const body = await req.json();
    const { type, payload, user_id, workspace_id } = body;

    if (!type) {
      return NextResponse.json({ ok: false, error: "type required" }, { status: 400 });
    }

    broadcastEvent({
      type,
      payload: payload || {},
      user_id,
      workspace_id,
      timestamp: new Date().toISOString(),
    });

    return NextResponse.json({ ok: true });
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e?.message || String(e) }, { status: 500 });
  }
}
