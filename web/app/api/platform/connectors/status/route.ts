import { NextResponse } from "next/server";
import { demoConnectorStatus } from "@/lib/demo-data";
import { getAuthHeaders } from "@/lib/flask-auth";

export const dynamic = "force-dynamic";

const PYTHON_URL = process.env.AEON_PYTHON_URL || "http://127.0.0.1:5000";

export async function GET() {
  try {
    const res = await fetch(`${PYTHON_URL}/platform/connectors/status`, {
      headers: getAuthHeaders(),
      cache: "no-store",
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json(demoConnectorStatus);
  }
}
