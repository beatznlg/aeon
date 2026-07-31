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
          models: ["gpt-4o-mini", "gpt-4o"],
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
          models: ["claude-3-5-sonnet"],
          configured: false,
          active: false,
          env_var: "ANTHROPIC_API_KEY",
          desc: "Advanced AI with safety focus.",
        },
        {
          id: "ollama",
          name: "Ollama (Local)",
          icon: "🦙",
          color: "#8b5cf6",
          models: ["llama3", "mistral"],
          configured: true,
          active: false,
          env_var: "OLLAMA_BASE_URL",
          desc: "Run LLMs locally.",
        },
        {
          id: "hf",
          name: "Hugging Face",
          icon: "🤗",
          color: "#fbbf24",
          models: ["Qwen2.5-3B-Instruct"],
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
