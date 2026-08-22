"""Declarative sector intelligence packs for AEON.

Packs are runtime defaults and control metadata, not certifications or legal
advice. Organizations must review and configure them for their jurisdiction,
policies, and risk tolerance before production use.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from aeon_inference import InferencePolicy


@dataclass(frozen=True)
class SectorPack:
    id: str
    version: str
    sector: str
    jurisdictions: tuple[str, ...]
    risk_level: str
    inference_policy: InferencePolicy
    allowed_task_types: tuple[str, ...] = ()
    blocked_task_types: tuple[str, ...] = ()
    output_schema: Mapping[str, Any] = field(default_factory=dict)
    approved_model_tags: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "version": self.version,
            "sector": self.sector,
            "jurisdictions": list(self.jurisdictions),
            "risk_level": self.risk_level,
            "inference_policy": {
                "require_grounding": self.inference_policy.require_grounding,
                "min_retrieval_score": self.inference_policy.min_retrieval_score,
                "min_groundedness_score": self.inference_policy.min_groundedness_score,
                "min_citation_coverage": self.inference_policy.min_citation_coverage,
                "require_citations": self.inference_policy.require_citations,
                "require_human_review": self.inference_policy.require_human_review,
                "risk_level": self.inference_policy.risk_level,
            },
            "allowed_task_types": list(self.allowed_task_types),
            "blocked_task_types": list(self.blocked_task_types),
            "output_schema": dict(self.output_schema),
            "approved_model_tags": list(self.approved_model_tags),
            "notes": list(self.notes),
        }


_GENERAL_SCHEMA = {
    "type": "object",
    "required": ["answer", "review_required"],
    "properties": {
        "answer": {"type": "string"},
        "review_required": {"type": "boolean"},
        "limitations": {"type": "array", "items": {"type": "string"}},
    },
}


def _regulated_policy(*, review: bool = False, risk: str = "high") -> InferencePolicy:
    return InferencePolicy(
        require_grounding=True,
        min_retrieval_score=0.78,
        min_groundedness_score=0.90,
        min_citation_coverage=1.0,
        require_citations=True,
        require_human_review=review,
        risk_level=risk,
    )


def _grounded_policy(*, review: bool = False, risk: str = "medium") -> InferencePolicy:
    """Grounded decision-support policy for medium-risk sectors.

    Outputs must be grounded in retrieved evidence and cited, but do not
    require mandatory human review for advisory outputs.
    """
    return InferencePolicy(
        require_grounding=True,
        min_retrieval_score=0.72,
        min_groundedness_score=0.85,
        min_citation_coverage=0.90,
        require_citations=True,
        require_human_review=review,
        risk_level=risk,
    )


SECTOR_PACKS: tuple[SectorPack, ...] = (
    SectorPack(
        id="general-business",
        version="1.0.0",
        sector="general",
        jurisdictions=("global",),
        risk_level="low",
        inference_policy=InferencePolicy(),
        output_schema=_GENERAL_SCHEMA,
        approved_model_tags=("general", "coding", "reasoning"),
    ),
    SectorPack(
        id="healthcare-us-provider",
        version="1.0.0",
        sector="health",
        jurisdictions=("US",),
        risk_level="high",
        inference_policy=_regulated_policy(review=True),
        allowed_task_types=("retrieval_qa", "summarization", "clinical_documentation"),
        blocked_task_types=("autonomous_diagnosis", "autonomous_treatment_change"),
        output_schema=_GENERAL_SCHEMA,
        approved_model_tags=("private", "healthcare", "grounded"),
        notes=("Decision support only; qualified professional review remains required.",),
    ),
    SectorPack(
        id="financial-services-global",
        version="1.0.0",
        sector="finance",
        jurisdictions=("global",),
        risk_level="high",
        inference_policy=_regulated_policy(review=True),
        allowed_task_types=("retrieval_qa", "reconciliation", "risk_analysis", "report_draft"),
        blocked_task_types=("autonomous_credit_decision", "autonomous_payment"),
        output_schema=_GENERAL_SCHEMA,
        approved_model_tags=("private", "finance", "grounded", "calculation_verified"),
    ),
    SectorPack(
        id="government-public-sector",
        version="1.0.0",
        sector="government",
        jurisdictions=("global",),
        risk_level="high",
        inference_policy=_regulated_policy(review=True),
        allowed_task_types=("policy_research", "policy_qa", "procurement_support", "records_assistance", "drafting"),
        blocked_task_types=("autonomous_benefits_decision", "autonomous_enforcement"),
        output_schema=_GENERAL_SCHEMA,
        approved_model_tags=("private", "government", "provenance", "grounded"),
        notes=("Profile selection is not a certification or authorization to process classified data.",),
    ),
    SectorPack(
        id="defense-secure",
        version="1.0.0",
        sector="defense",
        jurisdictions=("global",),
        risk_level="critical",
        inference_policy=_regulated_policy(review=True, risk="critical"),
        allowed_task_types=("logistics_analysis", "maintenance_support", "document_retrieval"),
        blocked_task_types=("autonomous_kinetic_action", "autonomous_targeting"),
        output_schema=_GENERAL_SCHEMA,
        approved_model_tags=("air_gapped", "private", "defense", "grounded"),
        notes=("Read-only assistance by default; deployment and classification controls are mandatory.",),
    ),
    SectorPack(
        id="critical-infrastructure",
        version="1.0.0",
        sector="utilities",
        jurisdictions=("global",),
        risk_level="critical",
        inference_policy=_regulated_policy(review=True, risk="critical"),
        allowed_task_types=("maintenance", "incident_analysis", "forecasting", "runbook_support"),
        blocked_task_types=("autonomous_control", "unapproved_production_change"),
        output_schema=_GENERAL_SCHEMA,
        approved_model_tags=("edge", "private", "critical_infrastructure", "grounded"),
        notes=("Operational control actions require explicit, scoped human approval and safety interlocks.",),
    ),
    SectorPack(
        id="manufacturing-enterprise",
        version="1.0.0",
        sector="manufacturing",
        jurisdictions=("global",),
        risk_level="high",
        inference_policy=_regulated_policy(review=True),
        allowed_task_types=("quality_analysis", "maintenance", "root_cause_analysis", "work_instruction"),
        blocked_task_types=("autonomous_safety_override", "unapproved_machine_control"),
        output_schema=_GENERAL_SCHEMA,
        approved_model_tags=("private", "edge", "manufacturing", "grounded"),
    ),
    SectorPack(
        id="telecom-operator",
        version="1.0.0",
        sector="telecom",
        jurisdictions=("global",),
        risk_level="high",
        inference_policy=_regulated_policy(review=True),
        allowed_task_types=("sla_analysis", "capacity_planning", "fault_triage", "network_analysis"),
        blocked_task_types=("autonomous_network_change", "autonomous_traffic_shaping"),
        output_schema=_GENERAL_SCHEMA,
        approved_model_tags=("private", "telecom", "grounded", "edge"),
        notes=("Network-affecting actions require scoped human approval; SLA assessments are decision support.",),
    ),
    SectorPack(
        id="agriculture-producer",
        version="1.0.0",
        sector="agriculture",
        jurisdictions=("global",),
        risk_level="medium",
        inference_policy=_grounded_policy(),
        allowed_task_types=("yield_forecast", "irrigation_planning", "pest_risk_assessment", "field_analysis"),
        blocked_task_types=("autonomous_chemical_release", "autonomous_water_release"),
        output_schema=_GENERAL_SCHEMA,
        approved_model_tags=("private", "agriculture", "grounded"),
        notes=("Physical actuation (irrigation, chemical application) stays manual; outputs are decision support.",),
    ),
    SectorPack(
        id="education-institution",
        version="1.0.0",
        sector="education",
        jurisdictions=("global",),
        risk_level="high",
        inference_policy=_regulated_policy(review=True),
        allowed_task_types=("at_risk_analysis", "intervention_planning", "outcome_analytics", "curriculum_support"),
        blocked_task_types=("autonomous_grade_change", "autonomous_disciplinary_action", "autonomous_enrollment_decision"),
        output_schema=_GENERAL_SCHEMA,
        approved_model_tags=("private", "education", "grounded"),
        notes=("Student-impacting decisions require human review; data handling should follow applicable student-privacy law.",),
    ),
    SectorPack(
        id="public-safety-agency",
        version="1.0.0",
        sector="public_safety",
        jurisdictions=("global",),
        risk_level="critical",
        inference_policy=_regulated_policy(review=True, risk="critical"),
        allowed_task_types=("incident_prioritization", "dispatch_suggestion", "ops_briefing", "resource_analysis"),
        blocked_task_types=("autonomous_dispatch_authorization", "autonomous_enforcement", "autonomous_use_of_force"),
        output_schema=_GENERAL_SCHEMA,
        approved_model_tags=("private", "public_safety", "grounded", "provenance"),
        notes=("Emergency-response outputs are decision support; dispatch and enforcement authority remains with qualified personnel.",),
    ),
    SectorPack(
        id="real-estate-portfolio",
        version="1.0.0",
        sector="real_estate",
        jurisdictions=("global",),
        risk_level="medium",
        inference_policy=_grounded_policy(),
        allowed_task_types=("valuation_analysis", "market_analysis", "comparables_report", "portfolio_review"),
        blocked_task_types=("autonomous_acquisition", "autonomous_price_commitment"),
        output_schema=_GENERAL_SCHEMA,
        approved_model_tags=("private", "real_estate", "grounded"),
        notes=("Valuations are advisory estimates; final pricing and acquisition decisions stay with humans.",),
    ),
)

_PACK_BY_ID = {pack.id: pack for pack in SECTOR_PACKS}
_PACK_BY_SECTOR = {pack.sector: pack for pack in SECTOR_PACKS}


def list_sector_packs() -> list[dict[str, Any]]:
    return [pack.to_dict() for pack in SECTOR_PACKS]


def get_sector_pack(pack_id: str | None = None, *, sector: str | None = None) -> SectorPack:
    """Resolve a pack, defaulting safely to the general pack."""
    if pack_id:
        pack = _PACK_BY_ID.get(str(pack_id).strip().lower())
        if pack is not None:
            return pack
        raise ValueError(f"unknown sector pack: {pack_id}")
    if sector:
        return _PACK_BY_SECTOR.get(str(sector).strip().lower(), _PACK_BY_ID["general-business"])
    return _PACK_BY_ID["general-business"]


def task_allowed(pack: SectorPack, task_type: str) -> bool:
    task = str(task_type or "general").strip().lower()
    if task in pack.blocked_task_types:
        return False
    return not pack.allowed_task_types or task in pack.allowed_task_types


__all__ = ["SECTOR_PACKS", "SectorPack", "get_sector_pack", "list_sector_packs", "task_allowed"]
