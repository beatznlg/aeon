import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/auth";
import { withBackendSessionHeaders } from "@/lib/backend-session";
import { logUsage } from "@/lib/usage";

export const dynamic = "force-dynamic";

const PYTHON_URL = process.env.AEON_PYTHON_URL;

export async function POST(req: NextRequest, context: { params: Promise<{ id: string }> }) {
  const params = await context.params;
  const session = await auth();
  const userId = (session?.user as any)?.id;
  const workspaceId = (session?.user as any)?.workspaceId;

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
      headers: await withBackendSessionHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        endpoint: body.endpoint || "",
        method: body.method || "GET",
        payload: body.payload,
      }),
    });
    const data = await res.json();

    logUsage({
      userId,
      workspaceId,
      action: "integration_call",
      module: params.id,
      quantity: 1,
    });

    return NextResponse.json(data);
  } catch (e) {
    return NextResponse.json({ ok: false, error: String(e) }, { status: 503 });
  }
}
