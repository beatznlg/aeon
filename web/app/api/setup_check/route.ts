import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

/**
 * GET /api/setup_check
 *
 * Reports which optional environment variables are wired on the deployed
 * Vercel instance. NEVER echoes the secret value itself — only whether it
 * exists and a low-risk length hint so the user can confirm
 * "looks like 40+ chars" without seeing the string.
 *
 * Returns:
 *   {
 *     ok: true,
 *     ts: <ms>,
 *     backend: "aeon-kernel" | "hf-inference",
 *     keys: {
 *       huggingface_token:       {present, length},
 *       supabase_url:            {present, host},
 *       next_public_supabase_url:{present, host},
 *       aeon_hf_space_url:       {present, host},
 *       gh_token:                {present, length}
 *     },
 *     notes: string[]
 *   }
 */
function safe(value: string | undefined) {
  if (!value) return { present: false, length: 0 };
  return { present: true, length: value.length };
}

function hostOf(url: string | undefined) {
  if (!url) return null;
  try {
    const u = new URL(url);
    return u.host;
  } catch {
    return null;
  }
}

export async function GET() {
  const HF = process.env.HUGGINGFACE_TOKEN;
  const SB_URL = process.env.SUPABASE_URL;
  const PUBLIC_SB_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const SPACE_URL = process.env.AEON_HF_SPACE_URL;
  const GH = process.env.GH_TOKEN;

  const notes: string[] = [];
  if (!HF)
    notes.push(
      "HUGGINGFACE_TOKEN missing — /api/chat will fall back to HF Inference direct but no Qwen-3B-on-GPU without it."
    );
  if (!SPACE_URL)
    notes.push(
      "AEON_HF_SPACE_URL missing — /api/chat will use the HF Inference API direct path (high rate-limit exposure, no AEON tools)."
    );
  if (!SB_URL && !PUBLIC_SB_URL)
    notes.push(
      "SUPABASE_URL + NEXT_PUBLIC_SUPABASE_URL both missing — Memory panel will be empty."
    );
  if (!GH) notes.push("GH_TOKEN missing — GitHub code search capped at 10/min/IP.");

  return NextResponse.json({
    ok: true,
    ts: Date.now(),
    backend: SPACE_URL ? "aeon-kernel" : "hf-inference",
    keys: {
      huggingface_token: safe(HF),
      supabase_url: { present: !!SB_URL, host: hostOf(SB_URL) },
      next_public_supabase_url: {
        present: !!PUBLIC_SB_URL,
        host: hostOf(PUBLIC_SB_URL),
      },
      aeon_hf_space_url: {
        present: !!SPACE_URL,
        host: hostOf(SPACE_URL),
      },
      gh_token: safe(GH),
    },
    notes,
  });
}
