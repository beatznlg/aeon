import { DEFAULT_PROVIDER } from "./llm";

export const PROVIDER_STORAGE_KEY = "aeon_provider";

export type StoredProvider = "openrouter" | "openai" | "anthropic" | "hf" | "stub";

export const ALL_PROVIDERS: StoredProvider[] = ["openrouter", "openai", "anthropic", "hf", "stub"];

export function getStoredProvider(): StoredProvider {
  if (typeof window === "undefined") return DEFAULT_PROVIDER as StoredProvider;
  try {
    const value = window.localStorage.getItem(PROVIDER_STORAGE_KEY);
    if (value && ALL_PROVIDERS.includes(value as StoredProvider)) {
      return value as StoredProvider;
    }
  } catch {}
  return DEFAULT_PROVIDER as StoredProvider;
}

export function setStoredProvider(provider: StoredProvider): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(PROVIDER_STORAGE_KEY, provider);
  } catch {}
}
