import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const AEON_URL = (process.env.AEON_PYTHON_URL || "http://127.0.0.1:5000").replace(/\/$/, "");

/**
 * GET /api/health
 *
 * Liveness probe for the Next.js instance plus a real reachability check of
 * the Flask backend (`AEON_PYTHON_URL/health`) and Supabase configuration.
 *
 * `ok` reflects the frontend itself (always true if this handler ran).
 * `backend_up` reports whether the Python kernel actually answered within
 * the timeout — consumers should use it to show demo-mode vs live status.
 */
export async function GET() {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 3000);

  let backendUp = false;
  try {
    const res = await fetch(`${AEON_URL}/health`, {
      signal: controller.signal,
      cache: "no-store",
    });
    backendUp = res.ok;
  } catch {
    backendUp = false;
  } finally {
    clearTimeout(timeout);
  }

  const supabaseConfigured = Boolean(
    process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL
  );

  return NextResponse.json({
    ok: true,
    ts: Date.now(),
    // Legacy label kept for existing consumers; derived from configured env.
    backend: process.env.AEON_HF_SPACE_URL ? "aeon-kernel" : "hf-inference",
    backend_up: backendUp,
    supabase_configured: supabaseConfigured,
  });
}
