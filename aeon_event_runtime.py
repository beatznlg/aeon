"""In-process publication and audit projection for AEON events.

This module intentionally keeps delivery transport-neutral. It provides a
small, synchronous publisher suitable for local workers and tests while the
outbox schema remains ready for a future queue-backed implementation.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from aeon_db import OutboxEvent, add_audit_log_in_session
from aeon_events import begin_event_consumption, event_payload_hash, mark_event_processed, validate_event

AUDIT_CONSUMER = "audit"
AUDIT_EVENT_MAP: dict[str, tuple[str, str]] = {
    "workflow.run.queued": ("workflow_queued", "automations"),
    "workflow.run.started": ("workflow_started", "automations"),
    "workflow.run.completed": ("workflow_completed", "automations"),
    "workflow.run.failed": ("workflow_failed", "automations"),
}


class EventDispatchError(RuntimeError):
    """Raised when a consumer cannot safely process an event."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def sanitized_audit_metadata(event: Mapping[str, Any]) -> dict[str, Any]:
    """Extract non-sensitive envelope metadata for the audit projection."""
    validated = validate_event(event)
    aggregate = validated["aggregate"]
    privacy = validated["privacy"]
    metadata: dict[str, Any] = {
        "event_id": validated["event_id"],
        "event_type": validated["event_type"],
        "event_version": validated["event_version"],
        "aggregate_type": aggregate["type"],
        "aggregate_id": aggregate["id"],
        "aggregate_version": aggregate["version"],
        "correlation_id": validated["correlation_id"],
        "redacted": bool(privacy.get("redacted")),
        "classification": privacy["classification"],
    }
    if validated.get("causation_id"):
        metadata["causation_id"] = validated["causation_id"]
    if validated.get("actor"):
        actor = validated["actor"]
        metadata["actor_type"] = actor.get("type")
        metadata["actor_id"] = actor.get("id")
    return metadata


def consume_audit_event(session: Session, event: Mapping[str, Any]) -> bool:
    """Project one event into the local audit chain exactly once per consumer.

    The inbox claim, audit row, and processed marker share the caller's
    transaction. The caller owns commit/rollback, so a failed projection does
    not leave a processed marker behind.
    """
    validated = validate_event(event)
    event_id = validated["event_id"]
    if not begin_event_consumption(session, consumer_name=AUDIT_CONSUMER, event_id=event_id):
        return False

    action, module = AUDIT_EVENT_MAP.get(
        validated["event_type"],
        ("event_recorded", "events"),
    )
    metadata = sanitized_audit_metadata(validated)
    add_audit_log_in_session(
        session,
        action=action,
        module=module,
        user_id=(validated.get("actor") or {}).get("id"),
        workspace_id=validated.get("workspace_id"),
        email=None,
        metadata=metadata,
        pii_redacted=True,
    )
    if not mark_event_processed(session, consumer_name=AUDIT_CONSUMER, event_id=event_id):
        raise EventDispatchError("audit inbox record disappeared during processing")
    return True


Consumer = Callable[[Session, Mapping[str, Any]], None]


