"""Regression tests for the unified AEON capability registry."""

from __future__ import annotations

import uuid
from unittest.mock import patch

from aeon_capabilities import (
    CapabilityRegistry,
    evaluate_capability_policy,
    validate_capability_arguments,
)
from aeon_marketplace import reset_marketplace_manager
from aeon_mcp import McpManager


def test_registry_discovers_builtin_and_workspace_plugin_capabilities(tmp_path, monkeypatch):
    monkeypatch.setenv("AEON_ROOT", str(tmp_path))
    reset_marketplace_manager()
    registry = CapabilityRegistry(tmp_path)
    manager = registry.root

    from aeon_marketplace import get_marketplace_manager

    marketplace = get_marketplace_manager(manager)
    assert marketplace.install("workspace-a", "sentiment-analyzer")["ok"] is True

    capabilities = registry.discover("workspace-a")
    ids = {capability["id"] for capability in capabilities}
    assert "builtin:math" in ids
    assert "plugin:sentiment-analyzer:analyze" in ids
    assert all("auth_token" not in str(capability) for capability in capabilities)

    other_ids = {capability["id"] for capability in registry.discover("workspace-b")}
    assert "plugin:sentiment-analyzer:analyze" not in other_ids


def test_registry_discovers_only_enabled_mcp_tools(tmp_path, monkeypatch):
    monkeypatch.setenv("AEON_ROOT", str(tmp_path))
    mcp = McpManager(tmp_path)
    server = mcp.add_server("workspace-a", "Research", "https://mcp.example/research")
    state = mcp._load_state()
    state["servers"][0]["tools"] = [
        {"name": "lookup", "description": "Look up a record", "inputSchema": {"type": "object"}}
    ]
    mcp._save_state(state)

    registry = CapabilityRegistry(tmp_path)
    capabilities = registry.discover("workspace-a")
    lookup = next(cap for cap in capabilities if cap["id"] == f"mcp:{server.id}:lookup")
    assert lookup["source"] == "mcp"
    assert lookup["server_name"] == "Research"
    assert lookup["input_schema"] == {"type": "object"}

    mcp.set_enabled("workspace-a", server.id, False)
    assert not any(cap["id"] == f"mcp:{server.id}:lookup" for cap in registry.discover("workspace-a"))


def test_capability_arguments_validate_mcp_json_schema():
    capability = {
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string"},
                "units": {"type": "string", "enum": ["metric", "imperial"]},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["city"],
            "additionalProperties": False,
        }
    }

    assert validate_capability_arguments(capability, {"city": "Paris", "units": "metric"}) is None
    assert "required fields" in (validate_capability_arguments(capability, {}) or "")
    assert "must be a string" in (validate_capability_arguments(capability, {"city": 42}) or "")
    assert "declared values" in (validate_capability_arguments(capability, {"city": "Paris", "units": "kelvin"}) or "")
    assert "unknown fields" in (validate_capability_arguments(capability, {"city": "Paris", "debug": True}) or "")
    assert "must be a string" in (validate_capability_arguments(capability, {"city": "Paris", "tags": ["ok", 1]}) or "")
    assert "arguments must be an object" in (validate_capability_arguments(capability, []) or "")


def test_admin_marketplace_permissions_require_admin_role(tmp_path, monkeypatch):
    monkeypatch.setenv("AEON_ROOT", str(tmp_path))
    reset_marketplace_manager()
    from aeon_marketplace import get_marketplace_manager

    marketplace = get_marketplace_manager(tmp_path)
    assert marketplace.install("workspace-a", "access-review")["ok"] is True
    registry = CapabilityRegistry(tmp_path)

    capability = registry.get("workspace-a", "plugin:access-review:review")
    assert capability is not None
    assert "admin" in capability["permissions"]

    denied = registry.invoke(
        "workspace-a",
        "plugin:access-review:review",
        {},
        user_role="OPERATOR",
    )
    assert denied == {"ok": False, "error": "capability requires ADMIN role"}

    allowed = registry.invoke(
        "workspace-a",
        "plugin:access-review:review",
        {},
        user_role="ADMIN",
    )
    assert allowed["ok"] is True


