/**
 * Helpers to detect and describe AEON backend (Python control plane) outages
 * so pages can degrade gracefully instead of showing raw errors or a blank UI.
 *
 * These are client-safe (no server-only imports).
 */

export const BACKEND_DOWN_TITLE = "Control plane offline";

export const BACKEND_DOWN_MESSAGE =
  "The AEON control plane (Python backend) is offline. Live data is temporarily unavailable, but the rest of the app still works.";

const DOWN_MARKERS = [
  "backend unreachable",
  "aeon backend",
  "control plane offline",
  "backend_down",
  "fetch failed",
  "failed to fetch",
  "networkerror",
  "econnrefused",
  "connection lost",
  "sector api error (5",
];

/**
 * True when an error message/object indicates the backend is unreachable
 * (as opposed to a normal application error like a 400 or 404).
 */
export function isBackendDownError(error: string | Error | null | undefined): boolean {
  if (!error) return false;
  const raw = error instanceof Error ? error.message : String(error);
  const s = raw.toLowerCase();
  return DOWN_MARKERS.some((marker) => s.includes(marker));
}

/**
 * True when an HTTP response from a Next.js API route indicates the backend
 * is unreachable. Also inspects the parsed JSON body for a backend_down flag
 * or a matching error message.
 */
export function isBackendDown(res: Response, data?: any): boolean {
  if (res.status === 502 || res.status === 503) return true;
  const raw = data?.error || data?.message;
  return isBackendDownError(raw);
}

/**
 * Return a friendly, human-readable error for an API response, using the
 * backend-offline message when the backend is down.
 */
export function describeError(res: Response, data?: any, fallback = "Request failed"): string {
  if (isBackendDown(res, data)) return BACKEND_DOWN_MESSAGE;
  const raw = data?.error || data?.message;
  return raw ? String(raw) : fallback;
}
