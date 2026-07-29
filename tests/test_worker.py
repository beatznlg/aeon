"""Tests for aeon_worker Celery tasks in eager mode."""

import pytest


@pytest.fixture(autouse=True)
def _eager_celery(monkeypatch):
    """Force Celery into eager mode for tests."""
    monkeypatch.setenv("AEON_REDIS_URL", "")
    monkeypatch.setenv("REDIS_URL", "")


def test_worker_import_and_eager_mode():
    from aeon_worker import app, execute_automation_task

    assert app.conf.task_always_eager is True
    # Running the task should complete synchronously because we are in eager mode.
    # It will fail inside the worker because the rule_id does not exist, but it
    # proves the task path is wired and returns a structured result.
    result = execute_automation_task.run("nonexistent-rule", {"source": "test"})
    assert isinstance(result, dict)
    assert "rule_id" in result
    assert result["rule_id"] == "nonexistent-rule"
    assert "ok" in result
