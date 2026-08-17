import { NextRequest, NextResponse } from "next/server";

const AEON_PYTHON_URL = process.env.AEON_PYTHON_URL || "http://127.0.0.1:5000";

/**
 * Server-side proxy for the AEON Python backend auth endpoints.
 *
 * The browser must not call the Flask origin directly (it is often a private
 * 127.0.0.1 address or a CORS-restricted host), so the login page and the
 * flask-auth helpers route login/register through this Next.js route instead.
 *
 * Body: { action: "login" | "register", email, password, name? }
 */
export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const action = body?.action === "register" ? "register" : "login";

    const res = await fetch(`${AEON_PYTHON_URL}/auth/${action}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: body?.email,
        password: body?.password,
        name: body?.name,
      }),
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err: any) {
    return NextResponse.json(
      {
        ok: false,
        error:
          "AEON backend unreachable — is the Python server running? Start it with `npm run dev:full` from web/, or set AEON_PYTHON_URL.",
      },
      { status: 502 }
    );
  }
}
