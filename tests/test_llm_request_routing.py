"""Regression tests for workspace-scoped LLM provider resolution."""

from __future__ import annotations


def test_request_provider_resolution_is_workspace_scoped(monkeypatch):
    import aeon_server

    preferences = {
        "workspace-a": {"provider": "custom", "model": "model-a"},
        "workspace-b": {"provider": "ollama", "model": "model-b"},
    }
    calls = []

    monkeypatch.setattr(
        aeon_server,
        "get_workspace_llm_preference",
        lambda workspace_id: {"workspace_id": workspace_id, **preferences[workspace_id]},
    )

    def build_provider(provider, model=None):
        calls.append((provider, model))
        return (provider, model)

    monkeypatch.setattr(aeon_server, "get_llm_provider", build_provider)

    provider_a = aeon_server._request_llm_provider("workspace-a")
    provider_b = aeon_server._request_llm_provider("workspace-b")
    explicit = aeon_server._request_llm_provider("workspace-a", "stub", "deterministic")

    assert provider_a == ("custom", "model-a")
    assert provider_b == ("ollama", "model-b")
    assert explicit == ("stub", "deterministic")
    assert calls == [
        ("custom", "model-a"),
        ("ollama", "model-b"),
        ("stub", "deterministic"),
    ]


def test_request_provider_resolution_falls_back_to_process_configuration(monkeypatch):
    import aeon_server

    monkeypatch.setenv("AEON_LLM_PROVIDER", "stub")
    monkeypatch.setenv("AEON_LLM_MODEL", "deterministic stub")
    monkeypatch.setattr(
        aeon_server,
        "get_workspace_llm_preference",
        lambda _workspace_id: {"workspace_id": "missing", "provider": None, "model": None},
    )

    result = aeon_server._request_llm_provider("missing")

    assert result.__class__.__name__ == "StubProvider"
