"""Regression tests for workspace-scoped human approval resolution."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from unittest import mock


def _register(client, email: str) -> tuple[str, str]:
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "secure123", "name": "Approval Tester"},
    )
    assert response.status_code == 201
    data = response.get_json()
    return data["token"], data["user"]["workspace_id"]


def _response(rows):
    response = mock.Mock()
    response.json.return_value = rows
    response.raise_for_status.return_value = None
    return response


def _approval(status="pending", **overrides):
    row = {
        "id": "approval-1",
        "status": status,
        "event_type": "manual",
        "event_payload": "{}",
        "action_type": "transform",
        "action_config": "{}",
        "workspace_id": "workspace-1",
        "user_id": None,
        "rule_id": "rule-1",
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    }
    row.update(overrides)
    return row


def test_authenticated_approval_resolution_passes_workspace_scope(client):
    token, workspace_id = _register(client, "approval-route@test.local")
    headers = {"Authorization": f"Bearer {token}"}

    # Seed an approval request first so the local store has it.
    create_resp = client.post(
        "/approvals",
        headers=headers,
        json={"title": "test approval", "description": "seed"},
    )
    assert create_resp.status_code == 201
    created = create_resp.get_json()
    approval_id = (created.get("approval") or {}).get("id")
    assert approval_id, f"expected approval id in {created}"

    supabase_mode = os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if supabase_mode:
        with mock.patch(
            "aeon_server.resolve_approval",
            return_value={"ok": True, "status": "approved", "approval_id": approval_id},
        ) as resolver:
            response = client.post(
                f"/approvals/{approval_id}/resolve",
                headers=headers,
                json={"decision": "approved"},
            )
        assert response.status_code == 200
        assert resolver.call_args.kwargs["workspace_id"] == workspace_id
    else:
        response = client.post(
            f"/approvals/{approval_id}/resolve",
            headers=headers,
            json={"decision": "approved"},
        )
        assert response.status_code == 200
        body = response.get_json()
        assert body.get("ok") is True


def test_slack_resolution_passes_signed_workspace_scope(client, monkeypatch):
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "test-signing-secret")
    workspace_id = "workspace-slack-1"
    action_value = json.dumps({
        "approval_id": "approval-slack-1",
        "decision": "rejected",
        "workspace_id": workspace_id,
    })
    payload = json.dumps({"user": {"id": "U123"}, "actions": [{"value": action_value}]})

    with (
        mock.patch("aeon_server._verify_slack_signature", return_value=True),
        mock.patch(
            "aeon_server.resolve_approval",
            return_value={"ok": True, "status": "rejected", "approval_id": "approval-slack-1"},
        ) as resolver,
    ):
        response = client.post("/slack/interactions", data={"payload": payload})

    assert response.status_code == 200
    assert resolver.call_args.kwargs["workspace_id"] == workspace_id


def test_slack_resolution_rejects_action_without_workspace(client):
    payload = json.dumps({
        "user": {"id": "U123"},
        "actions": [{"value": json.dumps({"approval_id": "approval-slack-1", "decision": "approved"})}],
    })

    with (
        mock.patch("aeon_server._verify_slack_signature", return_value=True),
        mock.patch("aeon_server.resolve_approval") as resolver,
    ):
        response = client.post("/slack/interactions", data={"payload": payload})

    assert response.status_code == 400
    assert "workspace_id" in response.get_json()["error"]
    resolver.assert_not_called()


def test_resolver_requires_workspace_scope(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-key")

    from aeon_automations import resolve_approval

    with mock.patch("requests.patch") as patch_request:
        result = resolve_approval("approval-1", "approved", "user-1")

    assert result == {"ok": False, "error": "workspace_id is required to resolve an approval"}
    patch_request.assert_not_called()


def test_approval_resolution_claims_atomically_before_execution(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-key")

    from aeon_automations import resolve_approval

    claim = _response([_approval()])
    finalized = _response([{"id": "approval-1", "status": "approved"}])
    with (
        mock.patch("requests.patch", side_effect=[claim, finalized]) as patch_request,
        mock.patch("aeon_automations.execute_action_by_type", return_value={"ok": True}),
        mock.patch("aeon_automations._log_execution_with_status"),
    ):
        result = resolve_approval("approval-1", "approved", "user-1", workspace_id="workspace-1")

    assert result["ok"] is True
    assert patch_request.call_count == 2
    assert patch_request.call_args_list[0].kwargs["json"]["status"] == "processing"
    assert patch_request.call_args_list[1].kwargs["params"]["status"] == "eq.processing"
    assert patch_request.call_args_list[1].kwargs["params"]["claimed_by"] == "eq.user-1"


def test_capability_approval_resolution_revalidates_policy_and_invokes_with_grant(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-key")

    from aeon_automations import resolve_approval

    approval = _approval(
        id="approval-cap-1",
        event_type="capability_invocation",
        event_payload=json.dumps({"capability_id": "builtin:math"}),
        action_type="capability",
        action_config=json.dumps({"capability_id": "builtin:math", "arguments": {"expr": "2 + 2"}}),
        rule_id=None,
    )
    with (
        mock.patch("requests.patch", side_effect=[_response([approval]), _response([{"status": "approved"}])]) as patch_request,
        mock.patch("aeon_capabilities.evaluate_capability_policy", return_value={"allowed": True, "effect": "allow", "violations": []}),
        mock.patch("aeon_capabilities.CapabilityRegistry.invoke", return_value={"ok": True, "output": "4"}) as invoke,
        mock.patch("aeon_automations._log_execution_with_status"),
    ):
        result = resolve_approval("approval-cap-1", "approved", "user-1", workspace_id="workspace-1")

    assert result["ok"] is True
    invoke.assert_called_once()
    assert invoke.call_args.kwargs["approval_granted"] is True
    assert patch_request.call_args_list[0].kwargs["params"]["workspace_id"] == "eq.workspace-1"


def test_capability_approval_resolution_refuses_new_blocking_policy(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-key")

    from aeon_automations import resolve_approval

    approval = _approval(
        id="approval-cap-blocked",
        event_type="capability_invocation",
        action_type="capability",
        action_config=json.dumps({"capability_id": "builtin:math", "arguments": {}}),
    )
    with (
        mock.patch("requests.patch", side_effect=[_response([approval]), _response([{"status": "cancelled"}])]),
        mock.patch("aeon_capabilities.evaluate_capability_policy", return_value={"allowed": False, "effect": "block", "violations": []}),
        mock.patch("aeon_capabilities.CapabilityRegistry.invoke") as invoke,
    ):
        result = resolve_approval("approval-cap-blocked", "approved", "user-1", workspace_id="workspace-1")

    assert result == {"ok": False, "error": "capability is now blocked by workspace policy"}
    invoke.assert_not_called()


def test_second_resolver_cannot_execute_when_atomic_claim_is_empty(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-key")

    from aeon_automations import resolve_approval

    with (
        mock.patch("requests.patch", return_value=_response([])) as patch_request,
        mock.patch("requests.get", return_value=_response([_approval(status="processing", claimed_by="other-user")])),
        mock.patch("aeon_automations.execute_action_by_type") as execute,
    ):
        result = resolve_approval("approval-1", "approved", "user-2", workspace_id="workspace-1")

    assert result == {"ok": False, "error": "approval request is currently being resolved"}
    execute.assert_not_called()
    patch_request.assert_called_once()


def test_expired_approval_is_marked_expired_and_not_executed(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-key")

    from aeon_automations import resolve_approval

    expired = _approval(
        expires_at=(datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
    )
    with (
        mock.patch("requests.patch", side_effect=[_response([]), _response([{"status": "expired"}])]) as patch_request,
        mock.patch("requests.get", return_value=_response([expired])),
        mock.patch("aeon_automations.execute_action_by_type") as execute,
    ):
        result = resolve_approval("approval-1", "approved", "user-1", workspace_id="workspace-1")

    assert result == {"ok": False, "error": "approval request expired"}
    assert patch_request.call_count == 2
    assert patch_request.call_args_list[1].kwargs["json"]["status"] == "expired"
    execute.assert_not_called()


def test_resolver_rejects_already_resolved_approval_without_execution(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-key")

    from aeon_automations import resolve_approval

    with (
        mock.patch("requests.patch", return_value=_response([])),
        mock.patch("requests.get", return_value=_response([_approval(status="approved")])),
        mock.patch("aeon_automations.execute_action_by_type") as execute,
    ):
        result = resolve_approval("approval-1", "approved", "user-1", workspace_id="workspace-1")

    assert result == {"ok": False, "error": "approval request already approved"}
    execute.assert_not_called()
