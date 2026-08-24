import { NextRequest, NextResponse } from "next/server";
import { backendSessionHeaders } from "@/lib/backend-session";
import { demoResponseForPath } from "@/lib/demo-data";

const AEON_URL = (process.env.AEON_PYTHON_URL || "http://127.0.0.1:5000").replace(/\/$/, "");

/**
 * Upstream request budget. Without this, a sleeping/hung backend (e.g. Render
 * free tier) hangs every API route until the platform limit kills it.
 * Override with AEON_PROXY_TIMEOUT_MS; set to 0 to disable.
 */
function upstreamTimeoutMs(): number {
  const raw = Number(process.env.AEON_PROXY_TIMEOUT_MS);
  return Number.isFinite(raw) && raw > 0 ? raw : 45000;
}

/**
 * Fetch from the Flask backend with a demo-data fallback.
 *
 * For GET requests, when the backend is unreachable and demo data is
 * configured for the given backend path, returns the demo payload so the UI
 * renders a populated workspace. POST/PATCH/DELETE return a structured
 * backend-down response.
 */
export async function backendFetch(
  req: NextRequest,
  backendPath: string,
  init?: RequestInit
): Promise<Response> {
  const method = init?.method || req.method || "GET";
  const url = new URL(`${AEON_URL}${backendPath}`);
  const incomingUrl = new URL(req.url);
  incomingUrl.searchParams.forEach((value, key) => {
    url.searchParams.set(key, value);
  });

  const headers = new Headers(init?.headers || {});
  const authHeader = req.headers.get("Authorization");
  if (authHeader && !headers.has("Authorization")) {
    headers.set("Authorization", authHeader);
  }
  // Carry the authenticated NextAuth identity to the Python backend, which
  // resolves the tenant/workspace from X-User-* headers (or a service token).
  const sessionHeaders = await backendSessionHeaders();
  for (const [key, value] of Object.entries(sessionHeaders)) {
    if (!headers.has(key)) headers.set(key, value);
  }
  if (!headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }
  const contentType = req.headers.get("Content-Type");
  if (contentType && !headers.has("Content-Type")) {
    headers.set("Content-Type", contentType);
  }

  let body: BodyInit | undefined;
  if (init?.body) {
    body = init.body;
  } else if (method !== "GET" && method !== "HEAD") {
    body = await req.arrayBuffer();
    if (!contentType) {
      headers.set("Content-Type", "application/json");
    }
  }

  try {
    const res = await fetch(url.toString(), {
      ...init,
      method,
      headers,
      body,
      signal: AbortSignal.timeout(upstreamTimeoutMs()),
    });
    const text = await res.text();
    let data: unknown;
    try {
      data = JSON.parse(text);
    } catch {
      data = { message: text };
    }
    return NextResponse.json(data, { status: res.status });
  } catch {
    // Backend unreachable — serve demo data for GET, structured error otherwise.
    if (method === "GET" || method === "HEAD") {
      const demo = demoResponseForPath(backendPath);
      if (demo) {
        return NextResponse.json(demo.body, { status: demo.status });
      }
    }
    return NextResponse.json(
      { ok: false, error: "AEON backend unreachable", backend_down: true },
      { status: 502 }
    );
  }
}
