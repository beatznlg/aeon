import type { UIMessage } from "@ai-sdk/react";

/**
 * AI SDK v7 messages are parts-based (`UIMessage.parts`), so plain text is
 * spread across one or more `text` parts. This joins them for rendering and
 * for callbacks that expect a plain string (e.g. memory writes).
 */
export function messageText(message: UIMessage): string {
  return message.parts
    .filter((part) => part.type === "text")
    .map((part) => part.text)
    .join("");
}
