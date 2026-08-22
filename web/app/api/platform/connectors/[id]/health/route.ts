import { NextResponse } from "next/server";
import { demoPlatformConnectors } from "@/lib/demo-data";
import { getAuthHeaders } from "@/lib/flask-auth";

export const dynamic = "force-dynamic";

const PYTHON_URL = process.env.AEON_PYTHON_URL || "http://127.0.0.1:5000";

const CONTRACT = ["authenticate", "connect", "discover", "fetch", "normalize", "sync", "webhook", "health_check", "disconnect"];

interface RouteContext {
  params: Promise<{ id: string }>;
}

export async function POST(_request: Request, context: RouteContext) {
  const { id } = await context.params;
  try {
    const res = await fetch(`${PYTHON_URL}/platform/connectors/${id}/health`, {
      method: "POST",
      headers: getAuthHeaders(),
      cache: "no-store",
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    const connector = demoPlatformConnectors.connectors.find((c) => c.id === id);
    if (!connector) {
      return NextResponse.json({ ok: false, error: `unknown connector: ${id}` }, { status: 404 });
    }
    return NextResponse.json({
      ok: true,
      demo: true,
      health: {
        ok: true,
        connector_id: connector.id,
        name: connector.name,
        status: "operational",
        contract: CONTRACT,
        capabilities: CONTRACT,
        required_secrets: connector.required_secrets,
        simulated: true,
        message: `${connector.name} connector implements the universal contract and is ready to authenticate when credentials are configured.`,
      },
    });
  }
}
