"""Tests for the ``plugin`` automation action type.

Verifies that automation rules can invoke marketplace plugin entry points,
including template interpolation, dry-run simulation, workspace scoping, and
fail-closed behavior when a plugin is missing or disabled.
"""

from __future__ import annotations

import uuid

from aeon_automations import execute_action_by_type


def _register(client, label: str) -> tuple[str, str]:
    """Create a test workspace owner and return (token, workspace_id)."""
    response = client.post(
        "/auth/register",
        json={
            "email": f"plugin-{label}-{uuid.uuid4().hex[:8]}@test.local",
            "password": "secure123",
            "name": f"Plugin {label}",
        },
    )
    assert response.status_code == 201, response.get_json()
    data = response.get_json()
    return data["token"], data["user"]["workspace_id"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _install(client, token, plugin_id: str, config: dict | None = None) -> dict:
    response = client.post(
        f"/marketplace/plugins/{plugin_id}/install",
        headers=_headers(token),
        json={"config": config or {}},
    )
    assert response.status_code == 201, response.get_json()
    return response.get_json()["install"]


def _run_plugin_action(workspace_id: str, action_config: dict, event: dict | None = None, dry_run: bool = False) -> dict:
    """Invoke the plugin action through the automation engine's dispatcher."""
    context = {
        "event": event or {"type": "test.event", "payload": {}, "workspace_id": workspace_id},
        "rule": {"id": "rule-1", "workspace_id": workspace_id},
        "steps": [],
    }
    return execute_action_by_type("plugin", action_config, context, dry_run=dry_run)


def test_plugin_action_runs_installed_entry_with_interpolation(client) -> None:
    token, workspace_id = _register(client, "exec")
    _install(client, token, "sentiment-analyzer")

    result = _run_plugin_action(
        workspace_id,
        {
            "plugin_id": "sentiment-analyzer",
            "entry": "analyze",
            "params": {"text": "{{ event.payload.text }}"},
        },
        event={"type": "ticket.created", "payload": {"text": "AEON is great"}, "workspace_id": workspace_id},
    )

    assert result["ok"] is True
    assert result["plugin_id"] == "sentiment-analyzer"
    assert result["entry"] == "analyze"
    assert result["workspace_id"] == workspace_id
    assert result["stats"]["words"] == 3


def test_plugin_action_requires_plugin_id_and_entry(client) -> None:
    token, workspace_id = _register(client, "config")

    missing_id = _run_plugin_action(workspace_id, {"entry": "analyze"})
    assert missing_id["ok"] is False
    assert "plugin_id and entry" in missing_id["error"]

    missing_entry = _run_plugin_action(workspace_id, {"plugin_id": "sentiment-analyzer"})
    assert missing_entry["ok"] is False
    assert "plugin_id and entry" in missing_entry["error"]


def test_plugin_action_fails_closed_when_not_installed(client) -> None:
    token_a, workspace_a = _register(client, "not-installed-a")
    token_b, _workspace_b = _register(client, "not-installed-b")
    # Install for workspace B only.
    _install(client, token_b, "fraud-scoring")

    result = _run_plugin_action(workspace_a, {"plugin_id": "fraud-scoring", "entry": "score"})
    assert result["ok"] is False
    assert result["error"] == "plugin not installed"


def test_plugin_action_fails_closed_when_disabled(client) -> None:
    token, workspace_id = _register(client, "disabled")
    _install(client, token, "fraud-scoring")
    disable = client.post(
        "/marketplace/plugins/fraud-scoring/disable", headers=_headers(token)
    )
    assert disable.status_code == 200

    result = _run_plugin_action(
        workspace_id, {"plugin_id": "fraud-scoring", "entry": "score", "params": {"risk": 0.9}}
    )
    assert result["ok"] is False
    assert result["error"] == "plugin disabled"


def test_plugin_action_workspace_isolation(client) -> None:
    token_a, workspace_a = _register(client, "iso-a")
    _token_b, workspace_b = _register(client, "iso-b")
    _install(client, token_a, "sentiment-analyzer")

    # Workspace A can run the plugin…
    ok_a = _run_plugin_action(workspace_a, {"plugin_id": "sentiment-analyzer", "entry": "analyze"})
    assert ok_a["ok"] is True

    # …but workspace B cannot (its own install store is empty).
    missing_b = _run_plugin_action(workspace_b, {"plugin_id": "sentiment-analyzer", "entry": "analyze"})
    assert missing_b["ok"] is False
    assert missing_b["error"] == "plugin not installed"


def test_plugin_action_dry_run_simulates_without_installing(client) -> None:
    token, workspace_id = _register(client, "dry-run")
    # Nothing installed — dry run must still preview cleanly.
    result = _run_plugin_action(
        workspace_id,
        {"plugin_id": "incident-responder", "entry": "triage"},
        dry_run=True,
    )
    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["simulated"] is True
    assert result["plugin_id"] == "incident-responder"

    missing_config = _run_plugin_action(workspace_id, {"entry": "triage"}, dry_run=True)
    assert missing_config["ok"] is False
    assert "plugin_id and entry" in missing_config["error"]


def test_plugin_action_unknown_plugin_rejected(client) -> None:
    token, workspace_id = _register(client, "unknown")
    _install(client, token, "sentiment-analyzer")

    result = _run_plugin_action(workspace_id, {"plugin_id": "does-not-exist", "entry": "analyze"})
    assert result["ok"] is False
    assert result["error"] == "plugin not installed"


def test_plugin_action_unknown_entry_rejected(client) -> None:
    token, workspace_id = _register(client, "bad-entry")
    _install(client, token, "sentiment-analyzer")

    result = _run_plugin_action(workspace_id, {"plugin_id": "sentiment-analyzer", "entry": "nope"})
    assert result["ok"] is False
    assert "unknown entry point" in result["error"]
