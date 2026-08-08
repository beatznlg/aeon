"""AEON OS model registry.

Records provider, model, adapter version, and eval evidence for every model
deployment so that what is running, who approved it, and what evidence gates it
passed are auditable. Registry entries are non-secret operational metadata;
credentials stay in the Keys/API-key system. A registry entry is
engineering/operational evidence, not a certification.

The registry stores workspace-scoped records in ``AEON_ROOT/model_registry.json``
using an atomic replace, mirroring the operating-profiles state pattern. When a
deployment is approved, a best-effort, hash-chained record is appended to the
assurance ledger (``aeon_assurance.EvidenceLedger``) so approvals leave an
audit-trail entry.

Lifecycle: ``registered -> approved -> active -> rolled_back`` or
``registered -> approved -> deprecated``.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import uuid
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REGISTRY_VERSION = 1

DEPLOYMENT_STATUSES = frozenset(
    {"registered", "approved", "active", "rolled_back", "deprecated"}
)

# Allowed source statuses for each transition. Fail-closed: unknown transitions
# raise instead of silently corrupting state.
_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "approved": ("registered", "approved"),
    "active": ("approved", "active"),
    "rolled_back": ("registered", "approved", "active"),
    "deprecated": ("registered", "approved", "active"),
}

_lock = threading.RLock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _root(root: str | Path | None = None) -> Path:
    return Path(root or os.environ.get("AEON_ROOT", "./aeon_state/server"))


def _registry_path(root: str | Path | None = None) -> Path:
    override = os.environ.get("AEON_MODEL_REGISTRY_PATH")
    if override:
        return Path(override)
    return _root(root) / "model_registry.json"


def _ledger_path(root: str | Path | None = None) -> Path:
    override = os.environ.get("AEON_ASSURANCE_LEDGER_PATH")
    if override:
        return Path(override)
    return _root(root) / "assurance_ledger.jsonl"


def _digest(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(dict(payload), sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _fingerprint(record: Mapping[str, Any]) -> str:
    """Content hash that never includes the stored fingerprint field."""
    return _digest({key: value for key, value in record.items() if key != "fingerprint"})


@dataclass(frozen=True)
class ModelDeployment:
    """A single auditable model deployment record."""

    deployment_id: str
    provider: str
    model: str
    workspace_id: str = ""
    adapter_version: str | None = None
    base_model: str | None = None
    sector_pack_id: str | None = None
    status: str = "registered"
    eval_report: str | None = None
    eval_sha256: str | None = None
    accuracy: float | None = None
    eval_metrics: Mapping[str, Any] = field(default_factory=dict)
    approved_by: str | None = None
    approved_at: str | None = None
    rolled_back_by: str | None = None
    rollback_reason: str | None = None
    rollback_plan: str | None = None
    notes: str | None = None
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    registry_version: int = REGISTRY_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def fingerprint(self) -> str:
        """Stable SHA-256 over the full record for audit/evidence hashing."""
        return _digest(self.to_dict())


def _load(root: str | Path | None = None) -> list[dict[str, Any]]:
    path = _registry_path(root)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def _save(records: list[dict[str, Any]], root: str | Path | None = None) -> None:
    path = _registry_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(records, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _index_of(
    records: list[dict[str, Any]], deployment_id: str, workspace_id: str | None
) -> int:
    for index, record in enumerate(records):
        if record.get("deployment_id") != deployment_id:
            continue
        if workspace_id and record.get("workspace_id") != workspace_id:
            continue
        return index
    raise KeyError(deployment_id)


def _assert_transition(current: str, target: str) -> None:
    allowed = _TRANSITIONS.get(target, ())
    if current not in allowed:
        raise ValueError(
            f"cannot move deployment from {current!r} to {target!r}; "
            f"allowed sources: {', '.join(allowed) or 'none'}"
        )


def _append_assurance(record: dict[str, Any], root: str | Path | None = None) -> None:
    """Best-effort hash-chained assurance record for an approval (append-only)."""
    try:
        from aeon_assurance import EvidenceLedger

        EvidenceLedger(_ledger_path(root)).append(
            control_id=f"model_deployment_{record['deployment_id']}",
            profile=str(record.get("sector_pack_id") or "baseline").lower(),
            status="verified",
            summary=(
                f"model deployment {record['deployment_id']} "
                f"{record['provider']}/{record['model']} approved"
            ),
            source="aeon_model_registry",
            artifact_sha256=record["fingerprint"],
        )
    except Exception:  # noqa: BLE001 - never let ledger issues block the registry
        pass


def register_deployment(
    provider: str,
    model: str,
    *,
    workspace_id: str = "",
    adapter_version: str | None = None,
    base_model: str | None = None,
    sector_pack_id: str | None = None,
    eval_report: str | None = None,
    eval_sha256: str | None = None,
    accuracy: float | None = None,
    rollback_plan: str | None = None,
    notes: str | None = None,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Register a model deployment (status ``registered``)."""
    provider = str(provider or "").strip().lower()
    model = str(model or "").strip()
    if not provider:
        raise ValueError("provider is required")
    if not model:
        raise ValueError("model is required")
    if accuracy is not None and not 0.0 <= float(accuracy) <= 1.0:
        raise ValueError("accuracy must be between 0 and 1")
    if eval_sha256 is not None:
        digest = str(eval_sha256).strip().lower()
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError("eval_sha256 must be a SHA-256 hex digest")
        eval_sha256 = digest

    record = ModelDeployment(
        deployment_id=str(uuid.uuid4()),
        provider=provider,
        model=model,
        workspace_id=str(workspace_id or ""),
        adapter_version=str(adapter_version).strip() if adapter_version else None,
        base_model=str(base_model).strip() if base_model else None,
        sector_pack_id=str(sector_pack_id).strip() if sector_pack_id else None,
        eval_report=str(eval_report).strip() if eval_report else None,
        eval_sha256=eval_sha256,
        accuracy=float(accuracy) if accuracy is not None else None,
        rollback_plan=str(rollback_plan).strip() if rollback_plan else None,
        notes=str(notes).strip() if notes else None,
    )
    stored = record.to_dict()
    stored["fingerprint"] = _fingerprint(stored)
    with _lock:
        records = _load(root)
        records.append(stored)
        _save(records, root)
    return stored


