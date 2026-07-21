import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/auth";
import { logUsage } from "@/lib/usage";

export const dynamic = "force-dynamic";

const PYTHON_URL = process.env.AEON_PYTHON_URL;

export async function POST(req: NextRequest, { params }: { params: { id: string } }) {
  const session = await auth();
  const userId = (session?.user as any)?.id;
  const workspaceId = (session?.user as any)?.workspaceId;

  if (!PYTHON_URL) {
    return NextResponse.json({ ok: false, error: "AEON_PYTHON_URL not set" }, { status: 503 });
  }
  try {
    const { id } = params;
    const body = (await req.json().catch(() => ({}))) as { initial_input?: string };
    const res = await fetch(`${PYTHON_URL}/workflows/${encodeURIComponent(id)}/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ initial_input: body.initial_input || "" }),
    });
    const data = await res.json();

    logUsage({
      userId,
      workspaceId,
      action: "workflow_run",
      module: params.id,
      quantity: data?.results?.length || 1,
    });

    return NextResponse.json(data);
  } catch (e) {
    return NextResponse.json({ ok: false, error: String(e) }, { status: 503 });
  }
}
