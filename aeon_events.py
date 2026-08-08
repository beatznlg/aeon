"""Canonical AEON event contracts and transaction-aware persistence helpers.

The event layer is deliberately small and transport-neutral. Callers that
change a SQLAlchemy aggregate must pass their existing session to
:func:`append_outbox_event`; the helper never commits so the aggregate and its
outbox row remain in one transaction.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

EVENT_SCHEMAS: dict[str, dict[str, Any]] = {
    "workflow.run.queued": {
        "version": 1,
        "owner": "automation",
        "classification": "internal",
        "workspace_required": True,
    },
    "workflow.run.started": {
        "version": 1,
        "owner": "automation",
        "classification": "internal",
        "workspace_required": True,
    },
    "workflow.run.completed": {
        "version": 1,
        "owner": "automation",
        "classification": "internal",
        "workspace_required": True,
    },
    "workflow.run.failed": {
        "version": 1,
        "owner": "automation",
        "classification": "internal",
        "workspace_required": True,
    },
}

REDACTED = "[REDACTED]"
_SENSITIVE_KEYS = {
    "access_token",
    "api_key",
    "apikey",
    "authorization",
    "client_secret",
    "cookie",
    "credential",
    "password",
    "private_key",
    "refresh_token",
    "secret",
    "session_token",
    "token",
}


class EventValidationError(ValueError):
    """Raised when an event does not satisfy the registered envelope contract."""


def _non_empty(value: Any, field: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise EventValidationError(f"{field} is required")
    return result


def _is_sensitive_key(key: Any) -> bool:
    normalized = str(key).strip().lower().replace("-", "_")
    return normalized in _SENSITIVE_KEYS or normalized.endswith("_token") or normalized.endswith("_secret")


def redact_sensitive(value: Any) -> tuple[Any, bool]:
    """Return a JSON-compatible copy with credential-like fields redacted."""
    if isinstance(value, Mapping):
        changed = False
        result: dict[str, Any] = {}
        for key, child in value.items():
            key_text = str(key)
            if _is_sensitive_key(key_text):
                result[key_text] = REDACTED
                changed = True
                continue
            redacted_child, child_changed = redact_sensitive(child)
            result[key_text] = redacted_child
            changed = changed or child_changed
        return result, changed
    if isinstance(value, list):
        items = []
        changed = False
        for child in value:
            redacted_child, child_changed = redact_sensitive(child)
            items.append(redacted_child)
            changed = changed or child_changed
        return items, changed
    if isinstance(value, tuple):
        redacted, changed = redact_sensitive(list(value))
        return redacted, changed
    return value, False


def _json_validate(value: Any, field: str) -> None:
    try:
        json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise EventValidationError(f"{field} must be JSON serializable") from exc


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _isoformat_z(value: datetime) -> str:
    timestamp = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise EventValidationError("occurred_at must be an ISO-8601 timestamp") from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def build_event(
    *,
    event_type: str,
    event_version: int,
    tenant_id: str,
    workspace_id: str | None,
    aggregate_type: str,
    aggregate_id: str,
    aggregate_version: int,
    data: dict[str, Any],
    correlation_id: str,
    actor: dict[str, Any] | None = None,
    causation_id: str | None = None,
) -> dict[str, Any]:
    """Build and validate a canonical event envelope."""
    event_type = _non_empty(event_type, "event_type")
    schema = EVENT_SCHEMAS.get(event_type)
    if schema is None:
        raise EventValidationError(f"unknown event type: {event_type}")
    if event_version != schema["version"]:
        raise EventValidationError(f"unsupported version for {event_type}: {event_version}")
    if not isinstance(data, dict):
        raise EventValidationError("data must be an object")
    if schema.get("workspace_required") and not str(workspace_id or "").strip():
        raise EventValidationError("workspace_id is required for this event")
    if not isinstance(aggregate_version, int) or aggregate_version < 1:
        raise EventValidationError("aggregate_version must be a positive integer")

    redacted_data, redacted = redact_sensitive(data)
    _json_validate(redacted_data, "data")
    actor_value = None
    if actor is not None:
        if not isinstance(actor, dict):
            raise EventValidationError("actor must be an object")
        actor_value = {key: actor[key] for key in ("type", "id") if key in actor}
        if not actor_value:
            raise EventValidationError("actor must include type or id")
        _json_validate(actor_value, "actor")

    event = {
        "event_id": f"evt_{uuid.uuid4().hex}",
        "event_type": event_type,
        "event_version": event_version,
        "schema_uri": f"aeon://events/{event_type}/v{event_version}",
        "occurred_at": _isoformat_z(_utc_now()),
        "tenant_id": _non_empty(tenant_id, "tenant_id"),
        "workspace_id": str(workspace_id).strip() if workspace_id is not None else None,
        "correlation_id": _non_empty(correlation_id, "correlation_id"),
        "causation_id": str(causation_id).strip() if causation_id else None,
        "actor": actor_value,
        "aggregate": {
            "type": _non_empty(aggregate_type, "aggregate.type"),
            "id": _non_empty(aggregate_id, "aggregate.id"),
            "version": aggregate_version,
        },
        "data": redacted_data,
        "privacy": {
            "classification": schema["classification"],
            "redacted": redacted,
        },
    }
    validate_event(event)
    return event


def validate_event(event: Mapping[str, Any]) -> dict[str, Any]:
    """Validate an event received from storage or a transport and return it."""
    if not isinstance(event, Mapping):
        raise EventValidationError("event must be an object")
    event_type = _non_empty(event.get("event_type"), "event_type")
    schema = EVENT_SCHEMAS.get(event_type)
    if schema is None:
        raise EventValidationError(f"unknown event type: {event_type}")
    if event.get("event_version") != schema["version"]:
        raise EventValidationError(f"unsupported version for {event_type}: {event.get('event_version')}")
    for field in ("event_id", "schema_uri", "occurred_at", "tenant_id", "correlation_id"):
        _non_empty(event.get(field), field)
    if event["schema_uri"] != f"aeon://events/{event_type}/v{schema['version']}":
        raise EventValidationError("schema_uri does not match the registered event schema")
    if schema.get("workspace_required") and not str(event.get("workspace_id") or "").strip():
        raise EventValidationError("workspace_id is required for this event")
    aggregate = event.get("aggregate")
    if not isinstance(aggregate, Mapping):
        raise EventValidationError("aggregate must be an object")
    _non_empty(aggregate.get("type"), "aggregate.type")
    _non_empty(aggregate.get("id"), "aggregate.id")
    if not isinstance(aggregate.get("version"), int) or aggregate["version"] < 1:
        raise EventValidationError("aggregate.version must be a positive integer")
    if not isinstance(event.get("data"), Mapping):
        raise EventValidationError("data must be an object")
    if not isinstance(event.get("privacy"), Mapping):
        raise EventValidationError("privacy must be an object")
    if event["privacy"].get("classification") != schema["classification"]:
        raise EventValidationError("privacy classification does not match the registered event schema")
    _parse_timestamp(str(event["occurred_at"]))
    _json_validate(dict(event), "event")
    return dict(event)


def canonical_event_json(event: Mapping[str, Any]) -> str:
    """Return the stable JSON representation used for payload hashes."""
    validated = validate_event(event)
    return json.dumps(validated, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def event_payload_hash(event: Mapping[str, Any]) -> str:
    """Hash only canonical event content, never transport metadata."""
    return hashlib.sha256(canonical_event_json(event).encode("utf-8")).hexdigest()


def append_outbox_event(
    session: Session,
    event: Mapping[str, Any],
    *,
    available_at: datetime | None = None,
) -> Any:
    """Append an event without committing the caller's transaction.

    Producers may safely retry an append after a timeout: a previously stored
    event with the same ID and canonical payload is returned unchanged. Reusing
    an event ID for different content is rejected because it would make the
    event stream ambiguous. The savepoint around the insert also keeps a
    concurrent duplicate from poisoning the caller's outer transaction.
    """
    from aeon_db import OutboxEvent

    validated = validate_event(event)
    payload_hash = event_payload_hash(validated)
    event_id = validated["event_id"]
    caller_in_transaction = session.in_transaction()
    existing = session.get(OutboxEvent, event_id)
    if existing is not None:
        if existing.payload_hash != payload_hash:
            raise EventValidationError("event_id already exists with a different payload")
        return existing

    occurred_at = _parse_timestamp(validated["occurred_at"])
    aggregate = validated["aggregate"]
    row = OutboxEvent(
        id=event_id,
        tenant_id=validated["tenant_id"],
        workspace_id=validated.get("workspace_id"),
        aggregate_type=aggregate["type"],
        aggregate_id=aggregate["id"],
        aggregate_version=aggregate["version"],
        event_type=validated["event_type"],
        event_version=validated["event_version"],
        schema_uri=validated["schema_uri"],
        payload=validated,
        payload_hash=payload_hash,
        occurred_at=occurred_at,
        available_at=available_at or _utc_now(),
    )
    try:
        if caller_in_transaction:
            with session.begin_nested():
                session.add(row)
                session.flush()
        else:
            # Preserve the caller's normal transaction semantics. SQLAlchemy
            # will autobegin here, and the caller remains responsible for
            # commit/rollback.
            session.add(row)
            session.flush()
    except IntegrityError as exc:
        existing = session.get(OutboxEvent, event_id)
        if existing is None:
            raise
        if existing.payload_hash != payload_hash:
            raise EventValidationError("event_id already exists with a different payload") from exc
        return existing
    return row


def begin_event_consumption(
    session: Session,
    *,
    consumer_name: str,
    event_id: str,
) -> bool:
    """Claim an event for a consumer; return False for duplicate delivery."""
    from aeon_db import EventConsumption

    consumer_name = _non_empty(consumer_name, "consumer_name")
    event_id = _non_empty(event_id, "event_id")
    try:
        with session.begin_nested():
            session.add(
                EventConsumption(
                    consumer_name=consumer_name,
                    event_id=event_id,
                    status="processing",
                    first_seen_at=_utc_now(),
                    attempt_count=1,
                )
            )
            session.flush()
        return True
    except IntegrityError:
        return False


def mark_event_processed(session: Session, *, consumer_name: str, event_id: str) -> bool:
    """Mark a previously claimed event processed without committing."""
    from aeon_db import EventConsumption

    row = (
        session.query(EventConsumption)
        .filter_by(consumer_name=_non_empty(consumer_name, "consumer_name"), event_id=_non_empty(event_id, "event_id"))
        .one_or_none()
    )
    if row is None:
        return False
    row.status = "processed"
    row.processed_at = _utc_now()
    session.flush()
    return True


# Short aliases keep the contract easy to discover for callers and tests.
append_event = append_outbox_event
consume_event = begin_event_consumption
