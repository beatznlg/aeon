import { callLLM } from "@/lib/llm";
import { APPS } from "@/lib/apps";
import { auth } from "@/auth";
import { logAudit } from "@/lib/audit";
import { kernelAppChat, pythonUrl } from "@/lib/kernel";
import { logUsage } from "@/lib/usage";
import { extractUserText, uiMessageError, uiMessageStream } from "@/lib/chat-stream";
import type { ChatRequestBody } from "@/lib/chat-stream";

export const maxDuration = 120;

/**
 * Build a system prompt tailored to the selected AEON OS module.
 * This gives the LLM the module’s identity, tools, and goals so that
 * responses are vertical-aware.
 */
function buildSystemPrompt(appId: string): string {
  const app = APPS.find((a) => a.id === appId);
  const name = app?.name ?? appId.replace(/_/g, " ");
  const description = app?.description ?? `AEON OS ${appId} module`;
  const tools = app?.allowed_tools?.join(", ") ?? "none";
  const goals =
    app?.default_goals?.map((g: { title: string }) => `• ${g.title}`).join("\n") ?? "none";

  return `You are AEON OS operating in the ${name} vertical.

Module description:
${description}

Allowed tools for this module:
${tools}

Default module goals:
${goals}

Respond as a helpful, concise AI agent. Whenever useful, reference the module's tools and goals in your answer.`;
}

export async function POST(req: Request, context: { params: Promise<{ id: string }> }) {
  const params = await context.params;
  const appId = params.id;
  let body: ChatRequestBody = {};
  try {
    body = (await req.json()) as ChatRequestBody;
  } catch {
    return uiMessageError("Invalid request body");
  }
  const prompt = extractUserText(body);
  const messageId = typeof body.id === "string" ? body.id : undefined;
  // Allow clients to request a specific provider at runtime. Falls back to
  // the AEON_LLM_PROVIDER env default (which is OpenRouter by default).
  const providerOverride = req.headers.get("x-aeon-provider") || undefined;
  const session = await auth();

  if (!prompt) {
    return uiMessageError("No message text found", messageId);
  }

  const system = buildSystemPrompt(appId);
  const userId = (session?.user as any)?.id;
  const workspaceId = (session?.user as any)?.workspaceId;

  logAudit({
    userId,
    email: session?.user?.email ?? undefined,
    action: "CHAT",
    module: appId,
    metadata: { backend: "web", provider: providerOverride },
  });

  logUsage({
    userId,
    workspaceId,
    action: "chat",
    module: appId,
    quantity: 1,
  });

  try {
    // --- Route to the Python AEON kernel if configured ---
    if (pythonUrl()) {
      const kernelRes = await kernelAppChat(appId, prompt, system);
      if (kernelRes) {
        return uiMessageStream(
          kernelRes.data?.answer ?? "",
          messageId,
          { "x-aeon-backend": kernelRes.data?.backend ?? "aeon_python" }
        );
      }
    }

    // --- Fallback: TypeScript LLM bridge ---
    const { text, backend } = await callLLM(prompt, system, providerOverride);
    return uiMessageStream(text, messageId, { "x-aeon-backend": backend });
  } catch (err: any) {
    const message = err?.message || String(err);
    console.error(`[module-chat ${appId}]`, message);
    return uiMessageError(`AEON backend unreachable — ${message}`, messageId);
  }
}
