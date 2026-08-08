"""AEON's dependency-light LLM provider bridge.

Provider metadata is public and credential-free. Credentials are read from the
process environment only when a request is made; this module never persists or
returns them. Custom hosted and local models use the OpenAI-compatible
``/v1/chat/completions`` contract, so Ollama, LM Studio, vLLM, OpenRouter, and
private gateways can be selected without adding another SDK.
"""

from __future__ import annotations

import copy
import json
import os
import time
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

_SESSION = requests.Session()
_SESSION.mount(
    "https://",
    HTTPAdapter(
        pool_connections=10,
        pool_maxsize=20,
        max_retries=Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("POST", "GET"),
        ),
    ),
)
_SESSION.mount(
    "http://",
    HTTPAdapter(
        pool_connections=10,
        pool_maxsize=20,
        max_retries=Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("POST", "GET"),
        ),
    ),
)


class LLMProvider:
    """Common interface for all AEON LLM backends."""

    def generate(self, prompt: str, system: str | None = None, max_new_tokens: int = 512) -> dict[str, Any]:
        raise NotImplementedError


def _result(text: str, tokens_used: int, started: float, backend: str) -> dict[str, Any]:
    return {
        "text": text,
        "tokens_used": int(tokens_used or 0),
        "wallclock_s": round(time.time() - started, 4),
        "backend": backend,
    }


def _error_result(label: str, error: str, backend: str) -> dict[str, Any]:
    return {
        "text": f"{label} error: {error}"[:500],
        "tokens_used": 0,
        "wallclock_s": 0.0,
        "backend": backend,
    }


def _timeout(default: float = 60.0) -> float:
    try:
        return max(1.0, float(os.environ.get("AEON_LLM_TIMEOUT_SECONDS", default)))
    except (TypeError, ValueError):
        return default


def _messages(prompt: str, system: str | None) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return messages


def _normalize_base_url(value: str, *, default_path: str = "/v1/chat/completions") -> str:
    """Normalize a compatible endpoint and reject embedded credentials."""
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("LLM base URL is required")
    parts = urlsplit(raw)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError("LLM base URL must use http:// or https://")
    if parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError("LLM base URL cannot contain credentials, query, or fragment")
    path = parts.path.rstrip("/")
    if path.endswith("/chat/completions"):
        endpoint_path = path
    elif path.endswith("/v1"):
        endpoint_path = path + "/chat/completions"
    elif path:
        endpoint_path = path + default_path
    else:
        endpoint_path = default_path
    return urlunsplit((parts.scheme, parts.netloc, endpoint_path, "", ""))


def _messages_text(data: Mapping[str, Any]) -> str:
    choices = data.get("choices") or []
    if not choices or not isinstance(choices[0], Mapping):
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content", "") if isinstance(message, Mapping) else ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            str(item.get("text", ""))
            for item in content
            if isinstance(item, Mapping) and item.get("type") in {"text", "output_text"}
        )
    return str(content or "")


def _usage_tokens(data: Mapping[str, Any]) -> int:
    usage = data.get("usage") or {}
    if not isinstance(usage, Mapping):
        return 0
    if usage.get("total_tokens") is not None:
        return int(usage.get("total_tokens") or 0)
    return int(usage.get("prompt_tokens", 0) or 0) + int(usage.get("completion_tokens", 0) or 0)


class StubProvider(LLMProvider):
    """Deterministic fallback for tests and offline development."""

    def generate(self, prompt: str, system: str | None = None, max_new_tokens: int = 512) -> dict[str, Any]:
        del system, max_new_tokens
        return _result(f"stub({prompt[:32]})", 0, time.time(), "stub")


