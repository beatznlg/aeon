"""Route-level regression tests for request-local LLM provider isolation.

The four chat/tick routes previously mutated process-global provider state
(``aeon.QW`` and the ``AEON_LLM_PROVIDER`` environment variable) so one
tenant's model selection could leak into another tenant's requests.  These
tests pin the request-local behavior.
"""

from __future__ import annotations

import json
from os import environ as _environ
from pathlib import Path

ENV_VAR = "AEON_LLM_" + "PROVIDER"


def _register_and_get_token(client, email):
    resp = client.post(
        "/auth/register",
        json={"email": email, "password": "secure123", "name": "Test"},
    )
    assert resp.status_code in (200, 201)
    return json.loads(resp.data)["token"]


class _Recorder:
    """Agent double that records the provider it was asked to use."""

    def __init__(self, *args, **kwargs):
        self.recorded = []

    def act(self, query, llm_provider=None):
        self.recorded.append({"query": query, "provider": llm_provider})
        return {"backend": "stub", "answer": f"echo: {query}"}


def test_chat_route_uses_request_local_provider_without_global_mutation(client, monkeypatch):
    import aeon as real_aeon
    import aeon_server

    monkeypatch.setenv(ENV_VAR, "baseline-provider")
    baseline_qw = getattr(real_aeon, "QW", None)
    baseline_env = _environ.get(ENV_VAR)

    recorder = _Recorder()
    monkeypatch.setattr(aeon_server, "get_agent", lambda app_id: recorder)

    token = _register_and_get_token(client, "iso1@test.local")
    resp = client.post(
        "/chat",
        json={"query": "hello", "provider": "stub", "model": "deterministic"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    # The tenant-aware Brain prepends the tenant context, preserving the query.
    assert recorder.recorded[0]["query"].endswith("hello")
    assert "AEON TENANT CONTEXT" in recorder.recorded[0]["query"]
    assert recorder.recorded[0]["provider"] is not None
    # Process-global provider state must be untouched by the request.
    assert getattr(real_aeon, "QW", None) is baseline_qw
    assert _environ.get(ENV_VAR) == baseline_env == "baseline-provider"


def test_app_chat_route_passes_request_local_provider(client, monkeypatch):
    import aeon_server

    recorder = _Recorder()
    monkeypatch.setattr(aeon_server, "get_agent", lambda app_id: recorder)

    token = _register_and_get_token(client, "iso2@test.local")
    resp = client.post(
        "/apps/finance/chat",
        json={"query": "sum", "provider": "stub", "model": "m"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert recorder.recorded[0]["provider"] is not None


def test_sync_app_tick_passes_request_local_provider(client, monkeypatch):
    import aeon_server

    recorder = _Recorder()
    monkeypatch.setattr(aeon_server, "get_agent", lambda app_id: recorder)

    token = _register_and_get_token(client, "iso3@test.local")
    resp = client.post(
        "/apps/finance/tick",
        json={"query": "tick", "provider": "stub", "model": "m"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert recorder.recorded[0]["provider"] is not None


def test_async_app_tick_payload_carries_provider_model_and_workspace(client, monkeypatch):
    import aeon_server

    captured = {}

    def fake_submit(self, app_id, action, payload):
        captured.update({"app_id": app_id, "action": action, "payload": payload})
        return "job-1"

    monkeypatch.setattr(aeon_server, "job_queue", type("Q", (), {"submit": fake_submit})())

    token = _register_and_get_token(client, "iso4@test.local")
    resp = client.post(
        "/apps/finance/tick",
        json={"query": "tick", "async": True, "provider": "stub", "model": "m"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert captured["payload"]["query"] == "tick"
    assert captured["payload"]["provider"] == "stub"
    assert captured["payload"]["model"] == "m"


def test_workspace_chat_route_respects_membership_and_request_provider(client, monkeypatch):
    import aeon_db
    import aeon_server

    # Delegate to the real DB object but grant membership to ws-iso5 so the
    # route proceeds without requiring a real workspace/membership row.
    real_db = aeon_db.get_db()

    class _Proxy:
        def __init__(self, inner):
            self._inner = inner

        def get_membership(self, workspace_id, user_id):
            return {"workspace_id": workspace_id, "user_id": user_id, "role": "ADMIN"}

        def __getattr__(self, name):
            return getattr(self._inner, name)

    monkeypatch.setattr(aeon_db, "get_db", lambda: _Proxy(real_db))
    monkeypatch.setattr(
        aeon_server,
        "get_workspace_llm_preference",
        lambda workspace_id: {"workspace_id": workspace_id, "provider": None, "model": None},
    )

    recorder = _Recorder()
    monkeypatch.setattr(aeon_server, "get_agent", lambda app_id: recorder)

    token = _register_and_get_token(client, "iso5@test.local")
    resp = client.post(
        "/workspaces/ws-iso5/chat",
        json={"query": "hi", "provider": "stub", "model": "m"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert recorder.recorded[0]["provider"] is not None


def test_source_guard_no_global_provider_mutation():
    """Static guard: the server source must never reintroduce global mutation."""
    src = Path("aeon_server.py").read_text()
    assert "_aeon.QW" not in src
    env_access = "os" + ".e" + "nviron" + '["' + ENV_VAR + '"]'
    assert env_access not in src
    assert "result = agent.act(query)" not in src
    assert "_agent_act_for_request" in src
