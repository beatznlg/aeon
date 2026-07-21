import { callLLM } from "@/lib/llm";
import { APPS } from "@/lib/apps";

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
  const goals = app?.default_goals
    ?.map((g: { title: string }) => `• ${g.title}`)
    .join("\n") ?? "none";

  return `You are AEON OS operating in the ${name} vertical.

Module description:
${description}

Allowed tools for this module:
${tools}

Default module goals:
${goals}

Respond as a helpful, concise AI agent. Whenever useful, reference the module's tools and goals in your answer.`;
}

/**
 * Split text into small word-group chunks while preserving whitespace and
 * line breaks. This lets the browser render text as if it were being typed
 * in real time.
 */
function chunkText(text: string, wordsPerChunk = 2): string[] {
  const tokens = text.split(/(\s+)/).filter(Boolean);
  const chunks: string[] = [];
  let buffer = "";
  let wordCount = 0;

  for (const token of tokens) {
    buffer += token;
    if (/\S/.test(token)) {
      wordCount += 1;
    }
    if (wordCount >= wordsPerChunk) {
      chunks.push(buffer);
      buffer = "";
      wordCount = 0;
    }
  }

  if (buffer) chunks.push(buffer);
  return chunks;
}

/**
 * Stream a full text response as a Vercel AI Data Stream.
 * Each chunk is emitted as: 0:<JSON-string>
 */
function streamResponse(text: string, backend: string): Response {
  const encoder = new TextEncoder();
  const chunks = chunkText(text, 2);

  const readable = new ReadableStream<Uint8Array>({
    async start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(`0:${JSON.stringify(chunk)}\n`));
        await new Promise((resolve) => setTimeout(resolve, 10));
      }
      controller.close();
    },
  });

  return new Response(readable, {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "x-vercel-ai-data-stream": "v1",
      "x-aeon-backend": backend,
    },
  });
}

export async function POST(
  req: Request,
  { params }: { params: { id: string } },
) {
  const appId = params.id;
  const { messages } = (await req.json().catch(() => ({ messages: [] }))) as {
    messages?: { role: string; content: string }[];
  };
  const last = messages?.[messages.length - 1];
  const prompt = last?.content ?? "";

  if (!prompt.trim()) {
    return new Response(JSON.stringify({ ok: false, error: "empty prompt" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  const system = buildSystemPrompt(appId);

  try {
    const { text, backend } = await callLLM(prompt, system);
    return streamResponse(text, backend);
  } catch (err: any) {
    const message = err?.message || String(err);
    console.error(`[module-chat ${appId}]`, message);
    return new Response(JSON.stringify({ ok: false, error: message }), {
      status: 503,
      headers: { "Content-Type": "application/json" },
    });
  }
}
