"""AEON OS assurance evidence ledger.

This module records evidence *about* controls; it does not perform an external
assessment and cannot create a certification, contract, or authorization. The
ledger stores metadata and digests rather than sensitive evidence contents. It
is deliberately append-only from the API perspective and hash-chained so
independent tooling can detect edits, deletions, and reordering in the file.

Use ``scripts/assurance_evidence.py`` to append a result or verify a ledger.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LEDGER_VERSION = 1
_VALID_STATUSES = {"verified", "failed", "pending", "not_applicable"}

# These identifiers describe evidence obligations, not legal conclusions.
_REQUIRED_EVIDENCE: dict[str, tuple[str, ...]] = {
    "baseline": (
        "security_assessment",
        "kms_validation",
        "audit_integrity",
        "backup_restore",
        "rto_rpo_measurement",
        "incident_response_exercise",
    ),
    "healthcare": (
        "hipaa_risk_analysis",
        "baa_review",
        "ephi_data_flow_validation",
    ),
    "financial": (
        "pci_scope_qsa_or_saq",
        "dora_resilience_review",
        "financial_model_risk_review",
    ),
    "critical_infrastructure": (
        "safety_case_review",
        "authority_approval",
        "segmentation_failover_test",
    ),
    "government": (
        "fedramp_boundary_ssp_3pao",
        "ato_or_agency_authorization",
        "cjis_agreement_review",
    ),
}


@dataclass(frozen=True)
class EvidenceRecord:
    """A non-sensitive, hash-chained record of an assurance observation."""

    evidence_id: str
    control_id: str
    profile: str
    status: str
    summary: str
    source: str
    observed_at: str
    artifact_sha256: str | None
    previous_hash: str
    record_hash: str
    ledger_version: int = LEDGER_VERSION

    def unsigned_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("record_hash")
        return data

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EvidenceLedger:
    """Append and verify evidence records stored as newline-delimited JSON."""

    def __init__(self, path: str | os.PathLike[str]):
        self.path = Path(path)

    @staticmethod
    def _canonical(payload: dict[str, Any]) -> bytes:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    @classmethod
    def _digest(cls, payload: dict[str, Any]) -> str:
        return hashlib.sha256(cls._canonical(payload)).hexdigest()

    def _records(self) -> list[EvidenceRecord]:
        if not self.path.exists():
            return []
        records: list[EvidenceRecord] = []
        with self.path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    records.append(EvidenceRecord(**data))
                except (TypeError, ValueError, json.JSONDecodeError) as exc:
                    raise ValueError(f"invalid evidence ledger record at line {line_number}") from exc
        return records

    def append(
        self,
        *,
        control_id: str,
        profile: str,
        status: str,
        summary: str,
        source: str,
        artifact_sha256: str | None = None,
        observed_at: str | None = None,
    ) -> EvidenceRecord:
        """Append one record and return it.

        ``artifact_sha256`` is optional so the ledger can represent a run whose
        artifact is held in an approved evidence system. Raw secrets or PHI are
        never accepted as part of the record contract.
        """
        control_id = control_id.strip()
        profile = profile.strip().lower()
        status = status.strip().lower()
        summary = summary.strip()
        source = source.strip()
        if not control_id or not profile or not summary or not source:
            raise ValueError("control_id, profile, summary, and source are required")
        if status not in _VALID_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(sorted(_VALID_STATUSES))}")
        if artifact_sha256 is not None:
            artifact_sha256 = artifact_sha256.strip().lower()
            if len(artifact_sha256) != 64 or any(char not in "0123456789abcdef" for char in artifact_sha256):
                raise ValueError("artifact_sha256 must be a SHA-256 hex digest")

        existing = self.verify()
        if not existing["ok"]:
            raise ValueError("cannot append to an invalid evidence ledger")
        records = self._records()
        previous_hash = records[-1].record_hash if records else "0" * 64
        observed = observed_at or datetime.now(timezone.utc).isoformat()
        unsigned = {
            "evidence_id": str(uuid.uuid4()),
            "control_id": control_id,
            "profile": profile,
            "status": status,
            "summary": summary,
            "source": source,
            "observed_at": observed,
            "artifact_sha256": artifact_sha256,
            "previous_hash": previous_hash,
            "ledger_version": LEDGER_VERSION,
        }
        record = EvidenceRecord(**unsigned, record_hash=self._digest(unsigned))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record.to_dict(), sort_keys=True, ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        return record

    def verify(self, expected_last_hash: str | None = None) -> dict[str, Any]:
        """Verify parsing, hash links, record hashes, IDs, and an optional anchor.

        The optional anchor should be stored outside the ledger in an approved,
        access-controlled or immutable evidence system. A local sidecar is only
        a convenience and does not provide independent tamper protection.
        """
        try:
            records = self._records()
        except ValueError as exc:
            return {"ok": False, "records": 0, "error": str(exc)}

        expected_previous = "0" * 64
        ids: set[str] = set()
        errors: list[str] = []
        for index, record in enumerate(records, 1):
            if record.evidence_id in ids:
                errors.append(f"duplicate evidence_id at record {index}")
            ids.add(record.evidence_id)
            if record.previous_hash != expected_previous:
                errors.append(f"broken previous_hash at record {index}")
            if self._digest(record.unsigned_dict()) != record.record_hash:
                errors.append(f"record_hash mismatch at record {index}")
            if record.status not in _VALID_STATUSES:
                errors.append(f"invalid status at record {index}")
            expected_previous = record.record_hash
        if expected_last_hash is not None:
            anchor = expected_last_hash.strip().lower()
            if len(anchor) != 64 or any(char not in "0123456789abcdef" for char in anchor):
                errors.append("expected_last_hash must be a SHA-256 hex digest")
            elif anchor != expected_previous:
                errors.append("external last-hash anchor mismatch")
        return {
            "ok": not errors,
            "records": len(records),
            "last_hash": expected_previous,
            "anchor_checked": expected_last_hash is not None,
            "errors": errors,
        }

    def latest_by_control(self, profiles: str | Iterable[str] | None = None) -> dict[str, EvidenceRecord]:
        """Return latest records, optionally restricted to one or more profiles."""
        allowed: set[str] | None
        if profiles is None:
            allowed = None
        elif isinstance(profiles, str):
            allowed = {profiles.strip().lower()}
        else:
            allowed = {profile.strip().lower() for profile in profiles}
        latest: dict[str, EvidenceRecord] = {}
        for record in self._records():
            if allowed is not None and record.profile not in allowed:
                continue
            latest[record.control_id] = record
        return latest


def required_evidence(profile: str) -> tuple[str, ...]:
    """Return evidence identifiers required for a supported profile."""
    selected = profile.strip().lower()
    if selected not in _REQUIRED_EVIDENCE:
        raise ValueError(f"unsupported assurance profile: {selected}")
    base = _REQUIRED_EVIDENCE["baseline"]
    return tuple(dict.fromkeys((*base, *_REQUIRED_EVIDENCE[selected])))


def evaluate_evidence(profile: str, path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    """Evaluate whether required evidence has a current ``verified`` record.

    ``verified`` means a named operator, assessor, or automated exercise recorded
    an observation. It does not mean the resulting compliance or authorization
    has been granted.
    """
    selected = profile.strip().lower()
    try:
        required = required_evidence(selected)
    except ValueError as exc:
        return {
            "ok": False,
            "profile": selected,
            "ledger_configured": False,
            "required": [],
            "verified": [],
            "missing": [],
            "failed": [],
            "invalid": [str(exc)],
            "ledger": {"ok": False, "records": 0, "errors": [str(exc)]},
        }
    ledger_path = Path(path or os.environ.get("AEON_ASSURANCE_EVIDENCE_PATH", "")) if (path or os.environ.get("AEON_ASSURANCE_EVIDENCE_PATH")) else None
    if ledger_path is None:
        return {
            "ok": False,
            "profile": selected,
            "ledger_configured": False,
            "required": list(required),
            "verified": [],
            "missing": list(required),
            "failed": [],
            "invalid": [],
            "ledger": {"ok": False, "records": 0, "errors": ["evidence ledger is not configured"]},
        }

    ledger = EvidenceLedger(ledger_path)
    expected_last_hash = os.environ.get("AEON_ASSURANCE_LAST_HASH")
    integrity = ledger.verify(expected_last_hash=expected_last_hash)
    profiles = ("baseline", selected) if selected != "baseline" else ("baseline",)
    latest = ledger.latest_by_control(profiles) if integrity["ok"] else {}
    verified = sorted(control for control in required if latest.get(control) and latest[control].status == "verified")
    failed = sorted(control for control in required if latest.get(control) and latest[control].status == "failed")
    missing = sorted(set(required) - set(verified) - set(failed))
    return {
        "ok": integrity["ok"] and not missing and not failed,
        "profile": selected,
        "ledger_configured": True,
        "required": list(required),
        "verified": verified,
        "missing": missing,
        "failed": failed,
        "invalid": [],
        "ledger": integrity,
    }


def sha256_file(path: str | os.PathLike[str]) -> str:
    """Return the SHA-256 digest of an evidence artifact without exposing it."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