class InProcessOutboxPublisher:
    """Publish ready outbox rows to registered consumers with bounded retries."""

    def __init__(
        self,
        session_factory: Callable[[], Session],
        *,
        max_attempts: int = 3,
        base_backoff_seconds: int = 30,
        lease_seconds: int = 300,
        worker_id: str | None = None,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        if base_backoff_seconds < 0:
            raise ValueError("base_backoff_seconds cannot be negative")
        if lease_seconds < 1:
            raise ValueError("lease_seconds must be positive")
        self.session_factory = session_factory
        self.max_attempts = max_attempts
        self.base_backoff_seconds = base_backoff_seconds
        self.lease_seconds = lease_seconds
        self.worker_id = worker_id or f"worker_{uuid.uuid4().hex}"
        self._consumers: list[Consumer] = []

    def register(self, consumer: Consumer) -> None:
        self._consumers.append(consumer)

    def publish_batch(self, limit: int = 100, now: datetime | None = None) -> dict[str, int]:
        """Attempt the oldest ready events and return lifecycle counters."""
        if limit < 1:
            raise ValueError("limit must be positive")
        current = _as_aware(now or _utc_now())
        session = self.session_factory()
        counts = {"claimed": 0, "published": 0, "retrying": 0, "dead_lettered": 0, "failed": 0}
        try:
            rows = (
                session.query(OutboxEvent)
                .filter(
                    OutboxEvent.published_at.is_(None),
                    OutboxEvent.available_at <= current,
                    OutboxEvent.status != "dead_lettered",
                    or_(OutboxEvent.lease_until.is_(None), OutboxEvent.lease_until <= current),
                )
                .order_by(OutboxEvent.created_at.asc(), OutboxEvent.id.asc())
                .limit(limit)
                .all()
            )
            for candidate in rows:
                row = self._claim(candidate, session, current)
                if row is None:
                    continue
                counts["claimed"] += 1
                try:
                    self._publish_one(session, row)
                except Exception as exc:
                    counts["failed"] += 1
                    # Consumer side effects and the inbox claim belong to the
                    # same attempt transaction. Roll them back before
                    # recording retry metadata, otherwise a later retry would
                    # be deduplicated even though publication failed.
                    session.rollback()
                    row = session.get(OutboxEvent, row.id)
                    if row is None:
                        counts["dead_lettered"] += 1
                        continue
                    row.attempt_count = (row.attempt_count or 0) + 1
                    row.last_error_code = type(exc).__name__[:100]
                    row.last_error_message = str(exc)[:2000]
                    if row.attempt_count >= self.max_attempts:
                        counts["dead_lettered"] += 1
                        row.status = "dead_lettered"
                        row.lease_owner = None
                        row.lease_until = None
                        row.available_at = current
                    else:
                        row.status = "pending"
                        row.lease_owner = None
                        row.lease_until = None
                        counts["retrying"] += 1
                        delay = self.base_backoff_seconds * (2 ** (row.attempt_count - 1))
                        row.available_at = current + timedelta(seconds=delay)
                    session.commit()
                else:
                    row.published_at = current
                    row.status = "published"
                    row.lease_owner = None
                    row.lease_until = None
                    row.last_error_code = None
                    row.last_error_message = None
                    session.commit()
                    counts["published"] += 1
        finally:
            session.close()
        return counts

    def _claim(self, candidate: OutboxEvent, session: Session, current: datetime) -> OutboxEvent | None:
        """Atomically lease one ready row so another worker skips it."""
        updated = (
            session.query(OutboxEvent)
            .filter(
                OutboxEvent.id == candidate.id,
                OutboxEvent.published_at.is_(None),
                OutboxEvent.status != "dead_lettered",
                or_(OutboxEvent.lease_until.is_(None), OutboxEvent.lease_until <= current),
            )
            .update(
                {
                    OutboxEvent.status: "processing",
                    OutboxEvent.lease_owner: self.worker_id,
                    OutboxEvent.lease_until: current + timedelta(seconds=self.lease_seconds),
                },
                synchronize_session=False,
            )
        )
        if not updated:
            session.rollback()
            return None
        session.commit()
        return session.get(OutboxEvent, candidate.id)

    def _publish_one(self, session: Session, row: OutboxEvent) -> None:
        event = validate_event(row.payload)
        if row.payload_hash is None:
            raise EventDispatchError("outbox payload hash is missing")
        if row.payload_hash != event_payload_hash(event):
            raise EventDispatchError("outbox payload hash mismatch")
        for consumer in self._consumers:
            consumer(session, event)


def audit_publisher(session_factory: Callable[[], Session], **kwargs: Any) -> InProcessOutboxPublisher:
    """Create a publisher with the built-in sanitized audit consumer."""
    publisher = InProcessOutboxPublisher(session_factory, **kwargs)
    publisher.register(consume_audit_event)
    return publisher


__all__ = [
    "AUDIT_CONSUMER",
    "AUDIT_EVENT_MAP",
    "EventDispatchError",
    "InProcessOutboxPublisher",
    "audit_publisher",
    "consume_audit_event",
    "sanitized_audit_metadata",
]