def test_workspace_capability_policy_blocks_and_allows_wildcards(tmp_path, monkeypatch):
    monkeypatch.setenv("AEON_DATABASE_URL", f"sqlite:///{tmp_path}/aeon.db")
    from aeon_db import create_automation_policy, init_db

    init_db()
    create_automation_policy(
        workspace_id="workspace-a",
        name="Block external research plugins",
        effect="block",
        rules={"blocked_capabilities": ["plugin:research:*"]},
    )
    blocked = evaluate_capability_policy("workspace-a", "plugin:research:lookup")
    assert blocked["allowed"] is False
    assert blocked["effect"] == "block"

    allowed = evaluate_capability_policy("workspace-a", "plugin:sentiment-analyzer:analyze")
    assert allowed == {"allowed": True, "effect": "allow", "violations": []}


def test_registry_invocation_honors_workspace_capability_policy(tmp_path, monkeypatch):
    monkeypatch.setenv("AEON_ROOT", str(tmp_path))
    monkeypatch.setenv("AEON_DATABASE_URL", f"sqlite:///{tmp_path}/aeon.db")
    reset_marketplace_manager()
    from aeon_db import create_automation_policy, init_db
    from aeon_marketplace import get_marketplace_manager

    init_db()
    get_marketplace_manager(tmp_path).install("workspace-a", "sentiment-analyzer")
    create_automation_policy(
        workspace_id="workspace-a",
        name="Disable sentiment execution",
        effect="block",
        rules={"blocked_capabilities": ["plugin:sentiment-analyzer:*"]},
    )

    result = CapabilityRegistry(tmp_path).invoke(
        "workspace-a",
        "plugin:sentiment-analyzer:analyze",
        {"text": "should not run"},
        user_role="OPERATOR",
    )
    assert result["ok"] is False
    assert result["error"] == "capability blocked by workspace policy"
    assert result["policy"][0]["rule"] == "blocked_capabilities"


def test_capability_route_creates_pending_approval_without_execution(client, monkeypatch):
    response = client.post(
        "/auth/register",
        json={
            "email": f"capabilities-approval-{uuid.uuid4().hex[:8]}@test.local",
            "password": "secure123",
            "name": "Capabilities Approval",
        },
    )
    assert response.status_code == 201
    data = response.get_json()
    headers = {"Authorization": f"Bearer {data['token']}"}

    from aeon_db import create_automation_policy

    create_automation_policy(
        workspace_id=data["user"]["workspace_id"],
        name="Approval for math",
        effect="require_approval",
        rules={"allowed_capabilities": ["builtin:fetch"]},
    )

    with patch(
        "aeon_automations._create_approval_request",
        return_value={"ok": True, "approval": {"id": "approval-cap-1"}},
    ) as creator, patch("aeon_capabilities_routes.get_capability_registry") as registry:
        registry.return_value.invoke.return_value = {
            "ok": False,
            "error": "capability requires approval by workspace policy",
            "policy": [{"rule": "allowed_capabilities"}],
        }
        result = client.post(
            "/capabilities/invoke",
            headers=headers,
            json={"capability_id": "builtin:math", "arguments": {"expr": "2 + 2"}},
        )

    assert result.status_code == 202
    body = result.get_json()
    assert body["status"] == "pending"
    assert body["approval_id"] == "approval-cap-1"
    creator.assert_called_once()
    registry.return_value.invoke.assert_called_once()
    assert registry.return_value.invoke.call_args.args[0:2] == (data["user"]["workspace_id"], "builtin:math")


def test_registry_invokes_builtin_and_plugin_with_fail_closed_ids(tmp_path, monkeypatch):
    monkeypatch.setenv("AEON_ROOT", str(tmp_path))
    reset_marketplace_manager()
    from aeon_marketplace import get_marketplace_manager

    get_marketplace_manager(tmp_path).install("workspace-a", "sentiment-analyzer")
    registry = CapabilityRegistry(tmp_path)

    builtin = registry.invoke("workspace-a", "builtin:math", {"expr": "2 + 2"})
    assert builtin["ok"] is True
    assert "4" in builtin["output"]

    plugin = registry.invoke(
        "workspace-a",
        "plugin:sentiment-analyzer:analyze",
        {"text": "AEON is modular"},
    )
    assert plugin["ok"] is True
    assert plugin["summary"] == "AEON is modular"

    missing = registry.invoke("workspace-b", "plugin:sentiment-analyzer:analyze", {})
    assert missing == {"ok": False, "error": "capability not found in workspace"}


