import { createClient } from "@supabase/supabase-js";
import { spawn } from "child_process";

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
 * browser-side useChat renders it as streamed text. We send a single chunk;
 * the SDK still treats it as "finished" once the stream closes.
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

/**
 * Spawn the AEON chat CLI and return its JSON output.
 * All LLM routing and provider selection is handled inside aeon_chat.py
 * based on the AEON_LLM_PROVIDER environment variable.
 */
function runAeonChat(query: string, system?: string): Promise<{ text: string; backend: string }> {
  return new Promise((resolve, reject) => {
    const args = ["aeon_chat.py", query, "--max-tokens", "512"];
    if (system) {
      args.push("--system", system);
    }
    const proc = spawn("python3", args, {
      cwd: process.cwd(),
      env: { ...process.env },
    });
    let stdout = "";
    let stderr = "";
    proc.stdout.on("data", (d) => { stdout += d.toString(); });
    proc.stderr.on("data", (d) => { stderr += d.toString(); });
    proc.on("close", (code) => {
      if (code !== 0) {
        return reject(new Error(stderr || "aeon chat process failed"));
      }
      // The CLI prints JSON as the last non-empty line.
      const lastLine = stdout.trim().split("\n").pop() || "";
      try {
        const parsed = JSON.parse(lastLine);
        resolve({ text: String(parsed.answer || parsed.text || ""), backend: String(parsed.backend || "unknown") });
      } catch (e) {
        reject(new Error("invalid JSON from aeon chat: " + lastLine));
      }
    });
    proc.on("error", reject);
  });
}

export async function POST(req: Request) {
  const { messages } = await req.json().catch(() => ({}));
  const last = messages?.[messages.length - 1];
  const prompt: string = last?.content ?? "";

  if (!prompt.trim()) {
    return new Response(
      JSON.stringify({ ok: false, error: "empty prompt" }),
      { status: 400, headers: { "Content-Type": "application/json" } },
    );
  }

  const sb = getSb();

  try {
    const { text, backend } = await runAeonChat(prompt);
    logTurn(sb, text, backend);
    return singleTextStream(text, backend);
  } catch (err: any) {
    const message = err?.message || String(err);
    return new Response(
      JSON.stringify({ ok: false, error: message }),
      { status: 503, headers: { "Content-Type": "application/json" } },
    );
  }
}
