/**
 * AEON LLM Provider Bridge
 *
 * Calls LLM APIs directly via HTTP fetch so the chat route works on Vercel
 * (no Python subprocess needed). Supports OpenAI, Anthropic, HuggingFace,
 * and a stub provider for testing.
 */

export type LLMProvider = "openai" | "anthropic" | "hf" | "stub";

function getProvider(): LLMProvider {
  const p = (process.env.AEON_LLM_PROVIDER || "stub").toLowerCase() as LLMProvider;
  if (["openai", "anthropic", "hf", "stub"].includes(p)) return p;
  return "stub";
}

export interface LLMResponse {
  text: string;
  backend: string;
}

/**
 * Call the configured LLM provider with a prompt and optional system message,
 * returning the generated text and the backend identifier.
 */
export async function callLLM(
  prompt: string,
  system?: string,
): Promise<LLMResponse> {
  const provider = getProvider();

  switch (provider) {
    case "openai":
      return callOpenAI(prompt, system);
    case "anthropic":
      return callAnthropic(prompt, system);
    case "hf":
      return callHuggingFace(prompt, system);
    case "stub":
    default:
      return callStub(prompt);
  }
}

// ─── OpenAI ─────────────────────────────────────────────────────────────

async function callOpenAI(
  prompt: string,
  system?: string,
): Promise<LLMResponse> {
  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey) throw new Error("OPENAI_API_KEY is not set");

  const messages: Array<{ role: string; content: string }> = [];
  if (system) messages.push({ role: "system", content: system });
  messages.push({ role: "user", content: prompt });

  const res = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: "gpt-4o-mini",
      messages,
      max_tokens: 512,
      temperature: 0.7,
    }),
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`OpenAI API error ${res.status}: ${body}`);
  }

  const json = await res.json();
  const text = json.choices?.[0]?.message?.content || "";
  return { text, backend: "openai" };
}

// ─── Anthropic ──────────────────────────────────────────────────────────

async function callAnthropic(
  prompt: string,
  system?: string,
): Promise<LLMResponse> {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) throw new Error("ANTHROPIC_API_KEY is not set");

  const body: Record<string, unknown> = {
    model: "claude-3-haiku-20240307",
    max_tokens: 512,
    messages: [{ role: "user", content: prompt }],
  };
  if (system) body.system = system;

  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "x-api-key": apiKey,
      "anthropic-version": "2023-06-01",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const bodyText = await res.text().catch(() => "");
    throw new Error(`Anthropic API error ${res.status}: ${bodyText}`);
  }

  const json = await res.json();
  const text =
    json.content
      ?.map((c: { type: string; text: string }) =>
        c.type === "text" ? c.text : "",
      )
      .join("") || "";
  return { text, backend: "anthropic" };
}

// ─── HuggingFace ───────────────────────────────────────────────────────

async function callHuggingFace(
  prompt: string,
  _system?: string,
): Promise<LLMResponse> {
  const token = process.env.HUGGINGFACE_TOKEN;
  if (!token) throw new Error("HUGGINGFACE_TOKEN is not set");

  const model =
    process.env.HF_MODEL || "microsoft/Phi-3-mini-4k-instruct";

  const res = await fetch(
    `https://api-inference.huggingface.co/models/${model}/v1/chat/completions`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model,
        messages: [{ role: "user", content: prompt }],
        max_tokens: 512,
        temperature: 0.7,
      }),
    },
  );

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`HuggingFace API error ${res.status}: ${body}`);
  }

  const json = await res.json();
  const text = json.choices?.[0]?.message?.content || "";
  return { text, backend: "hf_" + model.split("/").pop() };
}

// ─── Stub ───────────────────────────────────────────────────────────────

async function callStub(prompt: string): Promise<LLMResponse> {
  const responses: Record<string, string> = {
    hello:
      "Hello! I'm AEON, your autonomous AI operating system. I can help you with cybersecurity, retail, manufacturing, professional services, tourism, health, transport, finance, cultural heritage, utilities, and SME business tools. How can I assist you today?",
    help: "AEON is running in stub mode. To enable real AI responses, set AEON_LLM_PROVIDER to 'openai' or 'anthropic' and provide the corresponding API key.",
    default:
      "I received your message. AEON is currently operating in stub mode — real LLM responses require an API key (OpenAI or Anthropic). For now, know that your request has been logged and processed by the AEON OS kernel.",
  };

  const lower = prompt.toLowerCase().trim();
  const text =
    Object.entries(responses).find(([key]) => lower.includes(key))?.[1] ||
    responses.default;

  return { text, backend: "stub" };
}
