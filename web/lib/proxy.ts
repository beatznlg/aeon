import { NextRequest } from "next/server";
import { BACKEND_DOWN_MESSAGE } from "@/lib/backend-status";
import { backendSessionHeaders } from "@/lib/backend-session";
import { demoResponseForPath } from "@/lib/demo-data";

const AEON_PYTHON_URL = process.env.AEON_PYTHON_URL || "http://127.0.0.1:5000";

export interface ProxyOptions {
  backendPath: string;
}

/**
 * Forward an incoming Next.js App Router request to the AEON Python backend.
 * Forwards the Authorization header, Content-Type, query parameters, and body.
 *
 * When the backend is unreachable, GET requests that have demo data configured
 * return realistic demo content so the UI renders a populated workspace.
 */
export async function proxyApiRequest(
  request: NextRequest,
  { backendPath }: ProxyOptions
): Promise<Response> {
  const authHeader = request.headers.get("Authorization");

  const url = new URL(`${AEON_PYTHON_URL}${backendPath}`);
  const incomingUrl = new URL(request.url);
  incomingUrl.searchParams.forEach((value, key) => {
    url.searchParams.set(key, value);
  });

  const headers = new Headers();
  if (authHeader) {
    headers.set("Authorization", authHeader);
  }
  // Carry the authenticated NextAuth identity to the Python backend, which
  // resolves the tenant/workspace from X-User-* headers (or a service token).
  const sessionHeaders = await backendSessionHeaders();
  for (const [key, value] of Object.entries(sessionHeaders)) {
    if (!headers.has(key)) headers.set(key, value);
  }
  headers.set("Accept", "application/json");

  const contentType = request.headers.get("Content-Type");
  if (contentType) {
    headers.set("Content-Type", contentType);
  }

  let body: BodyInit | undefined;
  if (request.method !== "GET" && request.method !== "HEAD") {
    body = await request.arrayBuffer();
    if (!contentType) {
      headers.set("Content-Type", "application/json");
    }
  }

  let upstream: Response;
  try {
    upstream = await fetch(url.toString(), {
      method: request.method,
      headers,
      body,
    });
  } catch {
    // The Python backend is unreachable. Serve demo data for GET requests
    // that have a configured demo payload; otherwise return a structured
    // backend-down response so client pages degrade gracefully.
    if (request.method === "GET" || request.method === "HEAD") {
      const demo = demoResponseForPath(backendPath);
      if (demo) {
        return Response.json(demo.body, { status: demo.status });
      }
    }
    return Response.json(
      { ok: false, error: BACKEND_DOWN_MESSAGE, backend_down: true },
      { status: 502 }
    );
  }

  const responseBody = await upstream.arrayBuffer();
  const responseHeaders = new Headers();
  const responseContentType = upstream.headers.get("Content-Type");
  if (responseContentType) {
    responseHeaders.set("Content-Type", responseContentType);
  }

  return new Response(responseBody, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
}
