import { auth } from "@/auth";
import { NextResponse } from "next/server";

const AEON_URL = process.env.AEON_PYTHON_URL || "http://127.0.0.1:5000";

export async function GET() {
  try {
    const session = await auth();
    if (!session?.user) {
      return NextResponse.json({ ok: false, error: "unauthorized" }, { status: 401 });
    }

    // The browser sends the Flask JWT as a header; forward it.
    // If no Flask JWT is available, the Flask endpoint will reject with 401.
    const res = await fetch(`${AEON_URL}/workspaces`, {
      method: "GET",
      headers: { "Content-Type": "application/json" },
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err: any) {
    return NextResponse.json({ ok: false, error: err.message }, { status: 500 });
  }
}