def list_deployments(
    *,
    workspace_id: str | None = None,
    status: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    sector_pack_id: str | None = None,
    root: str | Path | None = None,
) -> list[dict[str, Any]]:
    """List deployments, optionally filtered. Newest first."""
    with _lock:
        records = _load(root)
    filtered = []
    for record in records:
        if workspace_id and record.get("workspace_id") != workspace_id:
            continue
        if status and record.get("status") != status:
            continue
        if provider and record.get("provider") != str(provider).strip().lower():
            continue
        if model and record.get("model") != str(model).strip():
            continue
        if sector_pack_id and record.get("sector_pack_id") != sector_pack_id:
            continue
        filtered.append(record)
    filtered.sort(key=lambda rec: rec.get("updated_at") or "", reverse=True)
    return filtered


def get_deployment(
    deployment_id: str,
    *,
    workspace_id: str | None = None,
    root: str | Path | None = None,
) -> dict[str, Any] | None:
    """Return one deployment, or None. Workspace-scoped when requested."""
    with _lock:
        records = _load(root)
        try:
            index = _index_of(records, deployment_id, workspace_id)
        except KeyError:
            return None
        return records[index]


def _transition_to(
    deployment_id: str,
    target: str,
    *,
    workspace_id: str | None,
    root: str | Path | None,
    **fields: Any,
) -> dict[str, Any]:
    with _lock:
        records = _load(root)
        index = _index_of(records, deployment_id, workspace_id)
        record = dict(records[index])
        _assert_transition(record.get("status") or "registered", target)
        record["status"] = target
        record.update(fields)
        record["updated_at"] = _now_iso()
        record["fingerprint"] = _fingerprint(record)
        records[index] = record
        _save(records, root)
        updated = record
    if target == "approved":
        _append_assurance(updated, root)
    return updated


