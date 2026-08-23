import { NextResponse } from "next/server";
import { withBackendSessionHeaders } from "@/lib/backend-session";
import { demoPlatformConnectors } from "@/lib/demo-data";

export const dynamic = "force-dynamic";

const PYTHON_URL = process.env.AEON_PYTHON_URL || "http://127.0.0.1:5000";

export async function GET() {
  try {
    const res = await fetch(`${PYTHON_URL}/platform/connectors`, {
      headers: await withBackendSessionHeaders({ "Content-Type": "application/json" }),
      cache: "no-store",
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json(demoPlatformConnectors);
  }
}
