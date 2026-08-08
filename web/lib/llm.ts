/**
 * AEON server-side LLM bridge.
 *
 * API keys are read only on the server. Provider/model overrides are identifiers
 * supplied by the caller; credentials and endpoint URLs are never accepted
 * from the browser.
 */

export type LLMProvider =
  | "openai"
  | "anthropic"
  | "google"
  | "mistral"
  | "hf"
  | "openrouter"
  | "ollama"
  | "lmstudio"
  | "vllm"
  | "custom"
  | "stub";

export const DEFAULT_PROVIDER: LLMProvider = "openrouter";

function isValidProvider(value: string): value is LLMProvider {
  return [
    "openai",
    "anthropic",
    "google",
    "mistral",
    "hf",
    "openrouter",
    "ollama",
    "lmstudio",
    "vllm",
    "custom",
    "stub",
  ].includes(value);
}

function getProvider(value?: string): LLMProvider {
  const candidate = (value || process.env.AEON_LLM_PROVIDER || DEFAULT_PROVIDER).toLowerCase();
  return isValidProvider(candidate) ? candidate : DEFAULT_PROVIDER;
}

function getModel(provider: LLMProvider, override?: string): string {
  if (override?.trim()) return override.trim();
  const envByProvider: Partial<Record<LLMProvider, string | undefined>> = {
    openai: process.env.OPENAI_MODEL || process.env.AEON_LLM_MODEL || "gpt-5-mini",
    anthropic: process.env.ANTHROPIC_MODEL || process.env.AEON_LLM_MODEL || "claude-sonnet-4-20250514",
    google: process.env.GEMINI_MODEL || process.env.AEON_LLM_MODEL || "gemini-2.5-flash",
    mistral: process.env.MISTRAL_MODEL || process.env.AEON_LLM_MODEL || "mistral-small-latest",
    hf: process.env.HF_MODEL || process.env.AEON_LLM_MODEL || "Qwen/Qwen2.5-7B-Instruct",
    openrouter: process.env.OPENROUTER_MODEL || process.env.AEON_LLM_MODEL || "openai/gpt-4.1-mini",
    ollama: process.env.OLLAMA_MODEL || process.env.AEON_LLM_MODEL || "llama3.1",
    lmstudio: process.env.LM_STUDIO_MODEL || process.env.AEON_LLM_MODEL || "local-model",
    vllm: process.env.VLLM_MODEL || process.env.AEON_LLM_MODEL || "served-model",
    custom: process.env.AEON_CUSTOM_LLM_MODEL || process.env.AEON_LLM_MODEL || "custom-model",
    stub: "deterministic stub",
  };
  return envByProvider[provider] || "custom-model";
}

function messages(prompt: string, system?: string): Array<{ role: string; content: string }> {
  return [...(system ? [{ role: "system", content: system }] : []), { role: "user", content: prompt }];
}

function compatibleBaseUrl(provider: LLMProvider): string {
  const values: Partial<Record<LLMProvider, string | undefined>> = {
    openai: process.env.OPENAI_BASE_URL || "https://api.openai.com/v1",
    google: process.env.GEMINI_BASE_URL || "https://generativelanguage.googleapis.com/v1beta/openai",
    mistral: process.env.MISTRAL_BASE_URL || "https://api.mistral.ai/v1",
    hf: process.env.HF_OPENAI_BASE_URL || "https://router.huggingface.co/v1",
    openrouter: process.env.OPENROUTER_BASE_URL || "https://openrouter.ai/api/v1",
    ollama: process.env.OLLAMA_OPENAI_BASE_URL || `${(process.env.OLLAMA_BASE_URL || "http://127.0.0.1:11434").replace(/\/$/, "")}/v1`,
    lmstudio: process.env.LM_STUDIO_BASE_URL || "http://127.0.0.1:1234/v1",
    vllm: process.env.VLLM_BASE_URL || "http://127.0.0.1:8000/v1",
    custom: process.env.AEON_CUSTOM_LLM_BASE_URL || process.env.AEON_LLM_BASE_URL || "",
  };
  const base = values[provider];
  if (!base) throw new Error("custom LLM endpoint is not configured on the server");
  const normalized = base.replace(/\/$/, "");
  return normalized.endsWith("/chat/completions") ? normalized : `${normalized}/chat/completions`;
}

