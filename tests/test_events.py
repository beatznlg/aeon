"""Focused tests for the first AEON event foundation slice."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from aeon_db import AuditLog, Base, EventConsumption, OutboxEvent
from aeon_event_runtime import audit_publisher, consume_audit_event
from aeon_events import (
    EventValidationError,
    append_outbox_event,
    begin_event_consumption,
    build_event,
    event_payload_hash,
    mark_event_processed,
)


def _event(**overrides):
    values = {
        "event_type": "workflow.run.queued",
        "event_version": 1,
        "tenant_id": "tenant-1",
        "workspace_id": "workspace-1",
        "aggregate_type": "workflow_run",
        "aggregate_id": "run-1",
        "aggregate_version": 1,
        "data": {"workflow_id": "workflow-1", "input": {"message": "hello"}},
        "correlation_id": "corr-1",
    }
    values.update(overrides)
    return build_event(**values)


def _session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'events.db'}")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_build_event_has_canonical_envelope_and_redacts_credentials():
    event = _event(data={"token": "do-not-store", "nested": {"api_key": "secret", "safe": True}})

    assert event["event_id"].startswith("evt_")
    assert event["schema_uri"] == "aeon://events/workflow.run.queued/v1"
    assert event["data"] == {"token": "[REDACTED]", "nested": {"api_key": "[REDACTED]", "safe": True}}
    assert event["privacy"]["redacted"] is True


def test_unknown_and_malformed_events_are_rejected():
    with pytest.raises(EventValidationError, match="unknown event type"):
        _event(event_type="workflow.run.unknown")
    with pytest.raises(EventValidationError, match="workspace_id is required"):
        _event(workspace_id=None)
    with pytest.raises(EventValidationError, match="correlation_id is required"):
        _event(correlation_id="")


def test_event_hash_is_deterministic_for_same_content():
    event = _event()
    first = event_payload_hash(event)
    second = event_payload_hash({key: event[key] for key in reversed(list(event))})
    assert first == second


def test_outbox_append_is_transaction_aware(tmp_path):
    session = _session(tmp_path)
    event = _event()
    row = append_outbox_event(session, event)

    assert row.id == event["event_id"]
    assert session.query(OutboxEvent).count() == 1
    session.rollback()
    assert session.query(OutboxEvent).count() == 0

    append_outbox_event(session, event)
    session.commit()
    assert session.query(OutboxEvent).one().payload_hash == event_payload_hash(event)


def test_outbox_append_is_idempotent_for_same_event_id(tmp_path):
    session = _session(tmp_path)
    event = _event()

    first = append_outbox_event(session, event)
    session.commit()
    second = append_outbox_event(session, event)

    assert second.id == first.id
    assert second.payload_hash == first.payload_hash
    assert session.query(OutboxEvent).count() == 1


def test_outbox_append_rejects_event_id_payload_collision(tmp_path):
    session = _session(tmp_path)
    event = _event()
    append_outbox_event(session, event)
    session.commit()

    conflicting = dict(event)
    conflicting["data"] = {"workflow_id": "workflow-2", "input": {"message": "different"}}
    with pytest.raises(EventValidationError, match="different payload"):
        append_outbox_event(session, conflicting)


def test_consumer_deduplication_is_persisted(tmp_path):
    session = _session(tmp_path)
    event = _event()
    append_outbox_event(session, event)
    session.commit()

    assert begin_event_consumption(session, consumer_name="audit", event_id=event["event_id"]) is True
    session.commit()
    assert begin_event_consumption(session, consumer_name="audit", event_id=event["event_id"]) is False
    assert begin_event_consumption(session, consumer_name="usage", event_id=event["event_id"]) is True
    assert mark_event_processed(session, consumer_name="audit", event_id=event["event_id"]) is True
    session.commit()

    row = session.query(EventConsumption).filter_by(consumer_name="audit").one()
    assert row.status == "processed"
    assert row.processed_at is not None


def test_audit_consumer_projects_sanitized_metadata_and_is_idempotent(tmp_path):
    session = _session(tmp_path)
    event = _event(
        actor={"type": "user", "id": "user-1", "email": "private@example.test"},
        data={"token": "never-store", "result": "ok"},
    )
    append_outbox_event(session, event)
    session.commit()

    assert consume_audit_event(session, event) is True
    session.commit()
    assert consume_audit_event(session, event) is False
    audit = session.query(AuditLog).one()
    assert audit.action == "workflow_queued"
    assert audit.module == "automations"
    assert audit.pii_redacted is True
    assert audit.metadata_json["event_id"] == event["event_id"]
    assert "token" not in audit.metadata_json
    assert audit.metadata_json["actor_id"] == "user-1"


def test_publisher_publishes_and_marks_outbox(tmp_path):
    session = _session(tmp_path)
    event = _event()
    append_outbox_event(session, event)
    session.commit()
    session.close()

    engine = create_engine(f"sqlite:///{tmp_path / 'events.db'}")
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    result = audit_publisher(factory, base_backoff_seconds=0).publish_batch()

    assert result["claimed"] == 1
    assert result["published"] == 1
    check = factory()
    assert check.query(OutboxEvent).one().published_at is not None
    assert check.query(AuditLog).count() == 1
    check.close()


def test_publisher_retries_then_dead_letters(tmp_path):
    session = _session(tmp_path)
    event = _event()
    append_outbox_event(session, event)
    session.commit()
    session.close()

    engine = create_engine(f"sqlite:///{tmp_path / 'events.db'}")
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    publisher = audit_publisher(factory, max_attempts=2, base_backoff_seconds=0)

    def failing_consumer(_session, _event):
        raise RuntimeError("consumer unavailable")

    publisher.register(failing_consumer)
    first = publisher.publish_batch()
    second = publisher.publish_batch()
    assert first["retrying"] == 1
    assert second["dead_lettered"] == 1

    check = factory()
    row = check.query(OutboxEvent).one()
    assert row.published_at is None
    assert row.attempt_count == 2
    assert row.last_error_code == "RuntimeError"
    assert row.status == "dead_lettered"
    assert row.lease_owner is None
    assert row.lease_until is None
    check.close()


def test_publisher_skips_active_lease(tmp_path):
    session = _session(tmp_path)
    event = _event()
    row = append_outbox_event(session, event)
    row.status = "processing"
    row.lease_owner = "other-worker"
    row.lease_until = row.available_at.replace(year=row.available_at.year + 1)
    session.commit()
    session.close()

    engine = create_engine(f"sqlite:///{tmp_path / 'events.db'}")
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    result = audit_publisher(factory, base_backoff_seconds=0, worker_id="this-worker").publish_batch()

    assert result["claimed"] == 0
    assert result["published"] == 0
    check = factory()
    persisted = check.get(OutboxEvent, row.id)
    assert persisted is not None
    assert persisted.lease_owner == "other-worker"
    assert persisted.status == "processing"
    check.close()


def test_publisher_reclaims_expired_lease(tmp_path):
    session = _session(tmp_path)
    event = _event()
    row = append_outbox_event(session, event)
    row.status = "processing"
    row.lease_owner = "stale-worker"
    row.lease_until = row.available_at.replace(year=row.available_at.year - 1)
    session.commit()
    session.close()

    engine = create_engine(f"sqlite:///{tmp_path / 'events.db'}")
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    result = audit_publisher(factory, base_backoff_seconds=0, worker_id="this-worker").publish_batch()

    assert result["claimed"] == 1
    assert result["published"] == 1
    check = factory()
    persisted = check.get(OutboxEvent, row.id)
    assert persisted is not None
    assert persisted.status == "published"
    assert persisted.lease_owner is None
    check.close()