def test_capability_route_audits_allowed_decision_without_arguments(client):
    response = client.post(
        "/auth/register",
        json={
            "email": f"capabilities-audit-{uuid.uuid4().hex[:8]}@test.local",
            "password": "secure123",
            "name": "Capabilities Audit",
        },
    )
    assert response.status_code == 201
    headers = {"Authorization": f"Bearer {response.get_json()['token']}"}

    with patch("aeon_governance.get_governance") as get_governance:
        result = client.post(
            "/capabilities/invoke",
            headers=headers,
            json={"capability_id": "builtin:math", "arguments": {"expr": "2 + 2"}},
        )

    assert result.status_code == 200
    metadata = get_governance.return_value.log_audit.call_args.kwargs["metadata"]
    assert metadata["decision"] == "allowed"
    assert metadata["reason"] == "success"
    assert "arguments" not in metadata


def test_capability_route_audits_policy_denial_without_arguments(client):
    response = client.post(
        "/auth/register",
        json={
            "email": f"capabilities-policy-audit-{uuid.uuid4().hex[:8]}@test.local",
            "password": "secure123",
            "name": "Capabilities Policy Audit",
        },
    )
    assert response.status_code == 201
    data = response.get_json()
    headers = {"Authorization": f"Bearer {data['token']}"}

    from aeon_db import create_automation_policy

    create_automation_policy(
        workspace_id=data["user"]["workspace_id"],
        name="Block math",
        effect="block",
        rules={"blocked_capabilities": ["builtin:math"]},
    )

    with patch("aeon_governance.get_governance") as get_governance:
        result = client.post(
            "/capabilities/invoke",
            headers=headers,
            json={"capability_id": "builtin:math", "arguments": {"expr": "secret input"}},
        )

    assert result.status_code == 403
    metadata = get_governance.return_value.log_audit.call_args.kwargs["metadata"]
    assert metadata["decision"] == "denied"
    assert metadata["reason"] == "policy_denied"
    assert metadata["policy_violation_count"] == 1
    assert "arguments" not in metadata


def test_capability_audit_route_is_workspace_scoped_and_read_only(client):
    response = client.post(
        "/auth/register",
        json={
            "email": f"capabilities-audit-viewer-{uuid.uuid4().hex[:8]}@test.local",
            "password": "secure123",
            "name": "Capabilities Audit Viewer",
        },
    )
    assert response.status_code == 201
    token = response.get_json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    with patch("aeon_governance.get_governance") as get_governance:
        get_governance.return_value.query_audit.return_value = {
            "ok": True,
            "rows": [
                {
                    "id": "audit-1",
                    "workspace_id": "must-match-request-workspace",
                    "action": "capability_invocation",
                    "module": "capabilities",
                    "metadata": {
                        "capability_id": "builtin:math",
                        "decision": "allowed",
                        "reason": "success",
                        "user_role": "OPERATOR",
                    },
                },
                {
                    "id": "audit-2",
                    "workspace_id": "must-match-request-workspace",
                    "action": "capability_invocation",
                    "module": "capabilities",
                    "metadata": {
                        "capability_id": "builtin:fetch",
                        "decision": "denied",
                        "reason": "policy_denied",
                    },
                },
            ],
        }
        result = client.get("/capabilities/audit?limit=1", headers=headers)

    assert result.status_code == 200
    body = result.get_json()
    assert body["ok"] is True
    assert body["count"] == 1
    assert body["has_more"] is True
    assert body["logs"][0]["metadata"]["capability_id"] == "builtin:math"
    get_governance.return_value.query_audit.assert_called_once_with(
        workspace_id=body["workspace_id"],
        action="capability_invocation",
        module="capabilities",
        limit=2,
        offset=0,
    )


