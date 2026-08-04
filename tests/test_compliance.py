"""Regression coverage for AEON OS compliance readiness tooling.

Covers the framework/control registry integrity, attestation summaries built
from a temporary evidence ledger, and the read-only /compliance routes.
"""

from __future__ import annotations

import uuid

from aeon_assurance import EvidenceLedger
from aeon_compliance import (
    CONTROL_REGISTRY,
    FRAMEWORKS,
    attestation_summary,
    control_map,
    framework_coverage,
)


def _register(client, label: str) -> tuple[str, str]:
    response = client.post(
        "/auth/register",
        json={
            "email": f"compliance-{label}-{uuid.uuid4().hex[:8]}@test.local",
            "password": "secure123",
            "name": f"Compliance {label}",
        },
    )
    assert response.status_code == 201, response.get_json()
    data = response.get_json()
    return data["token"], data["user"]["workspace_id"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ── registry integrity ──────────────────────────────────────────────────────


def test_framework_control_registry_is_internally_consistent() -> None:
    assert len(FRAMEWORKS) >= 5
    for framework_id, framework in FRAMEWORKS.items():
        assert framework["name"]
        assert framework["controls"], f"{framework_id} has no controls"
        for control_id in framework["controls"]:
            assert control_id in CONTROL_REGISTRY, f"{framework_id} references unknown control {control_id}"
    # Every registered control is used by at least one framework.
    used = {control for framework in FRAMEWORKS.values() for control in framework["controls"]}
    assert set(CONTROL_REGISTRY) <= used


def test_control_map_for_all_supported_profiles() -> None:
    for profile in ("baseline", "healthcare", "financial", "critical_infrastructure", "government"):
        mapping = control_map(profile)
        assert mapping, profile
        assert mapping[0]["control_id"]
        assert "frameworks" in mapping[0]
    import pytest

    with pytest.raises(ValueError):
        control_map("not_a_profile")


# ── attestation summaries ───────────────────────────────────────────────────


def test_attestation_summary_with_fresh_ledger(tmp_path) -> None:
    ledger_path = tmp_path / "evidence.jsonl"
    summary = attestation_summary("healthcare", ledger_path)
    assert summary["ok"] is False
    assert summary["ledger_configured"] is True
    assert summary["total_controls"] > 0
    assert summary["verified"] == 0
    assert summary["missing"] == summary["total_controls"]
    assert summary["coverage_pct"] == 0.0
    assert "disclaimer" in summary


def test_attestation_summary_reflects_verified_evidence(tmp_path) -> None:
    ledger_path = tmp_path / "evidence.jsonl"
    ledger = EvidenceLedger(ledger_path)
    required = control_map("baseline")
    # Mark every baseline control verified.
    for row in required:
        ledger.append(
            control_id=row["control_id"],
            profile="baseline",
            status="verified",
            summary="automated drill passed",
            source="test",
        )
    summary = attestation_summary("baseline", ledger_path)
    assert summary["ok"] is True
    assert summary["verified"] == summary["total_controls"]
    assert summary["missing"] == 0
    assert summary["coverage_pct"] == 100.0


def test_framework_coverage(tmp_path) -> None:
    ledger_path = tmp_path / "evidence.jsonl"
    coverage = framework_coverage(ledger_path)
    by_id = {entry["id"]: entry for entry in coverage}
    assert "soc2" in by_id
    assert by_id["soc2"]["ledger_configured"] is False  # ledger file does not exist yet
    assert by_id["soc2"]["coverage_pct"] == 0.0

    ledger = EvidenceLedger(ledger_path)
    for row in control_map("baseline"):
        ledger.append(control_id=row["control_id"], profile="baseline", status="verified", summary="ok", source="test")
    coverage = framework_coverage(ledger_path)
    by_id = {entry["id"]: entry for entry in coverage}
    assert by_id["soc2"]["verified"] == by_id["soc2"]["total"]
    assert by_id["soc2"]["coverage_pct"] == 100.0


# ── routes ──────────────────────────────────────────────────────────────────


def test_compliance_routes_require_auth(client) -> None:
    assert client.get("/compliance/frameworks").status_code == 401
    assert client.get("/compliance/controls").status_code == 401
    assert client.get("/compliance/attestation").status_code == 401


def test_compliance_routes_work(client) -> None:
    token, _ = _register(client, "routes")
    response = client.get("/compliance/frameworks", headers=_headers(token))
    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["ledger_configured"] is False
    assert {entry["id"] for entry in data["frameworks"]} >= {"soc2", "hipaa", "fedramp", "dora"}

    response = client.get("/compliance/controls?profile=healthcare", headers=_headers(token))
    assert response.status_code == 200
    controls = response.get_json()["controls"]
    assert any(control["control_id"] == "baa_review" for control in controls)

    response = client.get("/compliance/attestation?profile=financial", headers=_headers(token))
    assert response.status_code == 200
    attestation = response.get_json()["attestation"]
    assert attestation["total_controls"] > 0

    # Invalid profile rejected.
    response = client.get("/compliance/controls?profile=nope", headers=_headers(token))
    assert response.status_code == 400
