"""Regression tests for workspace-scoped human approval resolution."""

from __future__ import annotations

import hashlib
import hmac
import json
from unittest import mock


def _register(client, email: str) -> tuple[str, str]:
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "secure123", "name": "Approval Tester"},
    )
    assert response.status_code == 201
    data = response.get_json()
    return data["token"], data["user"]["workspace_id"]


def test_authenticated_approval_resolution_passes_workspace_scope(client):
    token, workspace_id = _register(client, "approval-route@test.local")

    with mock.patch(
        "aeon_server.resolve_approval",
        return_value={"ok": True, "status": "approved", "approval_id": "approval-1"},
    ) as resolver:
        response = client.post(
            "/approvals/approval-1/resolve",
            headers={"Authorization": f"Bearer {token}"},
            json={"decision": "approved"},
        )

    assert response.status_code == 200
    assert resolver.call_args.kwargs["workspace_id"] == workspace_id


def test_slack_resolution_passes_signed_workspace_scope(client, monkeypatch):
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "test-signing-secret")
    workspace_id = "workspace-slack-1"
    action_value = json.dumps({
        "approval_id": "approval-slack-1",
        "decision": "rejected",
        "workspace_id": workspace_id,
    })
    payload = json.dumps({
        "user": {"id": "U123"},
        "actions": [{"value": action_value}],
    })

    with (
        mock.patch("aeon_server._verify_slack_signature", return_value=True),
        mock.patch(
            "aeon_server.resolve_approval",
            return_value={"ok": True, "status": "rejected", "approval_id": "approval-slack-1"},
        ) as resolver,
    ):
        response = client.post(
            "/slack/interactions",
            data={"payload": payload},
        )

    assert response.status_code == 200
    assert resolver.call_args.kwargs["workspace_id"] == workspace_id


def test_slack_resolution_rejects_action_without_workspace(client):
    payload = json.dumps({
        "user": {"id": "U123"},
        "actions": [{
            "value": json.dumps({"approval_id": "approval-slack-1", "decision": "approved"}),
        }],
    })

    with (
        mock.patch("aeon_server._verify_slack_signature", return_value=True),
        mock.patch("aeon_server.resolve_approval") as resolver,
    ):
        response = client.post(
            "/slack/interactions",
            data={"payload": payload},
        )

    assert response.status_code == 400
    assert "workspace_id" in response.get_json()["error"]
    resolver.assert_not_called()

def test_resolver_requires_workspace_scope(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-key")

    from aeon_automations import resolve_approval

    with mock.patch("requests.get") as get_request:
        result = resolve_approval("approval-1", "approved", "user-1")

    assert result == {"ok": False, "error": "workspace_id is required to resolve an approval"}
    get_request.assert_not_called()

def test_resolver_scopes_get_and_patch_to_workspace(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-key")

    from aeon_automations import resolve_approval

    get_response = mock.Mock()
    get_response.json.return_value = [{
        "status": "pending",
        "event_type": "manual",
        "event_payload": "{}",
        "action_type": "transform",
        "action_config": "{}",
        "workspace_id": "workspace-1",
        "rule_id": "rule-1",
    }]
    get_response.raise_for_status.return_value = None
    patch_response = mock.Mock()
    patch_response.raise_for_status.return_value = None

    with (
        mock.patch("requests.get", return_value=get_response) as get_request,
        mock.patch("requests.patch", return_value=patch_response) as patch_request,
        mock.patch("aeon_automations.execute_action_by_type", return_value={"ok": True}),
        mock.patch("aeon_automations._log_execution_with_status"),
    ):
        result = resolve_approval(
            "approval-1",
            "approved",
            "user-1",
            workspace_id="workspace-1",
        )

    assert result["ok"] is True
    assert get_request.call_args.kwargs["params"] == {
        "id": "eq.approval-1",
        "workspace_id": "eq.workspace-1",
    }
    assert patch_request.call_args.kwargs["params"] == get_request.call_args.kwargs["params"]