class OpenAICompatibleProvider(LLMProvider):
    """Call any OpenAI-compatible chat completions endpoint."""

    def __init__(
        self,
        model: str | None = None,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        provider_id: str = "custom",
        default_model: str = "custom-model",
        timeout: float | None = None,
    ) -> None:
        if not base_url:
            raise ValueError(f"{provider_id} base URL is required")
        self.provider_id = provider_id
        self.model = model or default_model
        self.base_url = _normalize_base_url(base_url)
        self.api_key = api_key
        self.timeout = timeout or _timeout(120.0)

    def generate(self, prompt: str, system: str | None = None, max_new_tokens: int = 512) -> dict[str, Any]:
        started = time.time()
        if not self.model:
            return _error_result(self.provider_id, "model is required", f"{self.provider_id}_error")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            response = _SESSION.post(
                self.base_url,
                headers=headers,
                json={
                    "model": self.model,
                    "messages": _messages(prompt, system),
                    "max_tokens": max_new_tokens,
                    "temperature": 0.4,
                    "top_p": 0.9,
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, Mapping):
                raise ValueError("endpoint returned a non-object response")
            return _result(_messages_text(data), _usage_tokens(data), started, f"{self.provider_id}:{self.model}")
        except requests.RequestException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            suffix = f" (HTTP {status})" if status else ""
            return _error_result(self.provider_id, f"request failed{suffix}", f"{self.provider_id}_error")
        except (TypeError, ValueError, KeyError) as exc:
            return _error_result(self.provider_id, f"invalid response ({type(exc).__name__})", f"{self.provider_id}_error")


class CustomLLMProvider(OpenAICompatibleProvider):
    """User-configured hosted or local OpenAI-compatible endpoint."""

    def __init__(self, model: str | None = None, base_url: str | None = None, api_key: str | None = None):
        super().__init__(
            model=model or os.environ.get("AEON_CUSTOM_LLM_MODEL") or os.environ.get("AEON_LLM_MODEL"),
            base_url=base_url or os.environ.get("AEON_CUSTOM_LLM_BASE_URL") or os.environ.get("AEON_LLM_BASE_URL"),
            api_key=api_key or os.environ.get("AEON_CUSTOM_LLM_API_KEY") or os.environ.get("CUSTOM_LLM_API_KEY"),
            provider_id="custom",
            default_model="custom-model",
        )


class OpenAIProvider(OpenAICompatibleProvider):
    def __init__(self, model: str | None = None):
        super().__init__(
            model=model or os.environ.get("AEON_LLM_MODEL") or "gpt-5-mini",
            base_url=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            api_key=os.environ.get("OPENAI_API_KEY"),
            provider_id="openai",
            default_model="gpt-5-mini",
            timeout=_timeout(),
        )

    def generate(self, prompt: str, system: str | None = None, max_new_tokens: int = 512) -> dict[str, Any]:
        if not self.api_key:
            return _error_result("OpenAI", "missing OPENAI_API_KEY", "openai_error")
        return super().generate(prompt, system, max_new_tokens)


class AnthropicProvider(LLMProvider):
    def __init__(self, model: str | None = None):
        self.model = model or os.environ.get("AEON_LLM_MODEL") or "claude-sonnet-4-20250514"
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        self.base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/")

    def generate(self, prompt: str, system: str | None = None, max_new_tokens: int = 512) -> dict[str, Any]:
        if not self.api_key:
            return _error_result("Anthropic", "missing ANTHROPIC_API_KEY", "anthropic_error")
        started = time.time()
        try:
            response = _SESSION.post(
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
                    "system": system or "You are a helpful assistant.",
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=_timeout(),
            )
            response.raise_for_status()
            data = response.json()
            content = data.get("content", [])
            text = "".join(str(block.get("text", "")) for block in content if isinstance(block, Mapping) and block.get("type") == "text")
            usage = data.get("usage") or {}
            tokens = int(usage.get("input_tokens", 0) or 0) + int(usage.get("output_tokens", 0) or 0)
            return _result(text, tokens, started, f"anthropic:{self.model}")
        except requests.RequestException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            suffix = f" (HTTP {status})" if status else ""
            return _error_result("Anthropic", f"request failed{suffix}", "anthropic_error")
        except (TypeError, ValueError, KeyError) as exc:
            return _error_result("Anthropic", f"invalid response ({type(exc).__name__})", "anthropic_error")


class OllamaProvider(OpenAICompatibleProvider):
    """Ollama through its OpenAI-compatible server."""

    def __init__(self, model: str | None = None):
        base_url = os.environ.get("OLLAMA_OPENAI_BASE_URL", f"{os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434').rstrip('/')}/v1")
        super().__init__(
            model=model or os.environ.get("AEON_LLM_MODEL") or "llama3.1",
            base_url=base_url,
            api_key=os.environ.get("OLLAMA_API_KEY"),
            provider_id="ollama",
            default_model="llama3.1",
            timeout=_timeout(120.0),
        )


class HFInferenceProvider(OpenAICompatibleProvider):
    """Hugging Face router through its OpenAI-compatible endpoint."""

    def __init__(self, model: str | None = None):
        super().__init__(
            model=model or os.environ.get("AEON_LLM_MODEL") or "Qwen/Qwen2.5-7B-Instruct",
            base_url=os.environ.get("HF_OPENAI_BASE_URL", "https://router.huggingface.co/v1"),
            api_key=os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("AEON_HF_TOKEN"),
            provider_id="hf",
            default_model="Qwen/Qwen2.5-7B-Instruct",
            timeout=_timeout(90.0),
        )

    def generate(self, prompt: str, system: str | None = None, max_new_tokens: int = 512) -> dict[str, Any]:
        if not self.api_key:
            return _error_result("HF", "missing HUGGINGFACE_TOKEN", "hf_error")
        return super().generate(prompt, system, max_new_tokens)


class QwenLocalProvider(LLMProvider):
    """Wrap AEON's optional in-process local Qwen runtime."""

    def __init__(self, model: str | None = None):
        self.model = model or "Qwen/Qwen2.5-7B-Instruct"
        self._qw = None

    def generate(self, prompt: str, system: str | None = None, max_new_tokens: int = 512) -> dict[str, Any]:
        from aeon import QwenPolicy

        if self._qw is None:
            self._qw = QwenPolicy()
        return self._qw.generate(prompt, system=system, max_new_tokens=max_new_tokens)


MODEL_REGISTRY: dict[str, dict[str, Any]] = {
    "openai": {"name": "OpenAI", "models": ["gpt-5.6", "gpt-5-mini", "gpt-4.1", "gpt-4.1-mini", "o3-pro", "o4-mini-deep-research", "gpt-realtime-mini"], "env_var": "OPENAI_API_KEY", "desc": "OpenAI frontier, coding, reasoning, and realtime models."},
    "anthropic": {"name": "Anthropic (Claude)", "models": ["claude-opus-4-1", "claude-sonnet-4-20250514", "claude-3-7-sonnet-latest", "claude-3-5-haiku-latest"], "env_var": "ANTHROPIC_API_KEY", "desc": "Claude models for reasoning, coding, and long-context work."},
    "google": {"name": "Google Gemini (OpenAI-compatible)", "models": ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite"], "env_var": "GEMINI_API_KEY", "desc": "Gemini through Google's OpenAI-compatible endpoint.", "base_url": "https://generativelanguage.googleapis.com/v1beta/openai"},
    "mistral": {"name": "Mistral (OpenAI-compatible)", "models": ["mistral-large-latest", "mistral-medium-latest", "mistral-small-latest", "codestral-latest"], "env_var": "MISTRAL_API_KEY", "desc": "Mistral hosted models, including coding-focused Codestral.", "base_url": "https://api.mistral.ai/v1"},
    "openrouter": {"name": "OpenRouter", "models": ["openai/gpt-4.1-mini", "anthropic/claude-sonnet-4", "google/gemini-2.5-flash", "meta-llama/llama-4-scout"], "env_var": "OPENROUTER_API_KEY", "desc": "Route across hosted and open models with one API.", "base_url": "https://openrouter.ai/api/v1"},
    "ollama": {"name": "Ollama (Local)", "models": ["llama3.1", "qwen2.5", "gemma3", "mistral"], "env_var": "OLLAMA_BASE_URL", "desc": "Run local models privately through Ollama."},
    "lmstudio": {"name": "LM Studio (Local)", "models": ["local-model"], "env_var": "LM_STUDIO_BASE_URL", "desc": "Use a model loaded in LM Studio's local OpenAI-compatible server."},
    "vllm": {"name": "vLLM (Local or Private)", "models": ["served-model"], "env_var": "VLLM_BASE_URL", "desc": "Connect to a self-hosted vLLM OpenAI-compatible server."},
    "hf": {"name": "Hugging Face Inference", "models": ["Qwen/Qwen2.5-7B-Instruct", "meta-llama/Llama-3.1-8B-Instruct", "mistralai/Mistral-7B-Instruct-v0.3"], "env_var": "HUGGINGFACE_TOKEN", "desc": "Open-weight models through the Hugging Face router."},
    "qwen": {"name": "Qwen Local (GPU)", "models": ["Qwen/Qwen2.5-7B-Instruct"], "env_var": None, "desc": "Optional in-process local Qwen runtime."},
    "custom": {"name": "Custom OpenAI-Compatible", "models": ["custom-model"], "env_var": "AEON_CUSTOM_LLM_API_KEY", "base_url_env": "AEON_CUSTOM_LLM_BASE_URL", "desc": "Connect any hosted API or local server implementing /v1/chat/completions."},
    "stub": {"name": "Stub (No AI)", "models": ["deterministic stub"], "env_var": None, "desc": "Deterministic fallback for tests and offline development."},
}

_PROVIDER_STYLE = {"stub": ("◇", "#71717a"), "openai": ("⚡", "#10a37f"), "anthropic": ("✦", "#d97706"), "google": ("✦", "#4285f4"), "mistral": ("◆", "#f97316"), "openrouter": ("◈", "#7c3aed"), "ollama": ("🦙", "#8b5cf6"), "lmstudio": ("⌘", "#14b8a6"), "vllm": ("▣", "#0ea5e9"), "hf": ("🤗", "#fbbf24"), "qwen": ("🧠", "#6366f1"), "custom": ("✚", "#22c55e")}


def _configured(provider_id: str, metadata: Mapping[str, Any]) -> bool:
    if provider_id in {"stub", "qwen", "ollama", "lmstudio", "vllm"}:
        return True
    if provider_id == "custom":
        return bool(os.environ.get("AEON_CUSTOM_LLM_BASE_URL") or os.environ.get("AEON_LLM_BASE_URL"))
    return bool(os.environ.get(str(metadata.get("env_var") or "")))


def list_providers() -> list[dict[str, Any]]:
    """Return public provider metadata without secrets or custom URL values."""
    current = os.environ.get("AEON_LLM_PROVIDER", "stub").lower()
    selected_model = os.environ.get("AEON_LLM_MODEL")
    result = []
    for provider_id, metadata in MODEL_REGISTRY.items():
        icon, color = _PROVIDER_STYLE[provider_id]
        entry = copy.deepcopy(metadata)
        entry.update({"id": provider_id, "icon": icon, "color": color, "configured": _configured(provider_id, metadata), "active": provider_id == current, "model": selected_model if provider_id == current and selected_model else metadata["models"][0]})
        result.append(entry)
    return result


def list_models(provider: str | None = None) -> list[dict[str, Any]]:
    """Return catalog entries; arbitrary IDs remain valid for custom providers."""
    normalized = (provider or "").lower().strip()
    provider_ids = [normalized] if normalized in MODEL_REGISTRY else list(MODEL_REGISTRY)
    result = []
    for provider_id in provider_ids:
        models = list(MODEL_REGISTRY[provider_id]["models"])
        if provider_id == "custom":
            selected = os.environ.get("AEON_CUSTOM_LLM_MODEL") or os.environ.get("AEON_LLM_MODEL")
            if selected and selected not in models:
                models.insert(0, selected)
        for model in models:
            result.append({"provider": provider_id, "id": model, "customizable": provider_id in {"custom", "openrouter", "ollama", "lmstudio", "vllm", "hf"}})
    return result


def _compatible_provider(provider_id: str, model: str | None) -> OpenAICompatibleProvider:
    configs = {
        "google": {"base_url": MODEL_REGISTRY["google"]["base_url"], "api_key": os.environ.get("GEMINI_API_KEY")},
        "mistral": {"base_url": MODEL_REGISTRY["mistral"]["base_url"], "api_key": os.environ.get("MISTRAL_API_KEY")},
        "openrouter": {"base_url": MODEL_REGISTRY["openrouter"]["base_url"], "api_key": os.environ.get("OPENROUTER_API_KEY")},
        "lmstudio": {"base_url": os.environ.get("LM_STUDIO_BASE_URL", "http://localhost:1234/v1")},
        "vllm": {"base_url": os.environ.get("VLLM_BASE_URL", "http://localhost:8000/v1"), "api_key": os.environ.get("VLLM_API_KEY")},
    }
    return OpenAICompatibleProvider(model=model or os.environ.get("AEON_LLM_MODEL") or MODEL_REGISTRY[provider_id]["models"][0], provider_id=provider_id, default_model=MODEL_REGISTRY[provider_id]["models"][0], **configs[provider_id])


def get_llm_provider(provider: str | None = None, model: str | None = None) -> LLMProvider:
    provider_id = (provider or os.environ.get("AEON_LLM_PROVIDER", "stub")).lower().strip()
    aliases = {"qwen_local": "qwen", "huggingface": "hf", "openai_compatible": "custom", "local": "custom"}
    provider_id = aliases.get(provider_id, provider_id)
    selected_model = model or os.environ.get("AEON_LLM_MODEL")
    if provider_id == "qwen":
        return QwenLocalProvider(selected_model)
    if provider_id == "openai":
        return OpenAIProvider(selected_model)
    if provider_id == "anthropic":
        return AnthropicProvider(selected_model)
    if provider_id == "ollama":
        return OllamaProvider(selected_model)
    if provider_id == "hf":
        return HFInferenceProvider(selected_model)
    if provider_id == "custom":
        return CustomLLMProvider(selected_model)
    if provider_id in {"google", "mistral", "openrouter", "lmstudio", "vllm"}:
        return _compatible_provider(provider_id, selected_model)
    return StubProvider()


def set_active_provider(provider_id: str, model: str | None = None) -> dict[str, Any]:
    """Validate then switch provider/model in the current process."""
    aliases = {"qwen_local": "qwen", "huggingface": "hf", "openai_compatible": "custom", "local": "custom"}
    pid = aliases.get(str(provider_id or "").lower().strip(), str(provider_id or "").lower().strip())
    if pid not in MODEL_REGISTRY:
        return {"ok": False, "error": f"unknown provider '{provider_id}'. Valid: {sorted(MODEL_REGISTRY)}"}
    selected = str(model).strip() if model is not None else None
    if selected is not None and (not selected or len(selected) > 200):
        return {"ok": False, "error": "model must be a non-empty value shorter than 200 characters"}
    try:
        provider = get_llm_provider(pid, selected)
    except (TypeError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}
    os.environ["AEON_LLM_PROVIDER"] = pid
    if selected is not None:
        os.environ["AEON_LLM_MODEL"] = selected
    try:
        import aeon as aeon_module
        aeon_module.QW = provider
    except ImportError:
        pass
    return {"ok": True, "provider": pid, "model": selected or os.environ.get("AEON_LLM_MODEL") or MODEL_REGISTRY[pid]["models"][0]}


def provider_health(provider_id: str | None = None, model: str | None = None) -> dict[str, Any]:
    """Probe an OpenAI-compatible endpoint without generating or billing tokens.

    Compatible local and hosted servers conventionally expose ``GET /models``.
    Other providers are reported as ``not_probeable`` rather than being marked
    ready based on an assumption.  The response intentionally contains no
    endpoint, credential, or provider error body.
    """
    requested = (provider_id or os.environ.get("AEON_LLM_PROVIDER", "stub")).lower().strip()
    try:
        provider = get_llm_provider(provider_id, model)
        if not isinstance(provider, OpenAICompatibleProvider):
            return {
                "ok": True,
                "ready": None,
                "provider": requested,
                "status": "not_probeable",
                "checked": False,
            }

        models_url = provider.base_url.removesuffix("/chat/completions") + "/models"
        headers = {"Accept": "application/json"}
        if provider.api_key:
            headers["Authorization"] = f"Bearer {provider.api_key}"
        timeout = min(max(1.0, float(provider.timeout)), 30.0)
        response = _SESSION.get(models_url, headers=headers, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, Mapping):
            raise ValueError("models response must be an object")
        raw_models = payload.get("data") or []
        available_models = [
            str(item.get("id"))
            for item in raw_models
            if isinstance(item, Mapping) and item.get("id") is not None
        ]
        return {
            "ok": True,
            "ready": True,
            "provider": provider.provider_id,
            "status": "ready",
            "checked": True,
            "available_models": available_models[:100],
        }
    except requests.RequestException as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        result: dict[str, Any] = {
            "ok": False,
            "ready": False,
            "provider": requested,
            "status": "unavailable",
            "checked": True,
        }
        if status_code is not None:
            result["http_status"] = int(status_code)
        return result
    except (TypeError, ValueError, KeyError):
        return {
            "ok": False,
            "ready": False,
            "provider": requested,
            "status": "invalid_response",
            "checked": True,
        }
    except Exception:
        return {
            "ok": False,
            "ready": False,
            "provider": requested,
            "status": "unavailable",
            "checked": True,
        }


def test_provider(provider_id: str | None = None, prompt: str | None = None, model: str | None = None) -> dict[str, Any]:
    """Run a short smoke test without exposing credentials or response bodies."""
    try:
        provider = get_llm_provider(provider_id, model)
        result = provider.generate(prompt or "Say exactly: 'AEON LLM provider test: OK' and nothing else.", system="You are a test harness. Respond concisely.", max_new_tokens=80)
        return {"ok": not str(result.get("backend", "")).endswith("_error"), "provider": provider_id or os.environ.get("AEON_LLM_PROVIDER", "stub"), "backend": result.get("backend", "unknown"), "text": (result.get("text") or "")[:200], "tokens_used": result.get("tokens_used", 0), "latency_s": result.get("wallclock_s", 0.0)}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


__all__ = ["AnthropicProvider", "CustomLLMProvider", "HFInferenceProvider", "LLMProvider", "MODEL_REGISTRY", "OllamaProvider", "OpenAICompatibleProvider", "OpenAIProvider", "QwenLocalProvider", "StubProvider", "get_llm_provider", "list_models", "list_providers", "provider_health", "set_active_provider", "test_provider"]


if __name__ == "__main__":
    query = os.sys.argv[1] if len(os.sys.argv) > 1 else "hello"
    print(json.dumps(get_llm_provider().generate(query), ensure_ascii=False))
