"""AEON OS — compliance framework control mapping and attestation summaries.

This module maps the assurance evidence ledger (``aeon_assurance``) onto
recognized compliance frameworks and produces coverage/attestation summaries.

Important disclaimer
====================
This module reports *status of evidence obligations* tracked in the evidence
ledger. It does not certify, authorize, or attest legal/regulatory compliance.
Actual SOC 2, HIPAA, PCI DSS, FedRAMP, CJIS, or DORA standing requires the
formal audit/authorization processes those programs define (QSA/3PAO/CMS
assessments, BAAs, ATOs, and agency agreements). Framework coverage shown
here is a readiness indicator, not a certification.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from aeon_assurance import EvidenceLedger, evaluate_evidence, required_evidence

# Control registry: control_id -> human-readable title/description.
# These are evidence obligations tracked by the ledger, mapped to frameworks.
CONTROL_REGISTRY: dict[str, dict[str, Any]] = {
    "security_assessment": {"title": "Independent security / penetration assessment", "description": "Third-party pen test and threat-model review with remediation evidence."},
    "kms_validation": {"title": "KMS/HSM-backed secret management", "description": "Encryption keys managed in a hardware-backed KMS with rotation evidence."},
    "audit_integrity": {"title": "Immutable audit-log integrity", "description": "Audit log append-only hash-chain validation (tamper detection)."},
    "backup_restore": {"title": "Backup & restore drill", "description": "Successful restore exercise from backup with timestamps and checksums."},
    "rto_rpo_measurement": {"title": "RTO/RPO measurement", "description": "Measured recovery time and recovery point objectives from drills."},
    "incident_response_exercise": {"title": "Incident-response exercise", "description": "Tabletop or live incident response drill with post-incident review."},
    "hipaa_risk_analysis": {"title": "HIPAA risk analysis", "description": "Documented security risk analysis for ePHI per 45 CFR 164.308."},
    "baa_review": {"title": "Business associate agreement", "description": "Executed BAAs covering ePHI handling and subprocessors."},
    "ephi_data_flow_validation": {"title": "ePHI data-flow validation", "description": "Validation of ePHI flows, storage locations, and retention/deletion."},
    "pci_scope_qsa_or_saq": {"title": "PCI DSS scope / QSA or SAQ validation", "description": "Cardholder-data environment scoping and SAQ/QSA evidence."},
    "dora_resilience_review": {"title": "DORA operational-resilience review", "description": "Digital Operational Resilience Act ICT risk, testing, and reporting review."},
    "financial_model_risk_review": {"title": "Financial model risk review", "description": "Validation and governance of models used for financial decisions."},
    "safety_case_review": {"title": "Critical-infrastructure safety case", "description": "Safety-case review for critical-infrastructure workloads."},
    "authority_approval": {"title": "Authority approval", "description": "Approval from the relevant regulatory or sector authority."},
    "segmentation_failover_test": {"title": "Segmentation & failover test", "description": "Network segmentation and failover testing evidence."},
    "fedramp_boundary_ssp_3pao": {"title": "FedRAMP boundary, SSP, 3PAO assessment", "description": "System security plan, authorization boundary, and 3PAO assessment."},
    "ato_or_agency_authorization": {"title": "ATO / agency authorization", "description": "Authority to Operate or equivalent agency authorization."},
    "cjis_agreement_review": {"title": "CJIS agreement review", "description": "Criminal Justice Information Services security policy agreement."},
}

# Framework -> controls relevant to that framework (subset of the registry).
FRAMEWORKS: dict[str, dict[str, Any]] = {
    "soc2": {
        "name": "SOC 2",
        "kind": "audit",
        "controls": [
            "security_assessment",
            "audit_integrity",
            "kms_validation",
            "backup_restore",
            "rto_rpo_measurement",
            "incident_response_exercise",
        ],
    },
    "iso27001": {
        "name": "ISO/IEC 27001",
        "kind": "audit",
        "controls": [
            "security_assessment",
            "audit_integrity",
            "kms_validation",
            "incident_response_exercise",
            "backup_restore",
        ],
    },
    "hipaa": {
        "name": "HIPAA (HITECH)",
        "kind": "regulated",
        "controls": [
            "hipaa_risk_analysis",
            "baa_review",
            "ephi_data_flow_validation",
            "audit_integrity",
            "kms_validation",
            "incident_response_exercise",
        ],
    },
    "pci_dss": {
        "name": "PCI DSS",
        "kind": "regulated",
        "controls": [
            "pci_scope_qsa_or_saq",
            "security_assessment",
            "audit_integrity",
            "kms_validation",
        ],
    },
    "fedramp": {
        "name": "FedRAMP",
        "kind": "government",
        "controls": [
            "fedramp_boundary_ssp_3pao",
            "ato_or_agency_authorization",
            "security_assessment",
            "audit_integrity",
            "kms_validation",
            "backup_restore",
            "incident_response_exercise",
        ],
    },
    "cjis": {
        "name": "CJIS Security Policy",
        "kind": "government",
        "controls": [
            "cjis_agreement_review",
            "authority_approval",
            "segmentation_failover_test",
            "audit_integrity",
            "kms_validation",
        ],
    },
    "dora": {
        "name": "DORA (EU)",
        "kind": "regulated",
        "controls": [
            "dora_resilience_review",
            "financial_model_risk_review",
            "rto_rpo_measurement",
            "incident_response_exercise",
            "backup_restore",
            "segmentation_failover_test",
        ],
    },
    "critical_infrastructure": {
        "name": "Critical Infrastructure (e.g., NERC-CIP)",
        "kind": "regulated",
        "controls": [
            "safety_case_review",
            "authority_approval",
            "segmentation_failover_test",
            "audit_integrity",
            "backup_restore",
            "rto_rpo_measurement",
            "incident_response_exercise",
        ],
    },
}

# Assurance ledger profiles that supply evidence for each framework.
_FRAMEWORK_PROFILES: dict[str, str] = {
    "soc2": "baseline",
    "iso27001": "baseline",
    "hipaa": "healthcare",
    "pci_dss": "financial",
    "fedramp": "government",
    "cjis": "critical_infrastructure",
    "dora": "financial",
    "critical_infrastructure": "critical_infrastructure",
}


def framework_ids() -> list[str]:
    return sorted(FRAMEWORKS)


def control_map(profile: str) -> list[dict[str, Any]]:
    """Return the control mapping for an assurance profile (status derived later)."""
    try:
        required = required_evidence(profile)
    except ValueError as exc:
        raise ValueError(f"unsupported assurance profile: {profile}") from exc
    rows: list[dict[str, Any]] = []
    for control_id in required:
        registry = CONTROL_REGISTRY.get(control_id, {})
        rows.append(
            {
                "control_id": control_id,
                "title": registry.get("title", control_id),
                "description": registry.get("description", ""),
                "frameworks": sorted(fid for fid, framework in FRAMEWORKS.items() if control_id in framework["controls"]),
            }
        )
    return rows


def _status_for(latest: dict[str, Any], control_id: str) -> str:
    record = latest.get(control_id)
    if record is None:
        return "missing"
    return record.status  # verified | failed | pending | not_applicable


def framework_coverage(ledger_path: str | Path | None) -> list[dict[str, Any]]:
    """Per-framework coverage summary from the evidence ledger."""
    results: list[dict[str, Any]] = []
    for framework_id in framework_ids():
        framework = FRAMEWORKS[framework_id]
        results.append(_framework_detail(framework_id, framework, ledger_path))
    return results


def _framework_detail(framework_id: str, framework: dict[str, Any], ledger_path: str | Path | None) -> dict[str, Any]:
    controls = framework["controls"]
    statuses: dict[str, str] = dict.fromkeys(controls, "missing")
    ledger = None
    if ledger_path is not None and Path(ledger_path).exists():
        ledger = EvidenceLedger(Path(ledger_path))
        profile = _FRAMEWORK_PROFILES.get(framework_id, "baseline")
        try:
            latest = ledger.latest_by_control(profile)
            for control in controls:
                if control in latest:
                    statuses[control] = latest[control].status
        except (ValueError, OSError):
            pass
    verified = sum(1 for status in statuses.values() if status == "verified")
    failed = sum(1 for status in statuses.values() if status == "failed")
    total = len(controls)
    return {
        "id": framework_id,
        "name": framework["name"],
        "kind": framework["kind"],
        "controls": [
            {
                "control_id": control,
                "title": CONTROL_REGISTRY.get(control, {}).get("title", control),
                "status": statuses[control],
            }
            for control in controls
        ],
        "total": total,
        "verified": verified,
        "failed": failed,
        "pending": total - verified - failed,
        "coverage_pct": round(verified / total * 100, 1) if total else 0.0,
        "ledger_configured": ledger is not None,
    }


def attestation_summary(profile: str, ledger_path: str | Path | None = None) -> dict[str, Any]:
    """Attestation readiness summary for one assurance profile."""
    try:
        mapping = control_map(profile)
    except ValueError as exc:
        return {"ok": False, "profile": profile, "error": str(exc)}
    evaluation = evaluate_evidence(profile, path=str(ledger_path) if ledger_path else None)
    total = len(mapping)
    verified = len(evaluation.get("verified", []))
    missing = len(evaluation.get("missing", []))
    failed = len(evaluation.get("failed", []))
    return {
        "ok": evaluation.get("ok", False),
        "profile": profile,
        "ledger_configured": evaluation.get("ledger_configured", False),
        "total_controls": total,
        "verified": verified,
        "missing": missing,
        "failed": failed,
        "coverage_pct": round(verified / total * 100, 1) if total else 0.0,
        "controls": mapping,
        "ledger": evaluation.get("ledger", {}),
        "framework_targets": sorted(fid for fid, framework in FRAMEWORKS.items() if profile in _required_profiles(fid)),
        "disclaimer": (
            "Coverage reflects evidence obligations tracked in the ledger, not a "
            "certification. Formal compliance requires the applicable audit/ATO process."
        ),
    }


def _required_profiles(framework_id: str) -> list[str]:
    profile = _FRAMEWORK_PROFILES.get(framework_id)
    if not profile:
        return []
    return ["baseline", profile] if profile != "baseline" else ["baseline"]


def _ledger_path_from_env() -> Path | None:
    configured = os.environ.get("AEON_ASSURANCE_EVIDENCE_PATH")
    if not configured:
        return None
    return Path(configured)


def evaluate_environment(profile: str | None = None) -> dict[str, Any]:
    """Evaluate production-compliance readiness for the readiness report.

    Called by ``aeon_server.validate_environment``. Returns ``ok`` plus
    ``missing``/``invalid`` lists the readiness report folds into its gate.
    Ledger-based evidence tracking only; never a certification.
    """
    selected = (profile or os.environ.get("AEON_COMPLIANCE_PROFILE", "baseline")).strip().lower()
    ledger_path = _ledger_path_from_env()
    frameworks = framework_coverage(ledger_path)
    try:
        required_evidence(selected)
    except ValueError as exc:
        return {
            "ok": False,
            "profile": selected,
            "ledger_configured": ledger_path is not None,
            "frameworks": frameworks,
            "missing": [],
            "invalid": [f"assurance profile: {exc}"],
        }
    if ledger_path is None:
        return {
            "ok": False,
            "profile": selected,
            "ledger_configured": False,
            "frameworks": frameworks,
            "missing": ["assurance evidence ledger is not configured"],
            "invalid": [],
        }
    try:
        evaluation = evaluate_evidence(selected, path=str(ledger_path))
    except Exception as exc:  # pragma: no cover - defensive
        return {
            "ok": False,
            "profile": selected,
            "ledger_configured": True,
            "frameworks": frameworks,
            "missing": [],
            "invalid": [f"assurance ledger: {exc}"],
        }
    missing = [f"assurance evidence: {control}" for control in evaluation.get("missing", [])]
    missing += [f"assurance evidence failed: {control}" for control in evaluation.get("failed", [])]
    missing += [f"assurance ledger: {error}" for error in evaluation.get("ledger", {}).get("errors", [])]
    invalid = [f"assurance profile: {error}" for error in evaluation.get("invalid", [])]
    return {
        "ok": evaluation.get("ok", False),
        "profile": selected,
        "ledger_configured": True,
        "frameworks": frameworks,
        "missing": missing,
        "invalid": invalid,
    }
