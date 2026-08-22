"""Tests for non-sensitive assurance evidence tracking."""

from __future__ import annotations

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

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


def test_concurrent_appenders_preserve_hash_chain(tmp_path):
    path = tmp_path / "evidence.ndjson"
    ledgers = [EvidenceLedger(path), EvidenceLedger(path)]

    def append(index: int) -> str:
        record = ledgers[index % len(ledgers)].append(
            control_id=f"control_{index}",
            profile="baseline",
            status="verified",
            summary=f"Concurrent check {index}",
            source="test-suite",
        )
        return record.record_hash

    with ThreadPoolExecutor(max_workers=8) as executor:
        hashes = list(executor.map(append, range(32)))

    report = ledgers[0].verify()

    assert len(hashes) == 32
    assert len(set(hashes)) == 32
    assert report["ok"] is True
    assert report["records"] == 32


def test_cross_process_appenders_preserve_hash_chain(tmp_path):
    path = tmp_path / "evidence.ndjson"
    repo_root = str(Path(__file__).resolve().parents[1])
    append_code = """
import sys
from aeon_assurance import EvidenceLedger

ledger = EvidenceLedger(sys.argv[1])
index = sys.argv[2]
ledger.append(
    control_id=f\"process_{index}\",
    profile=\"baseline\",
    status=\"verified\",
    summary=f\"Process check {index}\",
    source=\"test-suite\",
)
"""

    def append(index: int) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-c", append_code, str(path), str(index)],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(append, range(16)))

    failures = [result.stderr for result in results if result.returncode != 0]
    report = EvidenceLedger(path).verify()

    assert failures == []
    assert report["ok"] is True
    assert report["records"] == 16
