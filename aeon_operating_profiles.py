"""AEON OS operating profiles.

Operating profiles are the policy-safe composition layer between AEON's broad
module catalog and a particular organization.  They describe defaults, not
certifications: a profile can recommend controls and plugins, but it never
claims that an organization is compliant merely because it selected a profile.

The manager stores only non-secret workspace configuration in the AEON state
root.  Credentials, connection strings, and plugin configuration remain in
their existing secret/configuration systems.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from aeon_marketplace import BUILTIN_PLUGIN_CATALOG

PROFILE_VERSION = 1
_DEFAULT_PROFILE_ID = "general-business"
_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")
_ALLOWED_DEPLOYMENTS = frozenset({"cloud", "hybrid", "on-premise", "air-gapped", "edge"})
_ALLOWED_CLASSIFICATIONS = frozenset({"public", "internal", "confidential", "restricted", "secret"})
_ALLOWED_ORG_TYPES = frozenset({
    "startup", "sme", "enterprise", "nonprofit", "university", "healthcare-provider",
    "financial-institution", "manufacturer", "utility", "municipality", "government-agency",
    "defense-contractor", "public-safety-agency",
})

# These are public sector/industry identifiers already understood by the
# sector registry or marketplace catalog. New identifiers can be added without
# changing the route contract.
_ALLOWED_SECTORS = frozenset({
    "general", "cybersecurity", "health", "finance", "retail", "transport", "manufacturing",
    "tourism", "utilities", "heritage", "sme", "energy", "telecom", "agriculture", "education",
    "public-safety", "real-estate", "professional", "government", "defense",
})

_BUILTIN_PLUGIN_IDS = frozenset(plugin.id for plugin in BUILTIN_PLUGIN_CATALOG)


@dataclass(frozen=True)
class OperatingProfile:
    """A non-secret, reviewable set of defaults for an AEON workspace."""

    id: str
    name: str
    description: str
    audience: str
    sectors: tuple[str, ...]
    organization_types: tuple[str, ...]
    deployment_modes: tuple[str, ...]
    data_classifications: tuple[str, ...]
    compliance_frameworks: tuple[str, ...]
    default_plugins: tuple[str, ...]
    recommended_capabilities: tuple[str, ...]
    approval_required_for: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    version: int = PROFILE_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "audience": self.audience,
            "sectors": list(self.sectors),
            "organization_types": list(self.organization_types),
            "deployment_modes": list(self.deployment_modes),
            "data_classifications": list(self.data_classifications),
            "compliance_frameworks": list(self.compliance_frameworks),
            "default_plugins": list(self.default_plugins),
            "recommended_capabilities": list(self.recommended_capabilities),
            "approval_required_for": list(self.approval_required_for),
            "notes": list(self.notes),
            "version": self.version,
        }


@dataclass(frozen=True)
class WorkspaceOperatingProfile:
    """The selected profile plus explicit workspace context overrides."""

    workspace_id: str
    profile_id: str
    sector: str = "general"
    organization_type: str = "enterprise"
    deployment_mode: str = "cloud"
    data_classification: str = "internal"
    compliance_frameworks: tuple[str, ...] = ()
    selected_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self, profile: OperatingProfile | None = None) -> dict[str, Any]:
        result: dict[str, Any] = {
            "workspace_id": self.workspace_id,
            "profile_id": self.profile_id,
            "sector": self.sector,
            "organization_type": self.organization_type,
            "deployment_mode": self.deployment_mode,
            "data_classification": self.data_classification,
            "compliance_frameworks": list(self.compliance_frameworks),
            "selected_at": self.selected_at,
            "updated_at": self.updated_at,
        }
        if profile is not None:
            result["profile"] = profile.to_dict()
        return result


def _profile(
    profile_id: str,
    name: str,
    description: str,
    audience: str,
    *,
    sectors: tuple[str, ...],
    organization_types: tuple[str, ...],
    deployment_modes: tuple[str, ...] = ("cloud", "hybrid", "on-premise"),
    classifications: tuple[str, ...] = ("public", "internal", "confidential"),
    frameworks: tuple[str, ...] = (),
    plugins: tuple[str, ...] = (),
    capabilities: tuple[str, ...] = (),
    approvals: tuple[str, ...] = (),
    notes: tuple[str, ...] = (),
) -> OperatingProfile:
    return OperatingProfile(
        id=profile_id,
        name=name,
        description=description,
        audience=audience,
        sectors=sectors,
        organization_types=organization_types,
        deployment_modes=deployment_modes,
        data_classifications=classifications,
        compliance_frameworks=frameworks,
        default_plugins=plugins,
        recommended_capabilities=capabilities,
        approval_required_for=approvals,
        notes=notes,
    )


# Keep this catalog opinionated but declarative. It is intentionally separate
# from the plugin catalog so adding a profile never grants a new permission.
OPERATING_PROFILES: tuple[OperatingProfile, ...] = (
    _profile(
        "general-business", "General Business", "Balanced defaults for most teams and service companies.", "commercial",
        sectors=("general", "sme"), organization_types=("startup", "sme", "enterprise", "nonprofit"),
        plugins=("workflow-orchestrator", "model-gateway", "audit-exporter", "connector-health"),
        capabilities=("builtin:math", "builtin:search", "builtin:fetch"),
        notes=("Use this as a neutral starting point, then select a sector profile when data and controls are known.",),
    ),
    _profile(
        "regulated-enterprise", "Regulated Enterprise", "Enterprise defaults with stronger approvals, evidence, and data governance.", "commercial",
        sectors=("general", "finance", "health", "utilities"), organization_types=("enterprise", "financial-institution", "utility"),
        classifications=("internal", "confidential", "restricted"), frameworks=("ISO 27001", "SOC 2", "NIST CSF"),
        plugins=("governance-ai", "compliance-evidence", "access-review", "dlp-guard", "approval-gate", "audit-exporter", "residency-guard"),
        capabilities=("builtin:math", "builtin:search", "builtin:fetch"), approvals=("external-write", "restricted-data-access", "production-change"),
    ),
    _profile(
        "healthcare-provider", "Healthcare Provider", "Patient-safety defaults for providers, clinics, and health operations.", "regulated",
        sectors=("health",), organization_types=("healthcare-provider", "enterprise"), classifications=("confidential", "restricted"),
        frameworks=("HIPAA", "HITECH", "NIST CSF"), plugins=("clinical-notes", "healthcare-triage", "readmission-risk", "dlp-guard", "approval-gate", "audit-exporter"),
        capabilities=("builtin:search", "builtin:fetch"), approvals=("clinical-decision", "restricted-data-access"),
        notes=("AI recommendations remain decision support and require qualified human review.",),
    ),
    _profile(
        "financial-services", "Financial Services", "Fraud, risk, and audit controls for banks, fintechs, and insurers.", "regulated",
        sectors=("finance",), organization_types=("financial-institution", "enterprise"), classifications=("confidential", "restricted"),
        frameworks=("PCI DSS", "SOC 2", "ISO 27001", "NIST CSF"), plugins=("credit-risk", "reconciliation", "fraud-scoring", "finance-model-validator", "dlp-guard", "approval-gate", "audit-exporter"),
        capabilities=("builtin:math", "builtin:search"), approvals=("credit-decision", "payment-action", "restricted-data-access"),
    ),
    _profile(
        "critical-infrastructure", "Critical Infrastructure", "Resilience and change-control defaults for energy, utilities, and essential services.", "regulated",
        sectors=("utilities", "energy", "telecom", "transport"), organization_types=("utility", "enterprise", "government-agency"),
        deployment_modes=("hybrid", "on-premise", "air-gapped", "edge"), classifications=("confidential", "restricted", "secret"),
        frameworks=("NIST 800-53", "NIST CSF", "ISO 27001"), plugins=("grid-monitor", "utility-load-forecast", "energy-market-insights", "telecom-network-health", "dr-coordinator", "incident-runbook", "approval-gate", "siem-forwarder"),
        capabilities=("builtin:math", "builtin:search"), approvals=("grid-control", "production-change", "restricted-data-access"),
    ),
    _profile(
        "government-agency", "Government Agency", "Public-sector defaults for transparent, accountable, and policy-controlled operations.", "government",
        sectors=("government", "utilities", "public-safety", "heritage", "education"), organization_types=("municipality", "government-agency"),
        deployment_modes=("cloud", "hybrid", "on-premise", "air-gapped"), classifications=("public", "internal", "confidential", "restricted"),
        frameworks=("NIST 800-53", "FedRAMP", "NIST CSF", "CJIS"), plugins=("gov-compliance-ai", "compliance-evidence", "approval-gate", "audit-exporter", "residency-guard", "public-safety-ops", "siem-forwarder"),
        capabilities=("builtin:search", "builtin:fetch"), approvals=("public-records-change", "benefits-decision", "restricted-data-access", "production-change"),
        notes=("Profile selection is not an authorization to process classified information or a certification of FedRAMP/CJIS compliance.",),
    ),
    _profile(
        "defense-air-gapped", "Defense / Air-Gapped", "Fail-closed defaults for disconnected, mission-sensitive deployments.", "government",
        sectors=("defense", "cybersecurity", "public-safety"), organization_types=("defense-contractor", "government-agency"),
        deployment_modes=("on-premise", "air-gapped", "edge"), classifications=("restricted", "secret"), frameworks=("NIST 800-53", "FedRAMP High", "CMMC"),
        plugins=("cyber-threat-ops", "threat-intel", "incident-runbook", "compliance-evidence", "approval-gate", "audit-exporter", "residency-guard"),
        capabilities=("builtin:math",), approvals=("mission-action", "external-write", "restricted-data-access", "production-change"),
        notes=("External network connectors must be explicitly reviewed and are not enabled by profile selection.",),
    ),
    _profile(
        "education", "Education", "Student-safety and privacy defaults for schools, colleges, and universities.", "regulated",
        sectors=("education",), organization_types=("university", "government-agency", "nonprofit"), classifications=("internal", "confidential", "restricted"),
        frameworks=("FERPA", "COPPA", "NIST CSF"), plugins=("education-student-success", "dlp-guard", "approval-gate", "audit-exporter", "knowledge-curator"),
        capabilities=("builtin:search", "builtin:fetch"), approvals=("student-record-access", "high-impact-decision"),
    ),
    _profile(
        "manufacturing-operations", "Manufacturing Operations", "Plant, quality, and supply-chain defaults for industrial operators.", "commercial",
        sectors=("manufacturing", "retail", "transport"), organization_types=("manufacturer", "enterprise", "sme"), classifications=("internal", "confidential"),
        frameworks=("ISO 9001", "ISO 27001", "NIST CSF"), plugins=("manufacturing-quality", "fleet-optimizer", "inventory-forecast", "developer-quality", "connector-health", "incident-runbook"),
        capabilities=("builtin:math", "builtin:search"), approvals=("production-change", "safety-action"),
    ),
)

_PROFILE_MAP = {profile.id: profile for profile in OPERATING_PROFILES}


def _validate_id(value: Any, field: str) -> str:
    text = str(value or "").strip().lower()
    if not _ID_PATTERN.fullmatch(text):
        raise ValueError(f"{field} must be a lowercase slug")
    return text


def _validate_profile(profile: OperatingProfile) -> None:
    _validate_id(profile.id, "profile id")
    if profile.version != PROFILE_VERSION:
        raise ValueError(f"unsupported profile version: {profile.version}")
    if not profile.sectors or not set(profile.sectors) <= _ALLOWED_SECTORS:
        raise ValueError(f"profile {profile.id} contains an unknown sector")
    if not set(profile.organization_types) <= _ALLOWED_ORG_TYPES:
        raise ValueError(f"profile {profile.id} contains an unknown organization type")
    if not set(profile.deployment_modes) <= _ALLOWED_DEPLOYMENTS:
        raise ValueError(f"profile {profile.id} contains an unknown deployment mode")
    if not set(profile.data_classifications) <= _ALLOWED_CLASSIFICATIONS:
        raise ValueError(f"profile {profile.id} contains an unknown data classification")
    missing_plugins = set(profile.default_plugins) - _BUILTIN_PLUGIN_IDS
    if missing_plugins:
        raise ValueError(f"profile {profile.id} references unknown plugins: {sorted(missing_plugins)}")


for _registered_profile in OPERATING_PROFILES:
    _validate_profile(_registered_profile)


def list_profiles(*, sector: str | None = None, organization_type: str | None = None, deployment_mode: str | None = None) -> list[dict[str, Any]]:
    """Return public profile metadata, optionally filtered by context."""
    sector_value = str(sector or "").strip().lower()
    org_value = str(organization_type or "").strip().lower()
    deployment_value = str(deployment_mode or "").strip().lower()
    profiles = []
    for profile in OPERATING_PROFILES:
        if sector_value and sector_value not in profile.sectors:
            continue
        if org_value and org_value not in profile.organization_types:
            continue
        if deployment_value and deployment_value not in profile.deployment_modes:
            continue
        profiles.append(profile.to_dict())
    return profiles


def get_profile(profile_id: str) -> OperatingProfile | None:
    """Resolve one registered profile by slug."""
    return _PROFILE_MAP.get(str(profile_id or "").strip().lower())


def recommend_profiles(*, sector: str | None = None, organization_type: str | None = None, deployment_mode: str | None = None, data_classification: str | None = None) -> list[dict[str, Any]]:
    """Rank profiles by how many requested context dimensions they match."""
    values = {
        "sector": str(sector or "").strip().lower(),
        "organization_type": str(organization_type or "").strip().lower(),
        "deployment_mode": str(deployment_mode or "").strip().lower(),
        "data_classification": str(data_classification or "").strip().lower(),
    }
    ranked: list[tuple[int, OperatingProfile]] = []
    for profile in OPERATING_PROFILES:
        score = 0
        if values["sector"] and values["sector"] in profile.sectors:
            score += 4
        if values["organization_type"] and values["organization_type"] in profile.organization_types:
            score += 3
        if values["deployment_mode"] and values["deployment_mode"] in profile.deployment_modes:
            score += 2
        if values["data_classification"] and values["data_classification"] in profile.data_classifications:
            score += 1
        ranked.append((score, profile))
    ranked.sort(key=lambda item: (-item[0], item[1].id))
    return [{"match_score": score, "profile": profile.to_dict()} for score, profile in ranked]


def _root_path(root: str | Path | None = None) -> Path:
    return Path(root or os.environ.get("AEON_ROOT", "./aeon_state/server")) / "operating_profiles.json"


class OperatingProfileManager:
    """Persist workspace profile selections in a small atomic JSON store."""

    def __init__(self, root: str | Path | None = None) -> None:
        path = _root_path(root)
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def _read(self) -> dict[str, Any]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else {"version": PROFILE_VERSION, "workspaces": {}}
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {"version": PROFILE_VERSION, "workspaces": {}}

    def _write(self, data: dict[str, Any]) -> None:
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        temp.replace(self.path)

    def get(self, workspace_id: str) -> WorkspaceOperatingProfile:
        workspace = str(workspace_id or "").strip()
        if not workspace:
            raise ValueError("workspace_id is required")
        with self._lock:
            row = self._read().get("workspaces", {}).get(workspace, {})
        if not row:
            return WorkspaceOperatingProfile(workspace_id=workspace, profile_id=_DEFAULT_PROFILE_ID)
        return WorkspaceOperatingProfile(
            workspace_id=workspace,
            profile_id=str(row.get("profile_id", _DEFAULT_PROFILE_ID)),
            sector=str(row.get("sector", "general")),
            organization_type=str(row.get("organization_type", "enterprise")),
            deployment_mode=str(row.get("deployment_mode", "cloud")),
            data_classification=str(row.get("data_classification", "internal")),
            compliance_frameworks=tuple(row.get("compliance_frameworks") or ()),
            selected_at=float(row.get("selected_at", time.time())),
            updated_at=float(row.get("updated_at", time.time())),
        )

    def set(self, workspace_id: str, *, profile_id: str, sector: str = "general", organization_type: str = "enterprise", deployment_mode: str = "cloud", data_classification: str = "internal", compliance_frameworks: list[str] | tuple[str, ...] = ()) -> WorkspaceOperatingProfile:
        workspace = str(workspace_id or "").strip()
        if not workspace:
            raise ValueError("workspace_id is required")
        profile = get_profile(profile_id)
        if profile is None:
            raise ValueError("unknown operating profile")
        sector_value = _validate_id(sector, "sector")
        org_value = _validate_id(organization_type, "organization_type")
        deployment_value = _validate_id(deployment_mode, "deployment_mode")
        classification_value = _validate_id(data_classification, "data_classification")
        if sector_value not in _ALLOWED_SECTORS:
            raise ValueError("unknown sector")
        if org_value not in _ALLOWED_ORG_TYPES:
            raise ValueError("unknown organization_type")
        if deployment_value not in _ALLOWED_DEPLOYMENTS:
            raise ValueError("unknown deployment_mode")
        if classification_value not in _ALLOWED_CLASSIFICATIONS:
            raise ValueError("unknown data_classification")
        if sector_value not in profile.sectors and sector_value != "general":
            raise ValueError("sector is not supported by the selected profile")
        if org_value not in profile.organization_types:
            raise ValueError("organization_type is not supported by the selected profile")
        if deployment_value not in profile.deployment_modes:
            raise ValueError("deployment_mode is not supported by the selected profile")
        if classification_value not in profile.data_classifications:
            raise ValueError("data_classification is not supported by the selected profile")
        frameworks = tuple(sorted({str(item).strip()[:80] for item in compliance_frameworks if str(item).strip()}))
        now = time.time()
        existing = self.get(workspace)
        selection = WorkspaceOperatingProfile(
            workspace_id=workspace,
            profile_id=profile.id,
            sector=sector_value,
            organization_type=org_value,
            deployment_mode=deployment_value,
            data_classification=classification_value,
            compliance_frameworks=frameworks,
            selected_at=existing.selected_at if existing.profile_id != _DEFAULT_PROFILE_ID or self._read().get("workspaces", {}).get(workspace) else now,
            updated_at=now,
        )
        with self._lock:
            data = self._read()
            data.setdefault("version", PROFILE_VERSION)
            data.setdefault("workspaces", {})[workspace] = selection.to_dict()
            self._write(data)
        return selection

    def effective(self, workspace_id: str) -> dict[str, Any]:
        selection = self.get(workspace_id)
        profile = get_profile(selection.profile_id) or get_profile(_DEFAULT_PROFILE_ID)
        assert profile is not None
        result = selection.to_dict(profile)
        result["effective"] = {
            "plugins": list(profile.default_plugins),
            "capabilities": list(profile.recommended_capabilities),
            "approval_required_for": list(profile.approval_required_for),
            "compliance_frameworks": sorted(set(profile.compliance_frameworks) | set(selection.compliance_frameworks)),
            "notes": list(profile.notes),
        }
        return result


def get_operating_profile_manager(root: str | Path | None = None) -> OperatingProfileManager:
    return OperatingProfileManager(root)


__all__ = [
    "OPERATING_PROFILES",
    "OperatingProfile",
    "OperatingProfileManager",
    "WorkspaceOperatingProfile",
    "get_operating_profile_manager",
    "get_profile",
    "list_profiles",
    "recommend_profiles",
]