def approve_deployment(
    deployment_id: str,
    approved_by: str,
    *,
    workspace_id: str | None = None,
    note: str | None = None,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Approve a registered deployment (status ``approved``)."""
    approved_by = str(approved_by or "").strip()
    if not approved_by:
        raise ValueError("approved_by is required")
    return _transition_to(
        deployment_id,
        "approved",
        workspace_id=workspace_id,
        root=root,
        approved_by=approved_by,
        approved_at=_now_iso(),
        notes=str(note).strip() if note else None,
    )


def activate_deployment(
    deployment_id: str,
    activated_by: str,
    *,
    workspace_id: str | None = None,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Activate an approved deployment (status ``active``)."""
    return _transition_to(
        deployment_id,
        "active",
        workspace_id=workspace_id,
        root=root,
        activated_by=str(activated_by or "").strip() or None,
    )


def rollback_deployment(
    deployment_id: str,
    rolled_back_by: str,
    reason: str,
    *,
    workspace_id: str | None = None,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Roll back a deployment (status ``rolled_back``)."""
    reason = str(reason or "").strip()
    if not reason:
        raise ValueError("reason is required")
    return _transition_to(
        deployment_id,
        "rolled_back",
        workspace_id=workspace_id,
        root=root,
        rolled_back_by=str(rolled_back_by or "").strip() or None,
        rollback_reason=reason,
    )


def deprecate_deployment(
    deployment_id: str,
    reason: str,
    *,
    workspace_id: str | None = None,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Deprecate a deployment (status ``deprecated``)."""
    reason = str(reason or "").strip()
    if not reason:
        raise ValueError("reason is required")
    return _transition_to(
        deployment_id,
        "deprecated",
        workspace_id=workspace_id,
        root=root,
        deprecation_reason=reason,
    )


def record_eval_evidence(
    deployment_id: str,
    *,
    eval_report: str | None = None,
    eval_sha256: str | None = None,
    accuracy: float | None = None,
    metrics: Mapping[str, Any] | None = None,
    workspace_id: str | None = None,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Attach eval evidence (e.g. a ``scripts/sector_eval.py`` report hash)."""
    if accuracy is not None and not 0.0 <= float(accuracy) <= 1.0:
        raise ValueError("accuracy must be between 0 and 1")
    if eval_sha256 is not None:
        digest = str(eval_sha256).strip().lower()
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError("eval_sha256 must be a SHA-256 hex digest")
        eval_sha256 = digest
    updates: dict[str, Any] = {}
    if eval_report:
        updates["eval_report"] = str(eval_report).strip()
    if eval_sha256:
        updates["eval_sha256"] = eval_sha256
    if accuracy is not None:
        updates["accuracy"] = float(accuracy)
    if metrics:
        updates["eval_metrics"] = dict(metrics)
    if not updates:
        raise ValueError("at least one eval field is required")
    with _lock:
        records = _load(root)
        index = _index_of(records, deployment_id, workspace_id)
        record = dict(records[index])
        record.update(updates)
        record["updated_at"] = _now_iso()
        record["fingerprint"] = _fingerprint(record)
        records[index] = record
        _save(records, root)
        return record


def get_active_deployments(
    *,
    workspace_id: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    sector_pack_id: str | None = None,
    root: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Resolve currently active deployments (status ``active``)."""
    return list_deployments(
        workspace_id=workspace_id,
        status="active",
        provider=provider,
        model=model,
        sector_pack_id=sector_pack_id,
        root=root,
    )


def attach_eval_evidence(
    deployment_id: str | None = None,
    *,
    provider: str | None = None,
    model: str | None = None,
    eval_report: str | None = None,
    eval_sha256: str | None = None,
    accuracy: float | None = None,
    metrics: Mapping[str, Any] | None = None,
    workspace_id: str | None = None,
    root: str | Path | None = None,
) -> dict[str, Any] | None:
    """Attach eval evidence to the deployment that produced it.

    With ``deployment_id``, attach to exactly that deployment. Otherwise match
    by provider + model (+ workspace) against deployments in the
    registered/approved/active states, preferring the most recently updated.
    Returns the updated record, or ``None`` when no deployment matches.
    """
    if deployment_id:
        current = get_deployment(deployment_id, workspace_id=workspace_id, root=root)
        if current is None:
            return None
    else:
        provider = str(provider or "").strip().lower()
        model = str(model or "").strip()
        if not provider or not model:
            raise ValueError("provider and model are required for automatic matching")
        candidates = [
            record
            for record in list_deployments(
                workspace_id=workspace_id,
                provider=provider,
                model=model,
                root=root,
            )
            if record.get("status") in ("registered", "approved", "active")
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda rec: rec.get("updated_at") or "", reverse=True)
        current = candidates[0]
    return record_eval_evidence(
        current["deployment_id"],
        eval_report=eval_report,
        eval_sha256=eval_sha256,
        accuracy=accuracy,
        metrics=metrics,
        workspace_id=workspace_id,
        root=root,
    )


__all__ = [
    "DEPLOYMENT_STATUSES",
    "ModelDeployment",
    "activate_deployment",
    "approve_deployment",
    "attach_eval_evidence",
    "deprecate_deployment",
    "get_active_deployments",
    "get_deployment",
    "list_deployments",
    "record_eval_evidence",
    "register_deployment",
    "rollback_deployment",
]
