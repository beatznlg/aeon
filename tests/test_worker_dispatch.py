"""Tests for Phase 43 distributed automation execution."""

from unittest.mock import patch

import pytest


@pytest.fixture
def sample_rule():
    return {
        "id": "rule-123",
        "name": "Test Rule",
        "workspace_id": "ws-123",
        "enabled": True,
        "condition": None,
        "actions": [{"type": "webhook", "config": {"url": "http://example.com/hook"}}],
        "cooldown_minutes": 0,
        "approval_required": False,
    }


def test_execute_rule_by_id_not_found():
    from aeon_automations import execute_rule_by_id

    result = execute_rule_by_id("missing-id", {"workspace_id": "ws-123"})
    assert result["ok"] is False
    assert result["error"] == "rule not found"


def test_execute_rule_by_id_runs_action(sample_rule):
    from aeon_automations import execute_rule_by_id

    with (patch("aeon_automations._fetch_rule_by_id", return_value=sample_rule) as _fetch,
          patch("aeon_automations._execute_action", return_value={"ok": True, "status": "completed"}) as _exec,
          patch("aeon_automations._update_last_triggered") as mock_update):
        result = execute_rule_by_id("rule-123", {"workspace_id": "ws-123"})

    assert result["ok"] is True
    assert result["status"] == "completed"
    assert result["rule_id"] == "rule-123"
    mock_update.assert_called_once()


def test_evaluate_automations_use_worker_false(sample_rule):
    from aeon_automations import evaluate_automations

    with patch("aeon_automations._fetch_rules_for_event", return_value=[sample_rule]), \
            patch("aeon_automations.execute_rule_by_id", return_value={"ok": True, "status": "completed"}) as mock_exec:
        results = evaluate_automations("system", {"status": "ok"}, workspace_id="ws-123", use_worker=False)

    assert len(results) == 1
    assert results[0]["rule_id"] == "rule-123"
    mock_exec.assert_called_once()


def test_dispatch_to_worker_runs_sync_in_eager_mode():
    from aeon_automations import _dispatch_to_worker

    with patch("aeon_automations.execute_rule_by_id", return_value={"ok": True, "status": "completed"}) as mock_exec:
        result = _dispatch_to_worker("rule-123", {"workspace_id": "ws-123"})

    # In eager mode the task is run synchronously and the function falls back
    # to the inline execution result.
    assert result["ok"] is True
    assert result["status"] == "completed"
    mock_exec.assert_called_once_with("rule-123", {"workspace_id": "ws-123"})
