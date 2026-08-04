"""AEON OS — Compliance readiness HTTP API.

Read-only routes registered via :func:`register_compliance_routes` (called
from ``aeon_server.py``). Routes report evidence-ledger coverage for
compliance frameworks; they do not assert certifications.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from flask import g, jsonify, request

from aeon_auth import require_auth, require_workspace_role
from aeon_compliance import (
    CONTROL_REGISTRY,
    FRAMEWORKS,
    attestation_summary,
    framework_coverage,
)


def _ledger_path() -> Path | None:
    configured = os.environ.get("AEON_ASSURANCE_EVIDENCE_PATH")
    if not configured:
        return None
    return Path(configured)


def register_compliance_routes(app: Any) -> None:
    @app.route("/compliance/frameworks", methods=["GET"])
    @require_auth
    @require_workspace_role("VIEWER")
    def compliance_frameworks():
        ledger = _ledger_path()
        coverage = framework_coverage(ledger)
        return jsonify(
            {
                "ok": True,
                "workspace_id": g.workspace_id,
                "ledger_configured": ledger is not None,
                "frameworks": coverage,
            }
        )

    @app.route("/compliance/controls", methods=["GET"])
    @require_auth
    @require_workspace_role("VIEWER")
    def compliance_controls():
        profile = (request.args.get("profile") or "baseline").strip().lower()
        try:
            from aeon_assurance import evaluate_evidence

            evaluation = evaluate_evidence(profile, path=str(_ledger_path()) if _ledger_path() else None)
            if evaluation.get("invalid"):
                return jsonify({"ok": False, "error": "; ".join(evaluation["invalid"])}), 400
            verified = set(evaluation.get("verified", []))
            failed = set(evaluation.get("failed", []))
            controls = []
            for control_id in evaluation.get("required", []):
                registry = CONTROL_REGISTRY.get(control_id, {})
                if control_id in verified:
                    status = "verified"
                elif control_id in failed:
                    status = "failed"
                else:
                    status = "missing"
                controls.append(
                    {
                        "control_id": control_id,
                        "title": registry.get("title", control_id),
                        "description": registry.get("description", ""),
                        "frameworks": sorted(fid for fid, framework in FRAMEWORKS.items() if control_id in framework["controls"]),
                        "status": status,
                    }
                )
            return jsonify({"ok": True, "profile": profile, "controls": controls, "count": len(controls)})
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/compliance/attestation", methods=["GET"])
    @require_auth
    @require_workspace_role("VIEWER")
    def compliance_attestation():
        profile = (request.args.get("profile") or "baseline").strip().lower()
        summary = attestation_summary(profile, _ledger_path())
        if not summary.get("ok") and "error" in summary:
            return jsonify({"ok": False, "error": summary["error"]}), 400
        return jsonify({"ok": True, "attestation": summary})
