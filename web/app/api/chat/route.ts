import { streamText } from "ai";
import { huggingface } from "@ai-sdk/huggingface";
import { Client } from "@gradio/client";
import { createClient } from "@supabase/supabase-js";

export const maxDuration = 60;

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

export async function POST(req: Request) {
  const { messages } = await req.json();
  const last = messages?.[messages.length - 1];
  const prompt: string = last?.content ?? "";

  const sb = getSb();

  // ── 1. AEON kernel proxy (preferred when AEON_HF_SPACE_URL is set) ──
  const spaceUrl = process.env.AEON_HF_SPACE_URL;
  if (spaceUrl) {
    try {
      const cleanUrl = spaceUrl.replace(/\/$/, "");
      const client = await Client.connect(cleanUrl);
      // /chat is the Gradio ChatInterface endpoint auto-created for fn=chat_fn.
      const stream = await client.submit("/chat", [prompt, []]);

      let fullText = "";
      const readable = new ReadableStream<Uint8Array>({
        async start(controller) {
          const enc = new TextEncoder();
          try {
            for await (const msg of stream) {
              // Gradio yields cumulative snapshots in msg.data[0]; slice off
              // the new tail and emit it as a Vercel AI SDK text part.
              if (msg.type === "data" && Array.isArray(msg.data) && msg.data[0]) {
                const next = String(msg.data[0]);
                const tail = next.slice(fullText.length);
                if (tail.length > 0) {
                  controller.enqueue(
                    enc.encode("0:" + JSON.stringify(tail) + "\n"),
                  );
                  fullText = next;
                }
              }
            }
            logTurn(sb, fullText, "aeon_kernel");
            controller.close();
          } catch (e) {
            controller.error(e);
          }
        },
      });

      return new Response(readable, {
        headers: {
          "Content-Type": "text/plain; charset=utf-8",
          "x-vercel-ai-data-stream": "v1",
        },
      });
    } catch (err) {
      // Fall through to HF Inference fallback below.
      console.error("[chat] GradIO proxy failed:", err);
    }
  }

  // ── 2. Fallback: HF Inference API direct via @ai-sdk/huggingface ────
  const result = streamText({
    model: huggingface("Qwen/Qwen2.5-3B-Instruct"),
    prompt,
    onFinish: (ev) => logTurn(sb, ev.text, "hf_inference"),
  });

  return result.toAIStreamResponse();
}
