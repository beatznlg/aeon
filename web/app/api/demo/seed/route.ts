import { NextRequest, NextResponse } from "next/server";

const DEMO_EMAIL = process.env.AEON_DEMO_EMAIL || "admin@demo.local";
const DEMO_PASSWORD = process.env.AEON_DEMO_PASSWORD || "demo123";
const DEMO_NAME = process.env.AEON_DEMO_NAME || "Demo Admin";
const AEON_URL = (process.env.AEON_PYTHON_URL || "http://127.0.0.1:5000").replace(/\/$/, "");

/**
 * Production demo bootstrap. Oracle is the source of truth: create the demo
 * user through the Flask/PostgreSQL auth service, then return the configured
 * demo credentials to the browser for the one-click login flow.
 *
 * The demo account is deliberately opt-in in production. It must never be
 * created silently when AEON_DEMO_ENABLED is false.
 */
export async function POST(_req: NextRequest) {
  const enabled = process.env.AEON_DEMO_ENABLED === "true" || process.env.NODE_ENV !== "production";
  if (!enabled) {
    return NextResponse.json({ ok: false, error: "Demo account is disabled" }, { status: 404 });
  }

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);
    try {
      const register = await fetch(`${AEON_URL}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: DEMO_EMAIL, password: DEMO_PASSWORD, name: DEMO_NAME }),
        signal: controller.signal,
        cache: "no-store",
      });
      const registered = await register.json().catch(() => ({}));
      if (registered?.ok) {
        return NextResponse.json({ ok: true, email: DEMO_EMAIL, password: DEMO_PASSWORD });
      }

      const login = await fetch(`${AEON_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: DEMO_EMAIL, password: DEMO_PASSWORD }),
        signal: controller.signal,
        cache: "no-store",
      });
      const loggedIn = await login.json().catch(() => ({}));
      if (loggedIn?.ok) {
        return NextResponse.json({ ok: true, email: DEMO_EMAIL, password: DEMO_PASSWORD });
      }
    } finally {
      clearTimeout(timeout);
    }

    return NextResponse.json({ ok: false, error: "Demo backend is not ready" }, { status: 503 });
  } catch {
    return NextResponse.json({ ok: false, error: "Demo backend is not reachable" }, { status: 503 });
  }
}
