"""Regression tests for the AEON OS domain event architecture."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from aeon_db import Base, EventConsumption, OutboxEvent, get_db
from aeon_events import (
    ALL_EVENT_TYPES,
    USER_REGISTERED,
    WORKSPACE_CREATED,
    MEMBERSHIP_CREATED,
    PLUGIN_INSTALLED,
    PLUGIN_REMOVED,
    SECTOR_DATA_CHANGED,
    AUTOMATION_TRIGGERED,
    AUTOMATION_COMPLETED,
    AUTOMATION_FAILED,
    EventRelay,
    _payload_hash,
    emit,
    get_consumer_registry,
    outbox_stats,
    publish_event,
    query_outbox,
    register_consumer,
)


def _setup_db(tmp_path):
    """Create an in-memory SQLite DB with event tables."""
    from sqlalchemy import create_engine, text

    database_url = f"sqlite:///{tmp_path / 'events.db'}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    return engine, database_url


def test_event_type_constants_are_complete():
    """All expected domain event types should be defined."""
    expected = {
        "workspace.created", "workspace.updated", "workspace.deleted",
        "membership.created", "membership.role_changed", "membership.removed",
        "user.registered", "user.login", "user.logout",
        "subscription.created", "subscription.updated", "subscription.cancelled",
        "billing.checkout_completed", "billing.payment_failed",
        "plugin.installed", "plugin.removed",
        "sector.updated", "sector.data_changed",
        "automation.triggered", "automation.completed", "automation.failed",
        "automation.approval_requested",
        "ai.execution.recorded", "ai.governance.blocked",
        "security.rate_limited", "security.login_failed", "security.jwt_rotated",
    }
    assert expected == set(ALL_EVENT_TYPES)


def test_publish_event_writes_to_outbox(tmp_path):
    """publish_event should insert a row into the outbox_events table."""
    from sqlalchemy import create_engine, inspect

    engine, db_url = _setup_db(tmp_path)
    from aeon_db import Database

    db = Database(db_url)

    with db.session() as s:
        event_id = publish_event(
            WORKSPACE_CREATED,
            tenant_id="t-1",
            workspace_id="ws-1",
            payload={"name": "Test Workspace", "plan": "free"},
            session=s,
        )
        s.commit()

    assert event_id is not None

    with db.session() as s:
        event = s.query(OutboxEvent).filter(OutboxEvent.id == event_id).first()
        assert event is not None
        assert event.event_type == WORKSPACE_CREATED
        assert event.tenant_id == "t-1"
        assert event.workspace_id == "ws-1"
        assert event.status == "pending"
        assert event.payload["name"] == "Test Workspace"
        assert event.payload_hash == _payload_hash({"name": "Test Workspace", "plan": "free"})


def test_publish_event_without_session(tmp_path, monkeypatch):
    """publish_event should work without an explicit session by getting one from the DB layer."""
    from aeon_db import Database

    engine, db_url = _setup_db(tmp_path)
    monkeypatch.setenv("AEON_DATABASE_URL", db_url)

    # Patch get_db to return our test DB
    test_db = Database(db_url)

    with patch("aeon_db.get_db", return_value=test_db):
        event_id = publish_event(
            USER_REGISTERED,
            tenant_id="t-1",
            workspace_id="ws-1",
            payload={"email": "test@example.com"},
        )

    assert event_id is not None
    with test_db.session() as s:
        event = s.query(OutboxEvent).filter(OutboxEvent.id == event_id).first()
        assert event is not None
        assert event.event_type == USER_REGISTERED


def test_consumer_registry():
    """Consumers should be registered and retrievable."""
    registry = get_consumer_registry()
    # Built-in security consumers should be registered
    assert "security.rate_limited" in registry or "security.login_failed" in registry


def test_register_custom_consumer():
    """Custom consumers should be callable and receive events."""
    calls = []

    def my_handler(event_id: str, payload: dict):
        calls.append((event_id, payload))

    register_consumer("test.custom.event", my_handler, "test-handler")
    registry = get_consumer_registry()
    assert "test.custom.event" in registry
    assert my_handler in registry["test.custom.event"]


def test_relay_dispatches_to_consumers(tmp_path, monkeypatch):
    """The event relay should dispatch pending events to registered consumers."""
    from aeon_db import Database

    engine, db_url = _setup_db(tmp_path)
    monkeypatch.setenv("AEON_DATABASE_URL", db_url)
    test_db = Database(db_url)

    calls = []

    def tracking_handler(event_id: str, payload: dict):
        calls.append(event_id)

    register_consumer("test.dispatch", tracking_handler, "test-dispatch")

    # Insert a pending event directly
    with test_db.session() as s:
        now = datetime.now(timezone.utc)
        event = OutboxEvent(
            id="evt-dispatch-1",
            tenant_id="t-1",
            workspace_id="ws-1",
            aggregate_type="test",
            aggregate_id="agg-1",
            aggregate_version=1,
            event_type="test.dispatch",
            event_version=1,
            schema_uri="aeon://events/test.dispatch/v1",
            payload={"key": "value"},
            payload_hash="abc123",
            occurred_at=now,
            created_at=now,
            available_at=now,
            status="pending",
            attempt_count=0,
        )
        s.add(event)
        s.commit()

    # Run the relay tick
    with patch("aeon_db.get_db", return_value=test_db):
        relay = EventRelay(max_attempts=3)
        processed = relay._tick()

    assert processed >= 1
    assert "evt-dispatch-1" in calls

    # Verify event is now published
    with test_db.session() as s:
        e = s.query(OutboxEvent).filter(OutboxEvent.id == "evt-dispatch-1").first()
        assert e.status == "published"
        assert e.published_at is not None


def test_consumer_idempotency(tmp_path, monkeypatch):
    """A consumer should not process the same event twice."""
    from aeon_db import Database

    engine, db_url = _setup_db(tmp_path)
    monkeypatch.setenv("AEON_DATABASE_URL", db_url)
    test_db = Database(db_url)

    calls = []

    def idempotent_handler(event_id: str, payload: dict):
        calls.append(event_id)

    register_consumer("test.idempotent", idempotent_handler, "idempotent-h")

    # Insert a pending event
    with test_db.session() as s:
        now = datetime.now(timezone.utc)
        event = OutboxEvent(
            id="evt-idem-1",
            tenant_id="t-1",
            aggregate_type="test",
            aggregate_id="a-1",
            aggregate_version=1,
            event_type="test.idempotent",
            event_version=1,
            schema_uri="aeon://events/test.idempotent/v1",
            payload={"x": 1},
            payload_hash="hash1",
            occurred_at=now,
            created_at=now,
            available_at=now,
            status="pending",
            attempt_count=0,
        )
        s.add(event)
        s.commit()

    with patch("aeon_db.get_db", return_value=test_db):
        relay = EventRelay(max_attempts=3)
        # First tick: processes the event
        relay._tick()
        assert len(calls) == 1

        # Mark it published, then re-insert as pending for second tick test
        with test_db.session() as s:
            e = s.query(OutboxEvent).filter(OutboxEvent.id == "evt-idem-1").first()
            e.status = "published"

        # Insert another event
        with test_db.session() as s:
            now = datetime.now(timezone.utc)
            event2 = OutboxEvent(
                id="evt-idem-2",
                tenant_id="t-1",
                aggregate_type="test",
                aggregate_id="a-2",
                aggregate_version=1,
                event_type="test.idempotent",
                event_version=1,
                schema_uri="aeon://events/test.idempotent/v1",
                payload={"x": 2},
                payload_hash="hash2",
                occurred_at=now,
                created_at=now,
                available_at=now,
                status="pending",
                attempt_count=0,
            )
            s.add(event2)
            s.commit()

        relay._tick()
        assert len(calls) == 2
        assert calls == ["evt-idem-1", "evt-idem-2"]


def test_duplicate_event_id_skipped(tmp_path, monkeypatch):
    """Two events with the same id should not both be processed by a consumer."""
    from aeon_db import Database

    engine, db_url = _setup_db(tmp_path)
    monkeypatch.setenv("AEON_DATABASE_URL", db_url)
    test_db = Database(db_url)

    calls = []

    def counting_handler(event_id: str, payload: dict):
        calls.append(event_id)

    register_consumer("test.dedup", counting_handler, "dedup-h")

    # Simulate: the relay processes an event, marks it completed,
    # then a duplicate is created with the same id
    now = datetime.now(timezone.utc)

    with test_db.session() as s:
        # First event (already completed by consumer)
        s.add(EventConsumption(
            consumer_name="dedup-h",
            event_id="evt-dedup-1",
            status="completed",
            processed_at=now,
            attempt_count=1,
        ))
        # Second event with same id but different status (retry scenario)
        s.add(OutboxEvent(
            id="evt-dedup-1",
            tenant_id="t-1",
            aggregate_type="test",
            aggregate_id="a-1",
            aggregate_version=1,
            event_type="test.dedup",
            event_version=1,
            schema_uri="aeon://events/test.dedup/v1",
            payload={"retry": True},
            payload_hash="retry-hash",
            occurred_at=now,
            created_at=now,
            available_at=now,
            status="published",
            attempt_count=1,
        ))
        s.commit()

    # Consumer should NOT be called because it's already been marked completed
    with patch("aeon_db.get_db", return_value=test_db):
        relay = EventRelay(max_attempts=3)
        # The event is already published, so _tick won't pick it up
        processed = relay._tick()
        assert len(calls) == 0


def test_relay_exponential_backoff(tmp_path, monkeypatch):
    """Failed events should get increasing backoff."""
    from aeon_db import Database

    engine, db_url = _setup_db(tmp_path)
    monkeypatch.setenv("AEON_DATABASE_URL", db_url)
    test_db = Database(db_url)

    def failing_handler(event_id: str, payload: dict):
        raise RuntimeError("Simulated failure")

    register_consumer("test.backoff", failing_handler, "backoff-h")

    now = datetime.now(timezone.utc)
    with test_db.session() as s:
        s.add(OutboxEvent(
            id="evt-backoff-1",
            tenant_id="t-1",
            aggregate_type="test",
            aggregate_id="a-1",
            aggregate_version=1,
            event_type="test.backoff",
            event_version=1,
            schema_uri="aeon://events/test.backoff/v1",
            payload={},
            payload_hash="x",
            occurred_at=now,
            created_at=now,
            available_at=now,
            status="pending",
            attempt_count=0,
        ))
        s.commit()

    with patch("aeon_db.get_db", return_value=test_db):
        relay = EventRelay(max_attempts=5)
        relay._tick()

    with test_db.session() as s:
        e = s.query(OutboxEvent).filter(OutboxEvent.id == "evt-backoff-1").first()
        assert e.attempt_count == 1
        assert e.status == "pending"  # Not yet at max
        assert e.last_error_code == "DISPATCH_FAILED"
        # Backoff should be 2^1 = 2 seconds
        if e.available_at.tzinfo is not None:
            assert e.available_at > now
        else:
            assert e.available_at > now.replace(tzinfo=None)


def test_query_outbox_and_stats(tmp_path, monkeypatch):
    """query_outbox and outbox_stats should work correctly."""
    from aeon_db import Database

    engine, db_url = _setup_db(tmp_path)
    monkeypatch.setenv("AEON_DATABASE_URL", db_url)
    test_db = Database(db_url)

    now = datetime.now(timezone.utc)
    with test_db.session() as s:
        for i in range(3):
            s.add(OutboxEvent(
                id=f"evt-q-{i}",
                tenant_id="t-1",
                workspace_id="ws-1",
                aggregate_type="test",
                aggregate_id=f"a-{i}",
                aggregate_version=1,
                event_type="test.query" if i < 2 else "test.other",
                event_version=1,
                schema_uri="aeon://events/test/v1",
                payload={"i": i},
                payload_hash=f"hash-{i}",
                occurred_at=now,
                created_at=now,
                available_at=now,
                status="pending" if i == 0 else "published",
                attempt_count=0,
            ))
        s.commit()

    with patch("aeon_db.get_db", return_value=test_db):
        # Query all
        events = query_outbox(limit=10)
        assert len(events) == 3

        # Query by status
        pending = query_outbox(status="pending")
        assert len(pending) == 1

        # Query by type
        query_type = query_outbox(event_type="test.query")
        assert len(query_type) == 2

        # Stats
        stats = outbox_stats()
        assert stats["total"] == 3
        assert stats["pending"] == 1
        assert stats["published"] == 2


def test_emit_enriches_payload(tmp_path, monkeypatch):
    """The emit() helper should enrich the payload with metadata."""
    from aeon_db import Database

    engine, db_url = _setup_db(tmp_path)
    monkeypatch.setenv("AEON_DATABASE_URL", db_url)
    test_db = Database(db_url)

    with patch("aeon_db.get_db", return_value=test_db):
        event_id = emit(
            USER_REGISTERED,
            tenant_id="t-1",
            workspace_id="ws-1",
            user_id="u-1",
            payload={"email": "test@example.com"},
        )

    assert event_id is not None
    with test_db.session() as s:
        event = s.query(OutboxEvent).filter(OutboxEvent.id == event_id).first()
        assert event.event_type == USER_REGISTERED
        assert event.payload["user_id"] == "u-1"
        assert event.payload["workspace_id"] == "ws-1"
        assert event.payload["_event_type"] == USER_REGISTERED
        assert "timestamp" in event.payload


def test_payload_hash_is_deterministic():
    """The same payload should produce the same hash."""
    p = {"key": "value", "nested": {"a": 1}}
    assert _payload_hash(p) == _payload_hash(p)


def test_event_relay_stats():
    """The relay should track dispatch statistics."""
    relay = EventRelay()
    assert relay.stats == {"dispatched": 0, "errors": 0, "skipped": 0}


def test_all_mutation_event_types_are_importable():
    """All event types used in mutation wiring should be importable."""
    # Workspace / membership
    assert WORKSPACE_CREATED == "workspace.created"
    assert MEMBERSHIP_CREATED == "membership.created"
    assert USER_REGISTERED == "user.registered"
    # Plugins
    assert PLUGIN_INSTALLED == "plugin.installed"
    assert PLUGIN_REMOVED == "plugin.removed"
    # Sectors
    assert SECTOR_DATA_CHANGED == "sector.data_changed"
    # Automations
    assert AUTOMATION_TRIGGERED == "automation.triggered"
    assert AUTOMATION_COMPLETED == "automation.completed"
    assert AUTOMATION_FAILED == "automation.failed"


def test_emit_plugin_installed_event(tmp_path, monkeypatch):
    """emit() should correctly write a PLUGIN_INSTALLED event to the outbox."""
    from aeon_db import Database

    engine, db_url = _setup_db(tmp_path)
    monkeypatch.setenv("AEON_DATABASE_URL", db_url)
    test_db = Database(db_url)

    with patch("aeon_db.get_db", return_value=test_db):
        event_id = emit(
            PLUGIN_INSTALLED,
            tenant_id="",
            workspace_id="ws-1",
            payload={"plugin_id": "workflow-orchestrator", "version": "1.0.0"},
        )

    assert event_id is not None
    with test_db.session() as s:
        event = s.query(OutboxEvent).filter(OutboxEvent.id == event_id).first()
        assert event is not None
        assert event.event_type == PLUGIN_INSTALLED
        assert event.payload["plugin_id"] == "workflow-orchestrator"
        assert event.payload["_event_type"] == PLUGIN_INSTALLED


def test_emit_sector_data_changed_event(tmp_path, monkeypatch):
    """emit() should correctly write a SECTOR_DATA_CHANGED event."""
    from aeon_db import Database

    engine, db_url = _setup_db(tmp_path)
    monkeypatch.setenv("AEON_DATABASE_URL", db_url)
    test_db = Database(db_url)

    with patch("aeon_db.get_db", return_value=test_db):
        event_id = emit(
            SECTOR_DATA_CHANGED,
            tenant_id="",
            workspace_id="ws-1",
            payload={"sector": "cybersecurity", "tool": "threats", "version": 2},
        )

    assert event_id is not None
    with test_db.session() as s:
        event = s.query(OutboxEvent).filter(OutboxEvent.id == event_id).first()
        assert event is not None
        assert event.event_type == SECTOR_DATA_CHANGED
        assert event.payload["sector"] == "cybersecurity"
        assert event.payload["tool"] == "threats"


def test_emit_automation_completed_event(tmp_path, monkeypatch):
    """emit() should correctly write an AUTOMATION_COMPLETED event."""
    from aeon_db import Database

    engine, db_url = _setup_db(tmp_path)
    monkeypatch.setenv("AEON_DATABASE_URL", db_url)
    test_db = Database(db_url)

    with patch("aeon_db.get_db", return_value=test_db):
        event_id = emit(
            AUTOMATION_COMPLETED,
            tenant_id="",
            workspace_id="ws-1",
            payload={"rule_id": "rule-1", "rule_name": "Send Report", "dry_run": False, "result_ok": True, "status": "completed"},
        )

    assert event_id is not None
    with test_db.session() as s:
        event = s.query(OutboxEvent).filter(OutboxEvent.id == event_id).first()
        assert event is not None
        assert event.event_type == AUTOMATION_COMPLETED
        assert event.payload["rule_id"] == "rule-1"
        assert event.payload["result_ok"] is True
