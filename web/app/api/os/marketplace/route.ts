import { NextRequest, NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend-fetch";
import { withBackendSessionHeaders } from "@/lib/backend-session";

export const dynamic = "force-dynamic";

const PYTHON_URL = process.env.AEON_PYTHON_URL;

type Action = "install" | "uninstall" | "enable" | "disable" | "config" | "run";

const ACTION_ROUTES: Record<Action, string> = {
  install: "/install",
  uninstall: "/uninstall",
  enable: "/enable",
  disable: "/disable",
  config: "/config",
  run: "/run",
};

export async function GET(req: NextRequest) {
  return backendFetch(req, "/marketplace/plugins");
}

export async function POST(req: NextRequest) {
  if (!PYTHON_URL) {
    return NextResponse.json({ ok: false, error: "AEON_PYTHON_URL not set" }, { status: 503 });
  }
  try {
    const body = await req.json();
    const pluginId = body.plugin_id as string;
    const action = body.action as Action;
    if (!pluginId || !action) {
      return NextResponse.json(
        { ok: false, error: "plugin_id and action are required" },
        { status: 400 }
      );
    }
    const route = ACTION_ROUTES[action];
    if (!route) {
      return NextResponse.json({ ok: false, error: `unknown action '${action}'` }, { status: 400 });
    }

    const payload: Record<string, unknown> = {};
    if (action === "install" || action === "config") payload.config = body.config ?? {};
    if (action === "run") {
      payload.entry = body.entry;
      payload.params = body.params ?? {};
    }

    const res = await fetch(`${PYTHON_URL}/marketplace/plugins/${pluginId}${route}`, {
      method: "POST",
      headers: await withBackendSessionHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload),
      cache: "no-store",
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (e) {
    return NextResponse.json({ ok: false, error: String(e) }, { status: 503 });
  }
}
