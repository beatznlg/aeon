import { NextRequest, NextResponse } from "next/server";
import { APPS } from "@/lib/apps";

export const dynamic = "force-dynamic";

let installed: string[] = [];

export async function GET() {
  return NextResponse.json({ ok: true, apps: APPS, installed });
}

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  const appId = String(body.appId || "").trim();
  const exists = APPS.some((a) => a.id === appId);
  if (!exists) {
    return NextResponse.json({ ok: false, error: "unknown app" }, { status: 400 });
  }
  if (!installed.includes(appId)) {
    installed.push(appId);
  }
  return NextResponse.json({ ok: true, appId, installed });
}
