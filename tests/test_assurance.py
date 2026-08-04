"""Tests for non-sensitive assurance evidence tracking."""

from __future__ import annotations

import json

import pytest

from aeon_assurance import EvidenceLedger, evaluate_evidence, required_evidence

_BASELINE_CONTROLS = required_evidence("baseline")


def _record_all(ledger: EvidenceLedger, profile: str = "baseline") -> None:
    for control_id in required_evidence(profile):
        ledger.append(
            control_id=control_id,
            profile="baseline" if control_id in _BASELINE_CONTROLS else profile,
            status="verified",
            summary=f"Observed {control_id} during controlled test",
            source="test-suite",
        )


def test_hash_chain_detects_tampering_and_blocks_append(tmp_path):
    path = tmp_path / "evidence.ndjson"
    ledger = EvidenceLedger(path)
    first = ledger.append(
        control_id="audit_integrity",
        profile="baseline",
        status="verified",
        summary="Audit integrity test passed",
        source="test-suite",
    )
    path.write_text(path.read_text().replace("Audit integrity test passed", "tampered"), encoding="utf-8")

    report = ledger.verify()
    assert report["ok"] is False
    assert any("record_hash mismatch" in error for error in report["errors"])
    with pytest.raises(ValueError, match="invalid evidence ledger"):
        ledger.append(
            control_id="kms_validation",
            profile="baseline",
            status="verified",
            summary="KMS test passed",
            source="test-suite",
        )
    assert first.previous_hash == "0" * 64


def test_profile_evaluation_inherits_baseline_evidence(tmp_path):
    path = tmp_path / "evidence.ndjson"
    ledger = EvidenceLedger(path)
    _record_all(ledger, "healthcare")

    report = evaluate_evidence("healthcare", path)

    assert report["ok"] is True
    assert report["missing"] == []
    assert report["failed"] == []
    assert report["invalid"] == []


def test_not_applicable_is_not_a_verified_release_gate(tmp_path):
    path = tmp_path / "evidence.ndjson"
    ledger = EvidenceLedger(path)
    for control_id in required_evidence("baseline"):
        ledger.append(
            control_id=control_id,
            profile="baseline",
            status="not_applicable" if control_id == "rto_rpo_measurement" else "verified",
            summary=f"Recorded disposition for {control_id}",
            source="test-suite",
        )

    report = evaluate_evidence("baseline", path)

    assert report["ok"] is False
    assert "rto_rpo_measurement" in report["missing"]


def test_external_anchor_detects_tail_truncation(tmp_path):
    path = tmp_path / "evidence.ndjson"
    ledger = EvidenceLedger(path)
    ledger.append(
        control_id="audit_integrity",
        profile="baseline",
        status="verified",
        summary="Audit integrity test passed",
        source="test-suite",
    )
    second = ledger.append(
        control_id="kms_validation",
        profile="baseline",
        status="verified",
        summary="KMS validation passed",
        source="test-suite",
    )
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text(lines[0] + "\n", encoding="utf-8")

    report = ledger.verify(expected_last_hash=second.record_hash)

    assert report["ok"] is False
    assert "external last-hash anchor mismatch" in report["errors"]


def test_malformed_ledger_fails_closed(tmp_path):
    path = tmp_path / "evidence.ndjson"
    path.write_text(json.dumps({"control_id": "only-partial"}) + "\n", encoding="utf-8")

    report = evaluate_evidence("baseline", path)

    assert report["ok"] is False
    assert report["ledger"]["ok"] is False
    assert set(report["missing"]) == set(required_evidence("baseline"))
