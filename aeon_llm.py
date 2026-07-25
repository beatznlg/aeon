# ============================================================
#  AEON LLM Provider Bridge
#  Pluggable backend for OpenAI, Anthropic, Ollama,
#  Hugging Face Inference, local Qwen, and a stub fallback.
# ============================================================
import json
import os
import time

import requests


class LLMProvider:
    """Common interface for all AEON LLM backends."""

    def generate(self, prompt: str, system: str = None, max_new_tokens: int = 512) -> dict:
        """
        Generate a text completion.
        Returns a dict with keys: text, tokens_used, wallclock_s, backend.
        """
        raise NotImplementedError


class StubProvider(LLMProvider):
    """Deterministic fallback used when no backend is configured or loading fails."""

    def generate(self, prompt: str, system: str = None, max_new_tokens: int = 512) -> dict:
        return {
            "text": "stub(" + prompt[:32] + ")",
            "tokens_used": 0,
            "wallclock_s": 0.0,
            "backend": "stub",
        }


class OpenAIProvider(LLMProvider):
    def __init__(self, model: str = None):
        self.model = model or os.environ.get("AEON_LLM_MODEL") or "gpt-4o-mini"
        self.api_key = os.environ.get("OPENAI_API_KEY")
        self.base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")

    def generate(self, prompt: str, system: str = None, max_new_tokens: int = 512) -> dict:
        if not self.api_key:
            return {"text": "OpenAI: missing OPENAI_API_KEY", "tokens_used": 0,
                    "wallclock_s": 0.0, "backend": "openai_error"}
        try:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            t0 = time.time()
            r = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": max_new_tokens,
                    "temperature": 0.4,
                    "top_p": 0.9,
                },
                timeout=60,
            )
            r.raise_for_status()
            data = r.json()
            choice = data.get("choices", [{}])[0]
            text = choice.get("message", {}).get("content", "")
            usage = data.get("usage", {})
            return {
                "text": text,
                "tokens_used": usage.get("total_tokens", 0),
                "wallclock_s": round(time.time() - t0, 4),
                "backend": f"openai:{self.model}",
            }
        except Exception as e:
            return {
                "text": f"OpenAI error: {type(e).__name__}: {e}"[:500],
                "tokens_used": 0,
                "wallclock_s": 0.0,
                "backend": "openai_error",
            }


class AnthropicProvider(LLMProvider):
    def __init__(self, model: str = None):
        self.model = model or os.environ.get("AEON_LLM_MODEL") or "claude-3-5-sonnet-20240620"
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        self.base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")

    def generate(self, prompt: str, system: str = None, max_new_tokens: int = 512) -> dict:
        if not self.api_key:
            return {"text": "Anthropic: missing ANTHROPIC_API_KEY", "tokens_used": 0,
                    "wallclock_s": 0.0, "backend": "anthropic_error"}
        try:
            t0 = time.time()
            r = requests.post(
                f"{self.base_url}/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": max_new_tokens,
                    "temperature": 0.4,
                    "top_p": 0.9,
                    "system": system or "You are a helpful assistant.",
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=60,
            )
            r.raise_for_status()
            data = r.json()
            content_blocks = data.get("content", [])
            text = ""
            for block in content_blocks:
                if block.get("type") == "text":
                    text += block.get("text", "")
            return {
                "text": text,
                "tokens_used": data.get("usage", {}).get("input_tokens", 0)
                            + data.get("usage", {}).get("output_tokens", 0),
                "wallclock_s": round(time.time() - t0, 4),
                "backend": f"anthropic:{self.model}",
            }
        except Exception as e:
            return {
                "text": f"Anthropic error: {type(e).__name__}: {e}"[:500],
                "tokens_used": 0,
                "wallclock_s": 0.0,
                "backend": "anthropic_error",
            }


class OllamaProvider(LLMProvider):
    def __init__(self, model: str = None):
        self.model = model or os.environ.get("AEON_LLM_MODEL") or "llama3"
        self.base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

    def generate(self, prompt: str, system: str = None, max_new_tokens: int = 512) -> dict:
        try:
            t0 = time.time()
            r = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "system": system or "",
                    "stream": False,
                    "options": {"temperature": 0.4, "top_p": 0.9, "num_predict": max_new_tokens},
                },
                timeout=120,
            )
            r.raise_for_status()
            data = r.json()
            return {
                "text": data.get("response", ""),
                "tokens_used": data.get("eval_count", 0),
                "wallclock_s": round(time.time() - t0, 4),
                "backend": f"ollama:{self.model}",
            }
        except Exception as e:
            return {
                "text": f"Ollama error: {type(e).__name__}: {e}"[:500],
                "tokens_used": 0,
                "wallclock_s": 0.0,
                "backend": "ollama_error",
            }


