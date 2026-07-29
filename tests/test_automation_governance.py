"""Tests for AEON automation governance & audit logs — Phase 40."""

import pytest


@pytest.fixture
def isolated_governance(tmp_path, monkeypatch):
    """Return a GovernanceManager that writes audit logs to a temp SQLite DB."""
    monkeypatch.setenv("AEON_DATABASE_URL", f"sqlite:///{tmp_path}/aeon.db")
    # Ensure no Supabase credentials are present so the local fallback is used.
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)

    from aeon_db import init_db
    from aeon_governance import GovernanceManager

    init_db()
    gm = GovernanceManager(batch_size=1, flush_interval=0.1)
    yield gm
    gm.shutdown()


def _flush_event(gm):
    """Pull the most recently queued event and flush it synchronously."""
    events = []
    while not gm._queue.empty():
        try:
            ev = gm._queue.get_nowait()
            if ev is not None:
                events.append(ev)
        except Exception:  # pragma: no cover
            break
    if events:
        gm._flush(events)
    return events


def test_governance_logs_automation_event_to_local_db(isolated_governance):
    gm = isolated_governance
    event = gm.log_audit(
        action="automation_created",
        module="automations",
        user_id="user-1",
        workspace_id="ws-1",
        email="admin@example.com",
        metadata={"rule_id": "rule-1", "name": "Test Rule"},
    )
    assert event is not None
    _flush_event(gm)

    result = gm.query_audit(workspace_id="ws-1", module="automations")
    assert result["ok"] is True
    assert result["count"] == 1
    row = result["rows"][0]
    assert row["action"] == "automation_created"
    assert row["module"] == "automations"
    assert row["workspace_id"] == "ws-1"
    assert row["metadata"]["rule_id"] == "rule-1"


def test_governance_filters_audit_by_action(isolated_governance):
    gm = isolated_governance
    gm.log_audit(action="automation_created", module="automations", workspace_id="ws-2")
    gm.log_audit(action="automation_deleted", module="automations", workspace_id="ws-2")
    _flush_event(gm)

    created = gm.query_audit(workspace_id="ws-2", action="automation_created")
    assert created["count"] == 1
    assert created["rows"][0]["action"] == "automation_created"

    all_rows = gm.query_audit(workspace_id="ws-2")
    assert all_rows["count"] == 2


def test_governance_export_audit_redacts_pii(isolated_governance):
    gm = isolated_governance
    gm.log_audit(
        action="automation_run",
        module="automations",
        workspace_id="ws-3",
        metadata={"note": "Contact me at admin@example.com"},
    )
    _flush_event(gm)

    rows = gm.query_audit(workspace_id="ws-3")["rows"]
    export = gm.export_audit(rows)
    assert export["ok"] is True
    assert "[EMAIL_REDACTED]" in export["rows"][0]["metadata"]["note"]