def test_capability_audit_route_returns_service_unavailable_on_query_failure(client):
    response = client.post(
        "/auth/register",
        json={
            "email": f"capabilities-audit-unavailable-{uuid.uuid4().hex[:8]}@test.local",
            "password": "secure123",
            "name": "Capabilities Audit Unavailable",
        },
    )
    assert response.status_code == 201
    headers = {"Authorization": f"Bearer {response.get_json()['token']}"}

    with patch("aeon_governance.get_governance") as get_governance:
        get_governance.return_value.query_audit.return_value = {
            "ok": False,
            "rows": [],
            "error": "database unavailable",
        }
        result = client.get("/capabilities/audit", headers=headers)

    assert result.status_code == 503
    assert result.get_json() == {"error": "audit service unavailable", "ok": False}


def test_capability_route_continues_when_audit_delivery_fails(client):
    response = client.post(
        "/auth/register",
        json={
            "email": f"capabilities-audit-failure-{uuid.uuid4().hex[:8]}@test.local",
            "password": "secure123",
            "name": "Capabilities Audit Failure",
        },
    )
    assert response.status_code == 201
    headers = {"Authorization": f"Bearer {response.get_json()['token']}"}

    with patch("aeon_governance.get_governance", side_effect=RuntimeError("audit unavailable")):
        result = client.post(
            "/capabilities/invoke",
            headers=headers,
            json={"capability_id": "builtin:math", "arguments": {"expr": "2 + 2"}},
        )

    assert result.status_code == 200
    assert result.get_json()["ok"] is True


def test_capability_route_enforces_marketplace_admin_permissions(client):
    response = client.post(
        "/auth/register",
        json={
            "email": f"capabilities-admin-{uuid.uuid4().hex[:8]}@test.local",
            "password": "secure123",
            "name": "Capabilities Admin",
        },
    )
    assert response.status_code == 201
    data = response.get_json()
    token = data["token"]
    user_id = data["user"]["id"]
    workspace_id = data["user"]["workspace_id"]
    headers = {"Authorization": f"Bearer {token}"}

    install = client.post(
        "/marketplace/plugins/access-review/install", headers=headers, json={}
    )
    assert install.status_code == 201

    from aeon_db import Membership, get_db

    db = get_db()
    with db.session() as session:
        membership = (
            session.query(Membership)
            .filter_by(workspace_id=workspace_id, user_id=user_id)
            .first()
        )
        assert membership is not None
        membership.role = "OPERATOR"
        session.commit()

    denied = client.post(
        "/capabilities/invoke",
        headers=headers,
        json={
            "capability_id": "plugin:access-review:review",
            "arguments": {},
        },
    )
    assert denied.status_code == 403
    assert denied.get_json()["error"] == "capability requires ADMIN role"


def test_capability_routes_require_auth_and_return_workspace_scoped_data(client):
    assert client.get("/capabilities").status_code == 401
    assert client.post("/capabilities/invoke", json={}).status_code == 401

    response = client.post(
        "/auth/register",
        json={
            "email": f"capabilities-owner-{uuid.uuid4().hex[:8]}@test.local",
            "password": "secure123",
            "name": "Capabilities",
        },
    )
    assert response.status_code == 201
    token = response.get_json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    discovered = client.get("/capabilities", headers=headers)
    assert discovered.status_code == 200
    body = discovered.get_json()
    assert body["ok"] is True
    assert body["source_counts"]["builtin"] >= 1
    assert all("auth_token" not in str(capability) for capability in body["capabilities"])

    install = client.post(
        "/marketplace/plugins/sentiment-analyzer/install",
        headers=headers,
        json={},
    )
    assert install.status_code == 201
    result = client.post(
        "/capabilities/invoke",
        headers=headers,
        json={
            "capability_id": "plugin:sentiment-analyzer:analyze",
            "arguments": {"text": "AEON is modular"},
        },
    )
    assert result.status_code == 200
    assert result.get_json()["ok"] is True

    unknown = client.post(
        "/capabilities/invoke",
        headers=headers,
        json={"capability_id": "plugin:other-workspace:run", "arguments": {}},
    )
    assert unknown.status_code == 404
