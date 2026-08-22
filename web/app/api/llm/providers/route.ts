import { NextResponse } from "next/server";
import { auth } from "@/auth";

const AEON_URL = process.env.AEON_PYTHON_URL || "http://127.0.0.1:5000";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const session = await auth();
    const headers: Record<string, string> = { "Content-Type": "application/json" };

    // Forward the session JWT to Flask for authentication
    if (session?.user && (session.user as any)?.token) {
      headers["Authorization"] = `Bearer ${(session.user as any).token}`;
    }

    const res = await fetch(`${AEON_URL}/llm/providers`, { headers, cache: "no-store" });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (err: any) {
    // If Flask is not running, return a static list so the UI still works
    return NextResponse.json({
      ok: true,
      providers: [
        {
          id: "stub",
          name: "Stub (No AI)",
          icon: "◇",
          color: "#71717a",
          models: ["deterministic stub"],
          configured: true,
          active: true,
          env_var: null,
          desc: "Fallback mode for testing.",
        },
        {
          id: "openai",
          name: "OpenAI",
          icon: "⚡",
          color: "#10a37f",
          models: ["gpt-5.6", "gpt-5-mini", "gpt-4.1", "gpt-4.1-mini", "o3-pro", "gpt-realtime-mini"],
          configured: false,
          active: false,
          env_var: "OPENAI_API_KEY",
          desc: "Industry-leading language models.",
        },
        {
          id: "anthropic",
          name: "Anthropic (Claude)",
          icon: "✦",
          color: "#d97706",
          models: ["claude-opus-4-1", "claude-sonnet-4-20250514", "claude-3-7-sonnet-latest", "claude-3-5-haiku-latest"],
          configured: false,
          active: false,
          env_var: "ANTHROPIC_API_KEY",
          desc: "Advanced AI with safety focus.",
        },
        {
          id: "google",
          name: "Google Gemini",
          icon: "✦",
          color: "#4285f4",
          models: ["gemini-3.7-flash", "gemini-3.1-pro", "gemini-3.1-flash-lite"],
          configured: false,
          active: false,
          env_var: "GEMINI_API_KEY",
          desc: "Gemini models through Google's OpenAI-compatible endpoint.",
        },
        {
          id: "mistral",
          name: "Mistral",
          icon: "◆",
          color: "#f97316",
          models: ["mistral-large-latest", "mistral-medium-latest", "mistral-small-latest", "codestral-latest"],
          configured: false,
          active: false,
          env_var: "MISTRAL_API_KEY",
          desc: "Hosted Mistral and Codestral models.",
        },
        {
          id: "openrouter",
          name: "OpenRouter",
          icon: "◈",
          color: "#7c3aed",
          models: ["openai/gpt-4.1-mini", "anthropic/claude-sonnet-4", "google/gemini-3.7-flash", "meta-llama/llama-4-scout"],
          configured: false,
          active: false,
          env_var: "OPENROUTER_API_KEY",
          desc: "Route across hosted and open models with one API.",
        },
        {
          id: "ollama",
          name: "Ollama (Local)",
          icon: "🦙",
          color: "#8b5cf6",
          models: ["llama3.1", "qwen2.5", "gemma3", "mistral"],
          configured: true,
          active: false,
          env_var: "OLLAMA_BASE_URL",
          desc: "Run LLMs locally.",
        },
        {
          id: "lmstudio",
          name: "LM Studio (Local)",
          icon: "⌘",
          color: "#14b8a6",
          models: ["local-model"],
          configured: true,
          active: false,
          env_var: "LM_STUDIO_BASE_URL",
          desc: "Use a model loaded in LM Studio.",
        },
        {
          id: "vllm",
          name: "vLLM (Private)",
          icon: "▣",
          color: "#0ea5e9",
          models: ["served-model"],
          configured: true,
          active: false,
          env_var: "VLLM_BASE_URL",
          desc: "Connect to a self-hosted vLLM server.",
        },
        {
          id: "pollinations",
          name: "Free (Pollinations)",
          icon: "✦",
          color: "#00a8ff",
          models: ["openai-fast"],
          configured: true,
          active: false,
          env_var: null,
          desc: "Genuinely free hosted AI — no API key required. Rate-limited.",
        },
        {
          id: "custom",
          name: "Custom OpenAI-Compatible",
          icon: "✚",
          color: "#22c55e",
          models: ["custom-model"],
          configured: false,
          active: false,
          env_var: "AEON_CUSTOM_LLM_API_KEY",
          base_url_env: "AEON_CUSTOM_LLM_BASE_URL",
          model_env_var: "AEON_CUSTOM_LLM_MODEL",
          desc: "Connect any hosted API or local /v1/chat/completions server.",
        },
        {
          id: "hf",
          name: "Hugging Face",
          icon: "🤗",
          color: "#fbbf24",
          models: ["Qwen/Qwen2.5-7B-Instruct", "meta-llama/Llama-3.1-8B-Instruct", "mistralai/Mistral-7B-Instruct-v0.3"],
          configured: false,
          active: false,
          env_var: "HUGGINGFACE_TOKEN",
          desc: "Open-source models via HF API.",
        },
        {
          id: "qwen",
          name: "Qwen Local (GPU)",
          icon: "🧠",
          color: "#6366f1",
          models: ["Qwen2.5-3B (quantized)"],
          configured: true,
          active: false,
          env_var: null,
          desc: "Built-in GPU model.",
        },
      ],
    });
  }
}
