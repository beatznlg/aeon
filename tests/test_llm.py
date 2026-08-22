"""Focused regression tests for AEON's provider and model bridge."""

from __future__ import annotations

from unittest.mock import patch

import pytest

import aeon_llm


class _Response:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "choices": [{"message": {"content": "local response"}}],
            "usage": {"prompt_tokens": 2, "completion_tokens": 3},
        }


class _Session:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []

    def post(self, *args, **kwargs):
        self.calls.append(("post", args, kwargs))
        return _Response()

    def get(self, *args, **kwargs):
        self.calls.append(("get", args, kwargs))
        return _Response()


class _ModelsResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "data": [
                {"id": "frontier-model-2026"},
                {"id": "local-qwen"},
                {"id": ""},
                {"name": "ignored-without-id"},
            ]
        }


def test_registry_contains_builtin_and_custom_provider_metadata() -> None:
    providers = {item["id"]: item for item in aeon_llm.list_providers()}

    assert {"openai", "anthropic", "google", "openrouter", "ollama", "custom", "stub"} <= providers.keys()
    assert providers["custom"]["env_var"] == "AEON_CUSTOM_LLM_API_KEY"
    assert "api_key" not in providers["custom"]
    assert "secret" not in str(providers["custom"]).lower()


def test_custom_endpoint_normalization_rejects_credentials() -> None:
    assert aeon_llm._normalize_base_url("http://localhost:1234/v1/") == "http://localhost:1234/v1/chat/completions"
    assert aeon_llm._normalize_base_url("https://example.test/api/chat/completions") == "https://example.test/api/chat/completions"

    with pytest.raises(ValueError, match="credentials"):
        aeon_llm._normalize_base_url("https://user:password@example.test/v1")

    with pytest.raises(ValueError, match="query"):
        aeon_llm._normalize_base_url("https://example.test/v1?token=secret")


def test_custom_provider_uses_openai_compatible_contract_without_persisting_key() -> None:
    session = _Session()
    with patch.object(aeon_llm, "_SESSION", session):
        provider = aeon_llm.CustomLLMProvider(
            model="local-qwen",
            base_url="http://127.0.0.1:1234/v1",
            api_key="test-secret",
        )
        result = provider.generate("hello", system="be concise", max_new_tokens=64)

    assert result["text"] == "local response"
    assert result["tokens_used"] == 5
    method, args, kwargs = session.calls[0]
    assert method == "post"
    assert args[0] == "http://127.0.0.1:1234/v1/chat/completions"
    assert kwargs["json"]["model"] == "local-qwen"
    assert kwargs["json"]["messages"][0] == {"role": "system", "content": "be concise"}
    assert kwargs["json"]["messages"][1] == {"role": "user", "content": "hello"}
    assert kwargs["headers"]["Authorization"] == "Bearer test-secret"
    assert "test-secret" not in result["text"]


def test_custom_model_is_listed_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEON_CUSTOM_LLM_MODEL", "my-private-model")
    models = aeon_llm.list_models("custom")

    assert models[0] == {"provider": "custom", "id": "my-private-model", "customizable": True}


def test_provider_health_uses_models_endpoint_without_exposing_credentials() -> None:
    session = _Session()
    with patch.object(aeon_llm, "_SESSION", session):
        provider = aeon_llm.CustomLLMProvider(
            model="local-qwen",
            base_url="http://127.0.0.1:1234/v1",
            api_key="test-secret",
        )
        with patch.object(aeon_llm, "get_llm_provider", return_value=provider):
            result = aeon_llm.provider_health("custom")

    assert result == {
        "ok": True,
        "ready": True,
        "provider": "custom",
        "status": "ready",
        "checked": True,
        "available_models": [],
    }
    method, args, kwargs = session.calls[0]
    assert method == "get"
    assert args[0] == "http://127.0.0.1:1234/v1/models"
    assert kwargs["headers"]["Authorization"] == "Bearer test-secret"
    assert "test-secret" not in str(result)


def test_discover_models_returns_provider_ids_without_secret_or_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _Session()
    session.get = lambda *args, **kwargs: (_ModelsResponse())
    provider = aeon_llm.CustomLLMProvider(
        model="local-qwen",
        base_url="http://127.0.0.1:1234/v1",
        api_key="test-secret",
    )
    with patch.object(aeon_llm, "_SESSION", session), patch.object(aeon_llm, "get_llm_provider", return_value=provider):
        result = aeon_llm.discover_models("custom")

    assert result["ok"] is True
    assert [item["id"] for item in result["models"]] == ["frontier-model-2026", "local-qwen"]
    assert all(item["source"] == "provider_api" for item in result["models"])
    assert "test-secret" not in str(result)
    assert "127.0.0.1" not in str(result)


def test_provider_health_does_not_claim_non_compatible_provider_is_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEON_LLM_PROVIDER", "stub")

    result = aeon_llm.provider_health("stub")

    assert result == {
        "ok": True,
        "ready": None,
        "provider": "stub",
        "status": "not_probeable",
        "checked": False,
    }


def test_invalid_custom_provider_does_not_mutate_active_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AEON_LLM_PROVIDER", "stub")
    monkeypatch.delenv("AEON_CUSTOM_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("AEON_LLM_BASE_URL", raising=False)

    result = aeon_llm.set_active_provider("custom", model="my-model")

    assert result["ok"] is False
    assert "base URL" in result["error"]
    assert aeon_llm.os.environ["AEON_LLM_PROVIDER"] == "stub"
