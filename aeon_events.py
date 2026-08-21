"""AEON OS Domain Event Architecture.

Outbox-based event system for decoupled, reliable, idempotent domain events.

Design:
  1. Mutations publish events to ``outbox_events`` inside the same DB transaction
     (transactional outbox pattern — guarantees at-least-once delivery).
  2. A background relay thread polls for ``status='pending'`` events, dispatches
     them to registered consumers, and marks them ``published`` or ``error``.
  3. Consumers register via ``register_consumer`` and each event is delivered
     exactly once per consumer (enforced by ``event_consumptions`` idempotency
     table — at-least-once relay + exactly-once consumer semantics).

Domain events use a ``<domain>.<verb>`` naming convention:

  workspace.created, workspace.updated, workspace.deleted,
  membership.created, membership.role_changed, membership.removed,
  user.registered, user.login, user.logout,
  subscription.created, subscription.updated, subscription.cancelled,
  plugin.installed, plugin.removed,
  sector.updated, sector.data_changed,
  automation.triggered, automation.completed, automation.failed,
  ai.execution.recorded, ai.governance.blocked,
  security.rate_limited, security.login_failed,
  billing.checkout_completed, billing.payment_failed,
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

# ── Event type constants ──────────────────────────────────────────────────────

# Workspace
WORKSPACE_CREATED = "workspace.created"
WORKSPACE_UPDATED = "workspace.updated"
WORKSPACE_DELETED = "workspace.deleted"

# Membership
MEMBERSHIP_CREATED = "membership.created"
MEMBERSHIP_ROLE_CHANGED = "membership.role_changed"
MEMBERSHIP_REMOVED = "membership.removed"

# User
USER_REGISTERED = "user.registered"
USER_LOGIN = "user.login"
USER_LOGOUT = "user.logout"

# Subscription / Billing
SUBSCRIPTION_CREATED = "subscription.created"
SUBSCRIPTION_UPDATED = "subscription.updated"
SUBSCRIPTION_CANCELLED = "subscription.cancelled"
BILLING_CHECKOUT_COMPLETED = "billing.checkout_completed"
BILLING_PAYMENT_FAILED = "billing.payment_failed"

# Plugins
PLUGIN_INSTALLED = "plugin.installed"
PLUGIN_REMOVED = "plugin.removed"

# Sectors
SECTOR_UPDATED = "sector.updated"
SECTOR_DATA_CHANGED = "sector.data_changed"

# Automations
AUTOMATION_TRIGGERED = "automation.triggered"
AUTOMATION_COMPLETED = "automation.completed"
AUTOMATION_FAILED = "automation.failed"
AUTOMATION_APPROVAL_REQUESTED = "automation.approval_requested"

# AI / Governance
AI_EXECUTION_RECORDED = "ai.execution.recorded"
AI_GOVERNANCE_BLOCKED = "ai.governance.blocked"

# Security
SECURITY_RATE_LIMITED = "security.rate_limited"
SECURITY_LOGIN_FAILED = "security.login_failed"
SECURITY_JWT_ROTATED = "security.jwt_rotated"

ALL_EVENT_TYPES = [
    WORKSPACE_CREATED, WORKSPACE_UPDATED, WORKSPACE_DELETED,
    MEMBERSHIP_CREATED, MEMBERSHIP_ROLE_CHANGED, MEMBERSHIP_REMOVED,
    USER_REGISTERED, USER_LOGIN, USER_LOGOUT,
    SUBSCRIPTION_CREATED, SUBSCRIPTION_UPDATED, SUBSCRIPTION_CANCELLED,
    BILLING_CHECKOUT_COMPLETED, BILLING_PAYMENT_FAILED,
    PLUGIN_INSTALLED, PLUGIN_REMOVED,
    SECTOR_UPDATED, SECTOR_DATA_CHANGED,
    AUTOMATION_TRIGGERED, AUTOMATION_COMPLETED, AUTOMATION_FAILED, AUTOMATION_APPROVAL_REQUESTED,
    AI_EXECUTION_RECORDED, AI_GOVERNANCE_BLOCKED,
    SECURITY_RATE_LIMITED, SECURITY_LOGIN_FAILED, SECURITY_JWT_ROTATED,
]

# ── In-memory consumer registry ───────────────────────────────────────────────

_consumer_registry: dict[str, list[Callable[[str, dict[str, Any]], None]]] = {}


def register_consumer(
    event_type: str,
    handler: Callable[[str, dict[str, Any]], None],
    consumer_name: str | None = None,
) -> None:
    """Register a handler for a specific event type.

    Args:
        event_type: The event type string (e.g. ``workspace.created``).
        handler: Callable receiving ``(event_id, payload)``.
        consumer_name: Optional name for the consumer (used in logging).
    """
    name = consumer_name or handler.__qualname__
    _consumer_registry.setdefault(event_type, []).append(handler)
    logger.debug("Registered consumer %r for event type %r", name, event_type)


def get_consumer_registry() -> dict[str, list[Callable]]:
    """Return the current consumer registry (read-only snapshot)."""
    return {k: list(v) for k, v in _consumer_registry.items()}


# ── Outbox Publisher ──────────────────────────────────────────────────────────

def _payload_hash(payload: dict[str, Any]) -> str:
    """Deterministic hash for idempotency / dedup."""
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def publish_event(
    event_type: str,
    *,
    tenant_id: str,
    workspace_id: str | None = None,
    aggregate_type: str = "",
    aggregate_id: str = "",
    aggregate_version: int = 1,
    payload: dict[str, Any] | None = None,
    session: Any = None,
    available_at: datetime | None = None,
) -> str | None:
    """Write a domain event to the outbox within an existing DB session.

    This should be called inside the same transaction as the mutation it
    describes. Returns the event id, or ``None`` if publishing is skipped
    (e.g. no DB session available — the event will be logged to the
    governance audit instead).

    The event relay background thread picks it up asynchronously.
    """
    payload = payload or {}
    event_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # If no session is provided, try to get one from the DB layer
    if session is None:
        try:
            from aeon_db import get_db
            db = get_db()
            with db.session() as s:
                _insert_outbox_event(s, event_id, tenant_id, workspace_id,
                                     aggregate_type, aggregate_id, aggregate_version,
                                     event_type, payload, now, available_at)
                s.commit()
            logger.debug("Published event %s [%s] to outbox", event_id, event_type)
            return event_id
        except Exception as exc:
            logger.warning("Failed to publish event %s [%s] to outbox: %s", event_id, event_type, exc)
            _log_event_to_audit(event_type, payload, tenant_id, workspace_id)
            return None
    else:
        try:
            _insert_outbox_event(session, event_id, tenant_id, workspace_id,
                                 aggregate_type, aggregate_id, aggregate_version,
                                 event_type, payload, now, available_at)
            return event_id
        except Exception as exc:
            logger.warning("Failed to write outbox event %s: %s", event_id, exc)
            return None


def _insert_outbox_event(
    session: Any,
    event_id: str,
    tenant_id: str,
    workspace_id: str | None,
    aggregate_type: str,
    aggregate_id: str,
    aggregate_version: int,
    event_type: str,
    payload: dict[str, Any],
    now: datetime,
    available_at: datetime | None,
) -> None:
    """Insert a row into the outbox_events table."""
    from aeon_db import OutboxEvent

    event = OutboxEvent(
        id=event_id,
        tenant_id=tenant_id or "",
        workspace_id=workspace_id,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        aggregate_version=aggregate_version,
        event_type=event_type,
        event_version=1,
        schema_uri=f"aeon://events/{event_type}/v1",
        payload=payload,
        payload_hash=_payload_hash(payload),
        occurred_at=now,
        created_at=now,
        available_at=available_at or now,
        status="pending",
        attempt_count=0,
    )
    session.add(event)


def _log_event_to_audit(
    event_type: str,
    payload: dict[str, Any],
    tenant_id: str,
    workspace_id: str | None,
) -> None:
    """Fallback: log the event to the governance audit when outbox write fails."""
    try:
        from aeon_governance import get_governance
        get_governance().log_audit(
            action="DOMAIN_EVENT_FAILED",
            module="events",
            user_id=payload.get("user_id"),
            workspace_id=workspace_id,
            metadata={"event_type": event_type, "tenant_id": tenant_id},
        )
    except Exception:  # pragma: no cover
        pass


# ── Background Event Relay ────────────────────────────────────────────────────

class EventRelay:
    """Background thread that polls the outbox and dispatches events to consumers.

    Uses a lease-based approach to prevent duplicate processing in multi-worker
    deployments. Events are leased to a unique relay owner, processed, then
    marked published. Failed events are retried with exponential backoff up to
    ``max_attempts`` times before being marked error.
    """

    def __init__(
        self,
        poll_interval: float = 2.0,
        batch_size: int = 50,
        max_attempts: int = 5,
        relay_id: str | None = None,
    ):
        self._poll_interval = poll_interval
        self._batch_size = batch_size
        self._max_attempts = max_attempts
        self._relay_id = relay_id or f"relay-{uuid.uuid4().hex[:8]}"
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._stats = {"dispatched": 0, "errors": 0, "skipped": 0}

    @property
    def relay_id(self) -> str:
        return self._relay_id

    @property
    def stats(self) -> dict[str, int]:
        return dict(self._stats)

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop,
            daemon=True,
            name="aeon-event-relay",
        )
        self._thread.start()
        logger.info("Event relay %s started (poll every %.1fs)", self._relay_id, self._poll_interval)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                processed = self._tick()
            except Exception as exc:
                logger.warning("Event relay tick failed: %s", exc)
                processed = 0
            # Sleep shorter if we processed events (more work to do)
            sleep_time = 0.5 if processed > 0 else self._poll_interval
            self._stop_event.wait(sleep_time)

    def _tick(self) -> int:
        """Process one batch of pending events. Returns count processed."""
        from aeon_db import get_db, OutboxEvent, EventConsumption
        from sqlalchemy import and_

        db = get_db()
        now = datetime.now(timezone.utc)
        processed = 0

        with db.session() as s:
            # Fetch pending events that are available (not leased or lease expired)
            events = (
                s.query(OutboxEvent)
                .filter(
                    and_(
                        OutboxEvent.status == "pending",
                        OutboxEvent.available_at <= now,
                        OutboxEvent.attempt_count < self._max_attempts,
                    )
                )
                .order_by(OutboxEvent.created_at.asc())
                .limit(self._batch_size)
                .all()
            )

            for event in events:
                # Try to lease the event
                if event.lease_owner and event.lease_until and event.lease_until > now:
                    continue  # Another relay owns this

                event.lease_owner = self._relay_id
                event.lease_until = now + timedelta(seconds=60)
                event.attempt_count += 1

                try:
                    self._dispatch_event(s, event, EventConsumption)
                    event.status = "published"
                    event.published_at = now
                    event.lease_owner = None
                    event.lease_until = None
                    processed += 1
                except Exception as exc:
                    event.last_error_code = "DISPATCH_FAILED"
                    event.last_error_message = str(exc)[:500]
                    if event.attempt_count >= self._max_attempts:
                        event.status = "error"
                        logger.error(
                            "Event %s [%s] failed after %d attempts: %s",
                            event.id, event.event_type, event.attempt_count, exc,
                        )
                        self._stats["errors"] += 1
                    else:
                        # Exponential backoff: 2s, 4s, 8s, 16s, 32s
                        backoff = min(2 ** event.attempt_count, 120)
                        event.available_at = now + timedelta(seconds=backoff)
                        event.lease_owner = None
                        event.lease_until = None
                    self._stats["errors"] += 1
                finally:
                    s.commit()

        return processed

    def _dispatch_event(self, session: Any, event: Any, EventConsumption: Any) -> None:
        """Dispatch a single event to all registered consumers with idempotency."""
        event_type = event.event_type
        payload = event.payload or {}
        handlers = _consumer_registry.get(event_type, [])

        if not handlers:
            self._stats["skipped"] += 1
            return

        for handler in handlers:
            consumer_name = handler.__qualname__

            # Idempotency check: has this consumer already processed this event?
            existing = (
                session.query(EventConsumption)
                .filter(
                    EventConsumption.consumer_name == consumer_name,
                    EventConsumption.event_id == event.id,
                )
                .first()
            )
            if existing and existing.status == "completed":
                continue  # Already processed

            try:
                handler(event.id, payload)
                # Record successful consumption
                if existing:
                    existing.status = "completed"
                    existing.processed_at = datetime.now(timezone.utc)
                    existing.attempt_count += 1
                else:
                    session.add(EventConsumption(
                        consumer_name=consumer_name,
                        event_id=event.id,
                        status="completed",
                        processed_at=datetime.now(timezone.utc),
                        attempt_count=1,
                    ))
                self._stats["dispatched"] += 1
            except Exception as exc:
                error_msg = str(exc)[:500]
                if existing:
                    existing.status = "error"
                    existing.attempt_count += 1
                    existing.last_error_code = "HANDLER_FAILED"
                    existing.last_error_message = error_msg
                else:
                    session.add(EventConsumption(
                        consumer_name=consumer_name,
                        event_id=event.id,
                        status="error",
                        attempt_count=1,
                        last_error_code="HANDLER_FAILED",
                        last_error_message=error_msg,
                    ))
                logger.warning("Consumer %r failed for event %s: %s", consumer_name, event.id, exc)
                raise  # Re-cause the event-level retry


# ── Built-in consumers ────────────────────────────────────────────────────────

def _audit_event_consumer(event_id: str, payload: dict[str, Any]) -> None:
    """Mirror every domain event to the governance audit log."""
    try:
        from aeon_governance import get_governance
        event_type = payload.pop("_event_type", "unknown")
        get_governance().log_audit(
            action=f"EVENT_{event_type.upper().replace('.', '_')}",
            module="events",
            user_id=payload.get("user_id"),
            workspace_id=payload.get("workspace_id"),
            metadata={"event_id": event_id, "event_type": event_type, **payload},
        )
    except Exception:  # pragma: no cover
        pass


def _security_alert_consumer(event_id: str, payload: dict[str, Any]) -> None:
    """Log security events to the governance security module."""
    try:
        from aeon_governance import get_governance
        get_governance().log_audit(
            action=payload.get("action", "SECURITY_EVENT"),
            module="security",
            user_id=payload.get("user_id"),
            workspace_id=payload.get("workspace_id"),
            metadata={"event_id": event_id, **payload},
        )
    except Exception:  # pragma: no cover
        pass


# Register built-in consumers
for _sec_type in (SECURITY_RATE_LIMITED, SECURITY_LOGIN_FAILED, SECURITY_JWT_ROTATED):
    register_consumer(_sec_type, _security_alert_consumer, f"security-audit-{_sec_type}")


# ── Module-level singleton ────────────────────────────────────────────────────

_relay: EventRelay | None = None
_relay_lock = threading.Lock()


def get_relay() -> EventRelay:
    """Return the global event relay, lazily initialised."""
    global _relay
    if _relay is not None:
        return _relay
    with _relay_lock:
        if _relay is not None:
            return _relay
        _relay = EventRelay()
        return _relay


def start_event_relay(**kwargs: Any) -> EventRelay:
    """Start the global event relay thread."""
    relay = get_relay()
    for k, v in kwargs.items():
        setattr(relay, f"_{k}", v)
    relay.start()
    return relay


def stop_event_relay() -> None:
    """Stop the global event relay thread."""
    relay = get_relay()
    relay.stop()


# ── Convenience: publish + audit in one call ──────────────────────────────────

def emit(
    event_type: str,
    *,
    tenant_id: str = "",
    workspace_id: str | None = None,
    aggregate_type: str = "",
    aggregate_id: str = "",
    payload: dict[str, Any] | None = None,
    user_id: str | None = None,
) -> str | None:
    """High-level emit: publish to outbox and enrich payload with metadata.

    Returns the event id or None.
    """
    payload = dict(payload or {})
    payload["_event_type"] = event_type
    if user_id:
        payload.setdefault("user_id", user_id)
    if workspace_id:
        payload.setdefault("workspace_id", workspace_id)
    payload.setdefault("timestamp", datetime.now(timezone.utc).isoformat())

    return publish_event(
        event_type,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        aggregate_type=aggregate_type or event_type.split(".")[0],
        aggregate_id=aggregate_id,
        payload=payload,
    )


# ── Query helpers (for /events API) ───────────────────────────────────────────

def query_outbox(
    *,
    status: str | None = None,
    event_type: str | None = None,
    workspace_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Query recent outbox events."""
    from aeon_db import get_db, OutboxEvent

    db = get_db()
    with db.session() as s:
        q = s.query(OutboxEvent)
        if status:
            q = q.filter(OutboxEvent.status == status)
        if event_type:
            q = q.filter(OutboxEvent.event_type == event_type)
        if workspace_id:
            q = q.filter(OutboxEvent.workspace_id == workspace_id)
        events = q.order_by(OutboxEvent.created_at.desc()).limit(limit).all()
        return [
            {
                "id": e.id,
                "event_type": e.event_type,
                "status": e.status,
                "tenant_id": e.tenant_id,
                "workspace_id": e.workspace_id,
                "aggregate_type": e.aggregate_type,
                "aggregate_id": e.aggregate_id,
                "attempt_count": e.attempt_count,
                "created_at": e.created_at.isoformat() if e.created_at else None,
                "published_at": e.published_at.isoformat() if e.published_at else None,
                "last_error_code": e.last_error_code,
                "last_error_message": e.last_error_message,
            }
            for e in events
        ]


def outbox_stats() -> dict[str, Any]:
    """Return aggregate outbox statistics."""
    from aeon_db import get_db, OutboxEvent

    db = get_db()
    with db.session() as s:
        total = s.query(OutboxEvent).count()
        pending = s.query(OutboxEvent).filter(OutboxEvent.status == "pending").count()
        published = s.query(OutboxEvent).filter(OutboxEvent.status == "published").count()
        errors = s.query(OutboxEvent).filter(OutboxEvent.status == "error").count()
        return {
            "total": total,
            "pending": pending,
            "published": published,
            "errors": errors,
            "relay_stats": get_relay().stats,
            "consumer_types": list(_consumer_registry.keys()),
        }



__all__ = [
    # Event type constants
    *ALL_EVENT_TYPES,
    # Publisher
    "publish_event",
    "emit",
    # Consumer
    "register_consumer",
    "get_consumer_registry",
    # Relay
    "EventRelay",
    "get_relay",
    "start_event_relay",
    "stop_event_relay",
    # Query
    "query_outbox",
    "outbox_stats",
]
