/**
 * Chat stream helpers for the AI SDK v7 wire protocol.
 *
 * `useChat` from `@ai-sdk/react` posts `{ id, messages, ...body }` where each
 * message is parts-based (`UIMessage.parts`), and expects the response as a
 * stream of newline-delimited `data: {"type": ...}` JSON chunks:
 *
 *   data: {"type":"start","messageId":"..."}
 *   data: {"type":"text-start","id":"..."}
 *   data: {"type":"text-delta","id":"...","delta":"..."}
 *   data: {"type":"text-end","id":"..."}
 *   data: {"type":"finish","finishReason":"stop"}
 *
 * These helpers keep both chat routes (global + module) on that contract.
 */

interface ChatPart {
  type?: string;
  text?: string;
}

interface ChatMessageLike {
  role?: string;
  content?: string;
  parts?: ChatPart[];
}

export interface ChatRequestBody {
  id?: string;
  query?: string;
  messages?: ChatMessageLike[];
}

/** Extract the latest user text from an AI SDK v7 (or legacy) request body. */
export function extractUserText(body: ChatRequestBody): string {
  if (typeof body.query === "string" && body.query.trim()) {
    return body.query.trim();
  }
  const messages = Array.isArray(body.messages) ? body.messages : [];
  for (let i = messages.length - 1; i >= 0; i--) {
    const message = messages[i];
    if (!message || message.role !== "user") continue;
    // AI SDK v7: parts-based
    if (Array.isArray(message.parts) && message.parts.length > 0) {
      const text = message.parts
        .filter((part) => part.type === "text" && typeof part.text === "string")
        .map((part) => part.text as string)
        .join("");
      if (text.trim()) return text.trim();
    }
    // Legacy: plain content
    if (typeof message.content === "string" && message.content.trim()) {
      return message.content.trim();
    }
  }
  return "";
}

function encode(lines: unknown[]): string {
  return lines
    .map((line) => `data: ${JSON.stringify(line)}\n\n`)
    .join("");
}

/** Build a valid AI SDK v7 stream response for a completed answer. */
export function uiMessageStream(
  text: string,
  messageId?: string,
  extra?: Record<string, string>
): Response {
  const id = messageId || `msg-${Date.now()}`;
  const body = encode([
    { type: "start", messageId: id },
    { type: "text-start", id },
    { type: "text-delta", id, delta: text },
    { type: "text-end", id },
    { type: "finish", finishReason: "stop" },
  ]);
  return new Response(body, {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "no-cache",
      ...(extra || {}),
    },
  });
}

/** Build a valid AI SDK v7 stream response that surfaces an error. */
export function uiMessageError(message: string, messageId?: string): Response {
  const id = messageId || `msg-${Date.now()}`;
  const body = encode([
    { type: "start", messageId: id },
    { type: "text-start", id },
    { type: "text-delta", id, delta: `⚠️ ${message}` },
    { type: "text-end", id },
    { type: "finish", finishReason: "error" },
  ]);
  return new Response(body, {
    status: 200,
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "no-cache",
    },
  });
}
