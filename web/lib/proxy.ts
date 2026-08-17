import { NextRequest } from "next/server";
import { BACKEND_DOWN_MESSAGE } from "@/lib/backend-status";

const AEON_PYTHON_URL = process.env.AEON_PYTHON_URL || "http://127.0.0.1:5000";

export interface ProxyOptions {
  backendPath: string;
}

/**
 * Forward an incoming Next.js App Router request to the AEON Python backend.
 * Forwards the Authorization header, Content-Type, query parameters, and body.
 * Returns 401 if the Authorization header is missing.
 */
export async function proxyApiRequest(
  request: NextRequest,
  { backendPath }: ProxyOptions
): Promise<Response> {
  const authHeader = request.headers.get("Authorization");
  if (!authHeader) {
    return Response.json({ ok: false, error: "unauthorized" }, { status: 401 });
  }

  const url = new URL(`${AEON_PYTHON_URL}${backendPath}`);
  const incomingUrl = new URL(request.url);
  incomingUrl.searchParams.forEach((value, key) => {
    url.searchParams.set(key, value);
  });

  const headers = new Headers();
  headers.set("Authorization", authHeader);
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
    // The Python backend is unreachable — return a structured response so
    // client pages can detect it and degrade gracefully instead of a raw 500.
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
