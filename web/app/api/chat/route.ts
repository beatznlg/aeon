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

/**
 * Wrap a single final string into a Vercel AI Data Stream response so the
 * browser-side useChat renders it as streamed text. We send a single chunk;
 * the SDK still treats it as "finished" once the stream closes.
 */
function singleTextStream(text: string): Response {
  const enc = new TextEncoder();
  const readable = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(enc.encode("0:" + JSON.stringify(text) + "\n"));
      controller.close();
    },
  });
  return new Response(readable, {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "x-vercel-ai-data-stream": "v1",
    },
  });
}

/**
 * AEON kernel closed-loop (Vercel → HF Space → AeonKernel) status:
 * temporarily disabled — see README for the migration plan.
 * `AEON_HF_SPACE_URL` is still accepted from env so the DeployGuidePanel
 * can confirm wiring; we just hand off to the HF Inference fallback until
 * the raw SSE client is shipped.
 */
function aeonSpaceReachable(): boolean {
  return !!process.env.AEON_HF_SPACE_URL;
}

export async function POST(req: Request) {
  const { messages } = await req.json().catch(() => ({}));
  const last = messages?.[messages.length - 1];
  const prompt: string = last?.content ?? "";

  const sb = getSb();
  const hfToken = process.env.HUGGINGFACE_TOKEN;

  // Closed-loop was wired through @gradio/client but the npm package version
  // we pinned (^0.6.0) is no longer the active line; the `Client` named export
  // was removed. Until we ship a raw-SSE replacement, fall through to the
  // HF Inference fallback rather than throw a 500.
  if (aeonSpaceReachable() && !hfToken) {
    // Both set: closed loop desired, but the client package is broken. We pick
    // the most useful surface: log that the closed loop is offline and use the
    // HF Inference API as the chat backend.
    console.warn(
      "[chat] AEON_HF_SPACE_URL is set but @gradio/client is currently " +
        "unavailable in this build; falling back to HF Inference API. " +
        "Set HUGGINGFACE_TOKEN or wait for the raw-SSE rewrite.",
    );
  }

  // No backend wired → graceful 503 so the UI shows the DeployGuidePanel
  // instead of a hard 500.
  if (!hfToken) {
    return new Response(
      JSON.stringify({
        ok: false,
        error:
          "No inference backend wired. Set AEON_HF_SPACE_URL (closed-loop) and/or HUGGINGFACE_TOKEN (HF Inference).",
      }),
      { status: 503, headers: { "Content-Type": "application/json" } },
    );
  }

  // ── Fallback: raw fetch to HF Inference API ─────────────────────────
  try {
    const res = await fetch(
      "https://api-inference.huggingface.co/models/Qwen/Qwen2.5-3B-Instruct",
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${hfToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ inputs: prompt }),
      },
    );

    if (!res.ok) {
      const errText = await res.text().catch(() => "");
      return new Response(
        JSON.stringify({
          ok: false,
          error: `HF Inference HTTP ${res.status}: ${errText.slice(0, 400)}`,
        }),
        { status: 503, headers: { "Content-Type": "application/json" } },
      );
    }

    const data =
      (await res.json()) as Array<{ generated_text?: string }> | any;
    const generated =
      Array.isArray(data) && data[0]?.generated_text
        ? String(data[0].generated_text)
        : "(empty response from Qwen-3B HF Inference)";
    logTurn(sb, generated, "hf_inference");
    return singleTextStream(generated);
  } catch (err: any) {
    return new Response(
      JSON.stringify({
        ok: false,
        error: `HF fallback crashed: ${err?.message || err}`,
      }),
      { status: 503, headers: { "Content-Type": "application/json" } },
    );
  }
}