function apiKey(provider: LLMProvider): string | undefined {
  const values: Partial<Record<LLMProvider, string | undefined>> = {
    openai: process.env.OPENAI_API_KEY,
    google: process.env.GEMINI_API_KEY,
    mistral: process.env.MISTRAL_API_KEY,
    hf: process.env.HUGGINGFACE_TOKEN,
    openrouter: process.env.OPENROUTER_API_KEY,
    ollama: process.env.OLLAMA_API_KEY,
    vllm: process.env.VLLM_API_KEY,
    custom: process.env.AEON_CUSTOM_LLM_API_KEY || process.env.CUSTOM_LLM_API_KEY,
  };
  return values[provider];
}

export interface LLMResponse {
  text: string;
  backend: string;
}

export async function callLLM(prompt: string, system?: string, providerOverride?: string, modelOverride?: string): Promise<LLMResponse> {
  const provider = getProvider(providerOverride);
  const model = getModel(provider, modelOverride);
  if (provider === "stub") return callStub(prompt);
  if (provider === "anthropic") return callAnthropic(prompt, system, model);
  return callOpenAICompatible(prompt, system, provider, model);
}

async function callOpenAICompatible(prompt: string, system: string | undefined, provider: LLMProvider, model: string): Promise<LLMResponse> {
  const key = apiKey(provider);
  const headers: Record<string, string> = { "Content-Type": "application/json", Accept: "application/json" };
  if (key) headers.Authorization = `Bearer ${key}`;
  const res = await fetch(compatibleBaseUrl(provider), {
    method: "POST",
    headers,
    body: JSON.stringify({ model, messages: messages(prompt, system), max_tokens: 512, temperature: 0.4 }),
    signal: AbortSignal.timeout(120_000),
  });
  if (!res.ok) throw new Error(`${provider} API error ${res.status}`);
  const json = await res.json();
  return { text: json.choices?.[0]?.message?.content || "", backend: `${provider}:${model}` };
}

async function callAnthropic(prompt: string, system: string | undefined, model: string): Promise<LLMResponse> {
  const key = process.env.ANTHROPIC_API_KEY;
  if (!key) throw new Error("ANTHROPIC_API_KEY is not set");
  const res = await fetch(`${(process.env.ANTHROPIC_BASE_URL || "https://api.anthropic.com").replace(/\/$/, "")}/v1/messages`, {
    method: "POST",
    headers: { "x-api-key": key, "anthropic-version": "2023-06-01", "Content-Type": "application/json" },
    body: JSON.stringify({ model, max_tokens: 512, system, messages: [{ role: "user", content: prompt }] }),
    signal: AbortSignal.timeout(120_000),
  });
  if (!res.ok) throw new Error(`anthropic API error ${res.status}`);
  const json = await res.json();
  return { text: json.content?.filter((item: { type: string }) => item.type === "text").map((item: { text: string }) => item.text).join("") || "", backend: `anthropic:${model}` };
}

async function callStub(prompt: string): Promise<LLMResponse> {
  const lower = prompt.toLowerCase().trim();
  if (lower.includes("hello")) return { text: "Hello! I'm AEON, your autonomous AI operating system. How can I assist you today?", backend: "stub" };
  if (lower.includes("help")) return { text: "AEON is running in stub mode. Configure a provider key or a local OpenAI-compatible endpoint to enable live responses.", backend: "stub" };
  return { text: "AEON is currently operating in stub mode. Configure an LLM provider in the Brain Connector to enable live responses.", backend: "stub" };
}
