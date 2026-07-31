import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

function keyMeta(envName: string): { present: boolean; length: number } {
  const value = process.env[envName];
  return {
    present: Boolean(value && value.length > 0),
    length: value?.length || 0,
  };
}

function urlHost(envName: string): { present: boolean; host: string | null } {
  const value = process.env[envName];
  let host: string | null = null;
  if (value) {
    try {
      host = new URL(value).host;
    } catch {
      host = null;
    }
  }
  return { present: Boolean(value && value.length > 0), host };
}

export async function GET() {
  const keys = {
    openrouter_api_key: keyMeta("OPENROUTER_API_KEY"),
    huggingface_token: keyMeta("HUGGINGFACE_TOKEN"),
    supabase_url: urlHost("SUPABASE_URL"),
    next_public_supabase_url: urlHost("NEXT_PUBLIC_SUPABASE_URL"),
    aeon_hf_space_url: urlHost("AEON_HF_SPACE_URL"),
    gh_token: keyMeta("GH_TOKEN"),
  };

  const notes: string[] = [];
  const hasLLMKey =
    keys.openrouter_api_key.present ||
    keys.huggingface_token.present ||
    process.env.OPENAI_API_KEY ||
    process.env.ANTHROPIC_API_KEY;
  if (!hasLLMKey) {
    notes.push("No LLM API key configured — chat runs in stub mode");
  }
  if (!keys.next_public_supabase_url.present && !keys.supabase_url.present) {
    notes.push("Supabase not configured — memory will not persist");
  }

  return NextResponse.json({
    ok: true,
    backend: process.env.AEON_HF_SPACE_URL
      ? "aeon-kernel"
      : process.env.AEON_LLM_PROVIDER || "openrouter",
    keys,
    notes,
  });
}
