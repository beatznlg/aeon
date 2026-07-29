"""Tests for AEON automation policy enforcement — Phase 41."""

import json
from unittest import mock

import pytest


@pytest.fixture
def admin_token(client):
    """Register a user and return an auth token with ADMIN workspace role."""
    import uuid

    email = f"admin-{uuid.uuid4().hex[:8]}@test.local"
    resp = client.post(
        "/auth/register",
        json={"email": email, "password": "secure123", "name": "Policy Admin"},
    )
    data = json.loads(resp.data)
    assert "token" in data, f"register failed: {resp.status_code} {data}"
    return data["token"]


@pytest.fixture
def operator_token(client):
    """Register a user and return an auth token with ADMIN workspace role."""
    import uuid

    email = f"operator-{uuid.uuid4().hex[:8]}@test.local"
    resp = client.post(
        "/auth/register",
        json={"email": email, "password": "secure123", "name": "Policy Operator"},
    )
    data = json.loads(resp.data)
    assert "token" in data, f"register failed: {resp.status_code} {data}"
    return data["token"]


def _policy_payload(name="Block Webhooks", effect="block", rules=None):
    return {
        "name": name,
        "effect": effect,
        "rules": rules or {"blocked_actions": ["webhook"]},
    }


def test_create_block_policy(client, admin_token):
    resp = client.post(
        "/automations/policies",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=_policy_payload(),
    )
    assert resp.status_code == 201
    data = json.loads(resp.data)
    assert data["ok"] is True
    assert data["policy"]["name"] == "Block Webhooks"
    assert data["policy"]["effect"] == "block"
    assert data["policy"]["rules"]["blocked_actions"] == ["webhook"]


def test_list_policies(client, admin_token):
    client.post(
        "/automations/policies",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=_policy_payload("Block Swarms", rules={"blocked_actions": ["swarm"]}),
    )
    resp = client.get(
        "/automations/policies",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["ok"] is True
    assert len(data["policies"]) >= 1
    assert any(p["name"] == "Block Swarms" for p in data["policies"])


def test_get_and_update_policy(client, admin_token):
    resp = client.post(
        "/automations/policies",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=_policy_payload("Require Condition", effect="require_approval", rules={"require_condition": True}),
    )
    policy_id = json.loads(resp.data)["policy"]["id"]

    resp = client.get(
        f"/automations/policies/{policy_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["policy"]["name"] == "Require Condition"

    resp = client.patch(
        f"/automations/policies/{policy_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"name": "Require Condition Updated"},
    )
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["policy"]["name"] == "Require Condition Updated"


def test_delete_policy(client, admin_token):
    resp = client.post(
        "/automations/policies",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=_policy_payload("To Delete"),
    )
    policy_id = json.loads(resp.data)["policy"]["id"]

    resp = client.delete(
        f"/automations/policies/{policy_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert json.loads(resp.data)["ok"] is True

    resp = client.get(
        f"/automations/policies/{policy_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404


def test_policy_evaluation_endpoint(client, admin_token):
    client.post(
        "/automations/policies",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=_policy_payload("Block Webhooks", rules={"blocked_actions": ["webhook"]}),
    )

    resp = client.post(
        "/automations/policies/evaluate",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "name": "Webhook Rule",
            "event_type": "workflow_status",
            "actions": [{"type": "webhook", "config": {"url": "https://example.com"}}],
        },
    )
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["allowed"] is False
    assert data["effect"] == "block"
    assert len(data["violations"]) == 1
    assert "webhook" in data["violations"][0]["message"].lower()


def test_policy_engine_blocks_action_type():
    from aeon_db import create_automation_policy, init_db
    from aeon_policies import evaluate_automation_policy

    init_db()
    policy = create_automation_policy(
        workspace_id="ws-1",
        name="Block Webhook",
        effect="block",
        rules={"blocked_actions": ["webhook"]},
    )
    result = evaluate_automation_policy(
        "ws-1",
        {
            "name": "Test Rule",
            "event_type": "workflow_status",
            "actions": [{"type": "webhook", "config": {"url": "https://example.com"}}],
        },
    )
    assert result.allowed is False
    assert result.effect == "block"
    assert any("webhook" in v.message for v in result.violations)


def test_policy_engine_requires_approval():
    from aeon_db import create_automation_policy, init_db
    from aeon_policies import evaluate_automation_policy

    init_db()
    create_automation_policy(
        workspace_id="ws-2",
        name="Require Approval",
        effect="require_approval",
        rules={"blocked_actions": ["swarm"]},
    )
    result = evaluate_automation_policy(
        "ws-2",
        {
            "name": "Swarm Rule",
            "event_type": "workflow_status",
            "actions": [{"type": "swarm", "config": {"prompt": "test"}}],
        },
    )
    assert result.allowed is False
    assert result.effect == "require_approval"


def test_policy_create_enforcement_blocks_rule(client, admin_token, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")

    client.post(
        "/automations/policies",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=_policy_payload("Block Webhooks", rules={"blocked_actions": ["webhook"]}),
    )

    import requests as _requests

    with mock.patch.object(_requests, "post") as mock_post:
        mock_resp = mock.Mock()
        mock_resp.json.return_value = [{"id": "rule-1"}]
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        resp = client.post(
            "/automations",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "name": "Webhook Rule",
                "event_type": "workflow_status",
                "actions": [{"type": "webhook", "config": {"url": "https://example.com"}}],
            },
        )
    assert resp.status_code == 403
    data = json.loads(resp.data)
    assert data["ok"] is False
    assert data["policy_effect"] == "block"


def test_policy_create_enforcement_requires_approval(client, admin_token, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")

    client.post(
        "/automations/policies",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=_policy_payload("Approve Webhooks", effect="require_approval", rules={"blocked_actions": ["webhook"]}),
    )

    import requests as _requests

    with mock.patch.object(_requests, "post") as mock_post:
        mock_resp = mock.Mock()
        mock_resp.json.return_value = [{"id": "rule-1", "approval_required": True}]
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        resp = client.post(
            "/automations",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "name": "Webhook Rule",
                "event_type": "workflow_status",
                "actions": [{"type": "webhook", "config": {"url": "https://example.com"}}],
            },
        )
    assert resp.status_code == 201
    data = json.loads(resp.data)
    assert data["ok"] is True
    # The policy should have forced approval_required on the payload sent to Supabase.
    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs["json"]["approval_required"] is True


def test_policy_import_enforcement_blocks_rule(client, admin_token, monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")

    client.post(
        "/automations/policies",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=_policy_payload("Block Webhooks", rules={"blocked_actions": ["webhook"]}),
    )

    import requests as _requests

    with mock.patch.object(_requests, "post") as mock_post:
        mock_resp = mock.Mock()
        mock_resp.json.return_value = [{"id": "imported-1"}]
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        resp = client.post(
            "/automations/import",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "rules": [
                    {
                        "name": "Bad Rule",
                        "event_type": "workflow_status",
                        "actions": [{"type": "webhook", "config": {"url": "https://example.com"}}],
                    }
                ]
            },
        )
    assert resp.status_code == 207
    data = json.loads(resp.data)
    assert data["ok"] is False
    assert len(data["errors"]) == 1
    assert data["errors"][0]["error"] == "policy violation"