class HFInferenceProvider(LLMProvider):
    """Hugging Face Inference API for text-generation models."""

    def __init__(self, model: str = None):
        self.model = model or os.environ.get("AEON_LLM_MODEL") or "Qwen/Qwen2.5-3B-Instruct"
        self.token = os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("AEON_HF_TOKEN")

    def generate(self, prompt: str, system: str = None, max_new_tokens: int = 512) -> dict:
        if not self.token:
            return {"text": "HF: missing HUGGINGFACE_TOKEN", "tokens_used": 0,
                    "wallclock_s": 0.0, "backend": "hf_error"}
        try:
            t0 = time.time()
            # Use chat template if available; otherwise simple text input
            payload = {"inputs": prompt, "parameters": {"max_new_tokens": max_new_tokens}}
            r = requests.post(
                f"https://api-inference.huggingface.co/models/{self.model}",
                headers={"Authorization": f"Bearer {self.token}"},
                json=payload,
                timeout=90,
            )
            r.raise_for_status()
            data = r.json()
            text = ""
            if isinstance(data, list):
                text = data[0].get("generated_text", "")
            elif isinstance(data, dict):
                text = data.get("generated_text", "")
            return {
                "text": text,
                "tokens_used": 0,
                "wallclock_s": round(time.time() - t0, 4),
                "backend": f"hf:{self.model}",
            }
        except Exception as e:
            return {
                "text": f"HF error: {type(e).__name__}: {e}"[:500],
                "tokens_used": 0,
                "wallclock_s": 0.0,
                "backend": "hf_error",
            }


class QwenLocalProvider(LLMProvider):
    """Wrap the existing local Qwen2.5-3B policy from aeon.py."""

    def __init__(self, model: str = None):
        # model is ignored; aeon.py's QwenPolicy always loads Qwen2.5-3B-Instruct
        self.model = model or "Qwen/Qwen2.5-3B-Instruct"
        self._qw = None

    def generate(self, prompt: str, system: str = None, max_new_tokens: int = 512) -> dict:
        # Lazy import to avoid circular dependency with aeon.py
        from aeon import QwenPolicy
        if self._qw is None:
            self._qw = QwenPolicy()
        return self._qw.generate(prompt, system=system, max_new_tokens=max_new_tokens)


def get_llm_provider(provider: str = None, model: str = None) -> LLMProvider:
    """
    Factory that returns the configured AEON LLM provider.
    Env: AEON_LLM_PROVIDER in {stub, qwen, qwen_local, openai, anthropic, ollama, hf, huggingface}
         AEON_LLM_MODEL, plus provider-specific API keys.
    """
    p = (provider or os.environ.get("AEON_LLM_PROVIDER", "stub")).lower()
    if p in ("qwen", "qwen_local"):
        return QwenLocalProvider(model)
    if p == "openai":
        return OpenAIProvider(model)
    if p == "anthropic":
        return AnthropicProvider(model)
    if p == "ollama":
        return OllamaProvider(model)
    if p in ("hf", "huggingface"):
        return HFInferenceProvider(model)
    return StubProvider()


