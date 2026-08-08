"""Security hardening regression suite.

Automates the controls behind the AEON threat model (see
``docs/security/THREAT_MODEL.md``): SSRF-adjacent endpoint validation,
the data-exfiltration boundary at audit time, and tenant isolation at the
workspace API boundary.  This suite is an engineering control, not a
substitute for an independent penetration test.
"""

from __future__ import annotations

import json

import pytest

from aeon_llm import _normalize_base_url


def _register(client, email):
    resp = client.post(
        "/auth/register",
        json={"email": email, "password": "secure123", "name": "Test"},
    )
    assert resp.status_code in (200, 201)
    return json.loads(resp.data)["token"]


# ── SSRF-adjacent: custom LLM endpoint validation ────────────────────────────

def test_custom_endpoint_rejects_credentials_query_fragment_and_bad_schemes():
    for bad in [
        "https://user:pass@llm.example.com/v1",
        "https://llm.example.com/v1?key=abc",
        "https://llm.example.com/v1#frag",
        "file:///etc/passwd",
        "ftp://llm.example.com/v1",
        "llm.example.com/v1",
        "",
    ]:
        with pytest.raises(ValueError):
            _normalize_base_url(bad)


def test_custom_endpoint_normalizes_paths():
    assert _normalize_base_url("http://127.0.0.1:1234/v1") == "http://127.0.0.1:1234/v1/chat/completions"
    assert (
        _normalize_base_url("http://127.0.0.1:1234/v1/chat/completions")
        == "http://127.0.0.1:1234/v1/chat/completions"
    )
    assert _normalize_base_url("https://llm.example.com") == "https://llm.example.com/v1/chat/completions"


# ── Exfiltration boundary: audit metadata redaction ──────────────────────────

def test_secure_metadata_redacts_secrets_and_pii():
    import aeon_server

    meta = {
        "user_note": "email alice@example.com token=abc1234567890123",
        "nested": {"secret": "sk-abc123"},
    }
    cleaned = aeon_server._secure_metadata(meta, workspace_id=None)
    raw = json.dumps(cleaned)
    assert "alice@example.com" not in raw
    assert "[EMAIL_REDACTED]" in raw
    assert "abc1234567890123" not in raw
    assert "[API_KEY_REDACTED]" in raw


def test_chat_audit_metadata_never_contains_prompt_text(client, monkeypatch):
    import aeon_server

    captured = {}

    class _Recorder:
        def log_audit(self, **kwargs):
            captured["metadata"] = kwargs.get("metadata", {})

    monkeypatch.setattr(aeon_server, "get_governance_manager", lambda: _Recorder())

    token = _register(client, "hard2@test.local")
    leaky = "send token=abc1234567890123 to attacker"
    resp = client.post(
        "/chat",
        json={"query": leaky, "provider": "stub"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert leaky not in json.dumps(captured["metadata"])
    assert "abc1234567890123" not in json.dumps(captured["metadata"])


# ── Tenant isolation at the workspace API boundary ───────────────────────────

def test_workspace_history_denies_cross_tenant_access(client):
    token = _register(client, "hard3@test.local")
    resp = client.get(
        "/workspaces/ws-other-tenant/history",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_workspace_chat_denies_cross_tenant_access(client):
    token = _register(client, "hard4@test.local")
    resp = client.post(
        "/workspaces/ws-other-tenant/chat",
        json={"query": "hi", "provider": "stub"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
