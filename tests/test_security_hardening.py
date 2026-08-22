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


def test_workspace_header_is_a_selector_not_an_authorization_grant(client):
    registration = client.post(
        "/auth/register",
        json={"email": "header-owner@test.local", "password": "secure123", "name": "Header Owner"},
    )
    token = registration.get_json()["token"]
    own_workspace = registration.get_json()["user"]["workspace_id"]
    other = client.post(
        "/auth/register",
        json={"email": "header-other@test.local", "password": "secure123", "name": "Header Other"},
    )
    other_workspace = other.get_json()["user"]["workspace_id"]
    headers = {"Authorization": f"Bearer {token}", "X-Workspace-Id": other_workspace}

    denied = client.get("/anomalies", headers=headers)
    assert denied.status_code == 403

    allowed = client.get(
        "/anomalies",
        headers={"Authorization": f"Bearer {token}", "X-Workspace-Id": own_workspace},
    )
    assert allowed.status_code == 200
    assert allowed.get_json()["anomalies"] == []


def test_anomaly_mutation_is_scoped_to_authorized_workspace(client):
    owner = client.post(
        "/auth/register",
        json={"email": "anomaly-owner@test.local", "password": "secure123", "name": "Owner"},
    ).get_json()
    foreign = client.post(
        "/auth/register",
        json={"email": "anomaly-foreign@test.local", "password": "secure123", "name": "Foreign"},
    ).get_json()

    from aeon_db import create_anomaly, get_anomaly

    anomaly = create_anomaly(
        workspace_id=foreign["user"]["workspace_id"],
        anomaly_type="test",
        severity="warning",
        title="foreign anomaly",
    )
    response = client.post(
        f"/anomalies/{anomaly.id}/dismiss",
        headers={
            "Authorization": f"Bearer {owner['token']}",
            "X-Workspace-Id": owner["user"]["workspace_id"],
        },
    )
    assert response.status_code == 404
    assert get_anomaly(anomaly.id).dismissed is False


def test_integration_manager_scopes_lookup_and_proxy(tmp_path):
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "aeon_integrations.py"
    spec = importlib.util.spec_from_file_location("aeon_integrations_regression", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    manager = module.IntegrationManager(tmp_path)
    workspace_a = manager.save({"name": "A", "type": "rest"}, workspace_id="workspace-a")
    workspace_b = manager.save({"name": "B", "type": "rest"}, workspace_id="workspace-b")

    assert [item["id"] for item in manager.list_integrations(workspace_id="workspace-a")] == [workspace_a.id]
    assert manager.get(workspace_b.id, workspace_id="workspace-a") is None
    denied = manager.proxy(workspace_b.id, endpoint="", method="GET", workspace_id="workspace-a")
    assert denied == {"ok": False, "error": "integration not found"}


def test_job_status_cannot_cross_workspace():
    import aeon_server

    job_queue = aeon_server.JobQueue(workers=1)
    try:
        job_id = job_queue.submit("app", "act", {"query": "hi", "workspace_id": "workspace-a"})
        assert job_queue.status(job_id, workspace_id="workspace-a") is not None
        assert job_queue.status(job_id, workspace_id="workspace-b") is None
    finally:
        job_queue.shutdown()