_PROVIDER_METADATA = [
    {
        "id": "stub",
        "name": "Stub (No AI)",
        "icon": "\u25c7",
        "color": "#71717a",
        "models": ["deterministic stub"],
        "desc": "Fallback mode for testing and development. Returns deterministic responses without any API calls.",
        "configured": True,
        "env_var": None,
    },
    {
        "id": "openai",
        "name": "OpenAI",
        "icon": "\u26a1",
        "color": "#10a37f",
        "models": ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo"],
        "desc": "Industry-leading language models with strong reasoning, coding, and instruction-following.",
        "configured": bool(os.environ.get("OPENAI_API_KEY")),
        "env_var": "OPENAI_API_KEY",
    },
    {
        "id": "anthropic",
        "name": "Anthropic (Claude)",
        "icon": "\u2726",
        "color": "#d97706",
        "models": ["claude-3-5-sonnet-20240620", "claude-3-haiku"],
        "desc": "Advanced AI assistants focused on safety, with exceptional reasoning and coding abilities.",
        "configured": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "env_var": "ANTHROPIC_API_KEY",
    },
    {
        "id": "ollama",
        "name": "Ollama (Local)",
        "icon": "\ud83e\udd99",
        "color": "#8b5cf6",
        "models": ["llama3", "mistral", "gemma", "qwen2.5"],
        "desc": "Run LLMs locally on your infrastructure. Perfect for air-gapped deployments.",
        "configured": True,
        "env_var": "OLLAMA_BASE_URL",
    },
    {
        "id": "hf",
        "name": "Hugging Face Inference",
        "icon": "\ud83e\udd17",
        "color": "#fbbf24",
        "models": ["Qwen/Qwen2.5-3B-Instruct", "microsoft/Phi-3-mini-4k-instruct"],
        "desc": "Access thousands of open-source models via the Hugging Face Inference API.",
        "configured": bool(os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("AEON_HF_TOKEN")),
        "env_var": "HUGGINGFACE_TOKEN",
    },
    {
        "id": "qwen",
        "name": "Qwen Local (GPU)",
        "icon": "\ud83e\udde0",
        "color": "#6366f1",
        "models": ["Qwen/Qwen2.5-3B-Instruct (quantized)"],
        "desc": "Built-in small language model that runs on GPU. Downloads automatically on first use.",
        "configured": True,
        "env_var": None,
    },
]


def list_providers() -> list:
    """
    Return metadata for all available providers, including status and active flag.
    Re-checks env vars so the UI always reflects the current configuration.
    """
    import copy
    current = os.environ.get("AEON_LLM_PROVIDER", "stub").lower()
    providers = []
    for p in _PROVIDER_METADATA:
        entry = copy.deepcopy(p)
        # Re-check configured status for providers that need API keys
        if entry["id"] == "openai":
            entry["configured"] = bool(os.environ.get("OPENAI_API_KEY"))
        elif entry["id"] == "anthropic":
            entry["configured"] = bool(os.environ.get("ANTHROPIC_API_KEY"))
        elif entry["id"] == "hf":
            entry["configured"] = bool(os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("AEON_HF_TOKEN"))
        entry["active"] = (entry["id"] == current)
        providers.append(entry)
    return providers


def set_active_provider(provider_id: str) -> dict:
    """
    Switch the active LLM provider at runtime.
    Updates os.environ and the aeon.QW module global so all subsequent
    chat/agent calls use the new provider.
    Returns {"ok": True, "provider": provider_id} or {"ok": False, "error": ...}.
    """
    valid_ids = {p["id"] for p in _PROVIDER_METADATA}
    pid = provider_id.lower().strip()
    if pid not in valid_ids:
        return {"ok": False, "error": f"unknown provider '{provider_id}'. Valid: {sorted(valid_ids)}"}

    # Update env var so subsequent get_llm_provider() calls pick it up
    os.environ["AEON_LLM_PROVIDER"] = pid

    # Update the aeon module's QW global directly for in-memory switching
    try:
        import aeon as _aeon_module
        _aeon_module.QW = get_llm_provider(pid)
    except ImportError:
        pass  # aeon.py may not be loaded yet (e.g. server cold start before first chat)

    return {"ok": True, "provider": pid}


def test_provider(provider_id: str = None, prompt: str = None) -> dict:
    """Test a provider with a simple prompt and return the result."""
    try:
        prov = get_llm_provider(provider_id)
        test_prompt = prompt or "Say exactly: 'AEON LLM provider test: OK' and nothing else."
        ts = time.time()
        result = prov.generate(test_prompt, system="You are a test harness. Respond concisely.", max_new_tokens=80)
        elapsed = round(time.time() - ts, 3)
        return {
            "ok": True,
            "provider": provider_id or os.environ.get("AEON_LLM_PROVIDER", "stub"),
            "backend": result.get("backend", "unknown"),
            "text": (result.get("text") or "")[:200],
            "tokens_used": result.get("tokens_used", 0),
            "latency_s": elapsed,
        }
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


if __name__ == "__main__":
    # CLI quick test: python aeon_llm.py "hello"
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "hello"
    p = get_llm_provider()
    print(json.dumps(p.generate(q, system="You are AEON.")))
