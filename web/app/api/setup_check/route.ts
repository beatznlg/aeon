import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

/**
 * GET /api/setup_check
 *
 * Reports non-secret deployment configuration state. Values themselves are
 * never returned. This endpoint is intentionally provider-agnostic so an
 * Oracle-only deployment does not expose legacy hosting dependencies.
 */
function safe(value: string | undefined) {
  if (!value) return { present: false, length: 0 };
  return { present: true, length: value.length };
}

function hostOf(url: string | undefined) {
  if (!url) return null;
  try {
    return new URL(url).host;
  } catch {
    return null;
  }
}

export async function GET() {
  const HF = process.env.HUGGINGFACE_TOKEN;
  const SPACE_URL = process.env.AEON_HF_SPACE_URL;
  const GH = process.env.GH_TOKEN;
  const REDIS = process.env.AEON_REDIS_URL;
  const DB = process.env.AEON_DATABASE_URL;
  const LLM = process.env.AEON_LLM_PROVIDER || "stub";
  const DOMAIN = process.env.NEXTAUTH_URL;

  const notes: string[] = [];
  if (!DB) notes.push("AEON_DATABASE_URL missing — database connectivity must be supplied by the Oracle stack.");
  if (!REDIS) notes.push("AEON_REDIS_URL missing — production background workers require Redis.");
  if (!HF && ["hf", "huggingface"].includes(LLM.toLowerCase()))
    notes.push("HUGGINGFACE_TOKEN missing for the selected Hugging Face provider.");
  if (!DOMAIN) notes.push("NEXTAUTH_URL missing — configure the public Oracle domain or IP before production login.");
  if (!GH) notes.push("GH_TOKEN missing — GitHub integration may use unauthenticated API limits.");

  return NextResponse.json({
    ok: true,
    ts: Date.now(),
    deployment: "oracle-self-hosted",
    llm_provider: LLM,
    keys: {
      huggingface_token: safe(HF),
      github_token: safe(GH),
      redis_url: { present: !!REDIS },
      database_url: { present: !!DB, host: hostOf(DB) },
      public_url: { present: !!DOMAIN, host: hostOf(DOMAIN) },
      hf_space_url: { present: !!SPACE_URL, host: hostOf(SPACE_URL) },
    },
    notes,
  });
}
