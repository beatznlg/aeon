import { NextRequest } from "next/server";
import { extractUserText, uiMessageStream, uiMessageError, ChatRequestBody } from "@/lib/chat-stream";

const AEON_URL = process.env.AEON_PYTHON_URL || "http://127.0.0.1:5000";

export const maxDuration = 120;

export async function POST(req: NextRequest) {
  let body: ChatRequestBody = {};
  try {
    body = (await req.json()) as ChatRequestBody;
  } catch {
    return uiMessageError("Invalid request body");
  }

  const query = extractUserText(body);
  if (!query) {
    return uiMessageError("No message text found");
  }

  const messageId = typeof body.id === "string" ? body.id : undefined;

  // Optional per-request provider override (from localStorage / header).
  const providerHeader = req.headers.get("x-aeon-provider");
  const payload: Record<string, unknown> = { query };
  if (providerHeader) {
    payload.provider = providerHeader;
  }

  // Forward the browser JWT so Flask resolves the tenant/workspace.
  const authHeader = req.headers.get("authorization");
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (authHeader) {
    headers["Authorization"] = authHeader;
  }

  try {
    const res = await fetch(`${AEON_URL}/chat`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({ ok: false, error: "invalid JSON from backend" }));
    if (!res.ok || !data.ok) {
      return uiMessageError(String(data.error || `Backend error (${res.status})`), messageId);
    }
    const answer = data.data?.answer ?? "";
    if (!answer) {
      return uiMessageError("The backend returned an empty answer", messageId);
    }
    return uiMessageStream(answer, messageId, { "x-aeon-backend": data.backend || "aeon_python" });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    return uiMessageError(
      `AEON backend unreachable — ${message}. The demo account works with sample data; connect a provider in Connect Brain.`,
      messageId
    );
  }
}
