import { createClient } from "@supabase/supabase-js";
import { callLLM } from "@/lib/llm";
import { auth } from "@/auth";
import { logAudit } from "@/lib/audit";
import { kernelChat, pythonUrl } from "@/lib/kernel";
import { logUsage } from "@/lib/usage";

export const maxDuration = 120;

/**
 * Server-side Supabase client for write-side logging.
 * Prefers the service-role key (server-only). Falls back to the anon key
 * which is NEXT_PUBLIC_* — fine for server-side use.
 */
function getSb() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key =
    process.env.SUPABASE_SERVICE_ROLE_KEY ??
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key) return null;
  return createClient(url, key, { auth: { persistSession: false } });
}

/**
 * Fire-and-forget insert. Errors are swallowed — logging must never break
 * the chat round-trip.
 */
function logTurn(sb: ReturnType<typeof getSb>, text: string, backend: string) {
  if (!sb) return;
  sb.from("episodes")
    .insert([
      {
        ts: Date.now() / 1000,
        kind: "bot",
        text: String(text).slice(0, 2000),
        ref: "web_api_" + backend,
      },
    ])
    .then(() => {}, () => {});
}

/**
 * Wrap a single final string into a Vercel AI Data Stream response so the
 * browser-side useChat renders it as streamed text.
 */
function singleTextStream(text: string, backend: string): Response {
  const enc = new TextEncoder();
  const readable = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(
        enc.encode("0:" + JSON.stringify(text) + "\n"),
      );
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

export async function POST(req: Request) {
  const { messages } = await req.json().catch(() => ({}));
  const last = messages?.[messages.length - 1];
  const prompt: string = last?.content ?? "";
  // Allow clients to request a specific provider at runtime (e.g. from
  // a UI selector stored in localStorage). Falls back to env default.
  const providerOverride = req.headers.get("x-aeon-provider") || undefined;
  const session = await auth();

  if (!prompt.trim()) {
    return new Response(
      JSON.stringify({ ok: false, error: "empty prompt" }),
      { status: 400, headers: { "Content-Type": "application/json" } },
    );
  }

  const sb = getSb();

  const userId = (session?.user as any)?.id;
  const workspaceId = (session?.user as any)?.workspaceId;

  logAudit({
    userId,
    email: session?.user?.email ?? undefined,
    action: "CHAT",
    module: "global",
    metadata: { backend: "web", provider: providerOverride },
  });

  logUsage({
    userId,
    workspaceId,
    action: "chat",
    module: "global",
    quantity: 1,
  });

  try {
    // --- Route to the Python AEON kernel if configured ---
    if (pythonUrl()) {
      const kernelRes = await kernelChat(prompt);
      if (kernelRes) {
        const text = kernelRes.data?.answer ?? "";
        const backend = kernelRes.data?.backend ?? "aeon_python";
        logTurn(sb, text, backend);
        return singleTextStream(text, backend);
      }
    }

    // --- Fallback: TypeScript LLM bridge ---
    const { text, backend } = await callLLM(prompt, undefined, providerOverride);
    logTurn(sb, text, backend);
    return singleTextStream(text, backend);
  } catch (err: any) {
    const message = err?.message || String(err);
    console.error("chat error:", message);
    return new Response(
      JSON.stringify({ ok: false, error: message }),
      { status: 503, headers: { "Content-Type": "application/json" } },
    );
  }
}
