"""Enterprise inference contracts for AEON.

This module is intentionally dependency-light and side-effect free.  It provides
stable contracts that chat, workflow, and sector adapters can use before an LLM
answer is exposed to a user or an automation.  It does not claim that a score
is a probability or that a response is error-free; it makes uncertainty,
evidence, and approval state explicit.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence


INFERENCE_STATUSES = frozenset(
    {
        "answered",
        "answered_with_warning",
        "needs_more_information",
        "abstained",
        "blocked_by_policy",
        "pending_human_approval",
        "failed",
    }
)


@dataclass(frozen=True)
class EvidenceItem:
    """A source fragment eligible to support an answer claim."""

    source_id: str
    chunk_id: str
    text: str
    relevance: float = 0.0
    authority: float = 0.0
    freshness: float = 0.0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.source_id or not self.chunk_id:
            raise ValueError("source_id and chunk_id are required")
        for name in ("relevance", "authority", "freshness"):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Citation:
    """A citation selected by a response validator."""

    source_id: str
    chunk_id: str
    quote: str = ""
    entailment: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class GroundingAssessment:
    """Deterministic evidence checks applied around probabilistic generation."""

    retrieval_score: float
    groundedness_score: float
    citation_coverage: float
    contradictions: tuple[str, ...] = ()
    citations: tuple[Citation, ...] = ()

    @property
    def supported(self) -> bool:
        return not self.contradictions and self.groundedness_score >= 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "retrieval_score": self.retrieval_score,
            "groundedness_score": self.groundedness_score,
            "citation_coverage": self.citation_coverage,
            "contradictions": list(self.contradictions),
            "citations": [citation.to_dict() for citation in self.citations],
            "supported": self.supported,
        }


@dataclass(frozen=True)
class InferencePolicy:
    """Runtime quality and safety thresholds for a task/profile combination."""

    require_grounding: bool = False
    min_retrieval_score: float = 0.0
    min_groundedness_score: float = 0.0
    min_citation_coverage: float = 0.0
    require_citations: bool = False
    require_human_review: bool = False
    risk_level: str = "low"

    def __post_init__(self) -> None:
        for name in (
            "min_retrieval_score",
            "min_groundedness_score",
            "min_citation_coverage",
        ):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")


@dataclass(frozen=True)
class InferenceResult:
    """Stable, auditable result envelope returned by enterprise inference."""

    status: str
    answer: str = ""
    reason: str | None = None
    evidence: GroundingAssessment | None = None
    confidence: float | None = None
    review_required: bool = False
    provider: str | None = None
    model: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in INFERENCE_STATUSES:
            raise ValueError(f"unknown inference status: {self.status}")
        if self.confidence is not None and not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be between 0 and 1")

    @property
    def ok(self) -> bool:
        return self.status in {"answered", "answered_with_warning"}

    def to_dict(self) -> dict[str, Any]:
        result = {
            "ok": self.ok,
            "status": self.status,
            "answer": self.answer,
            "reason": self.reason,
            "confidence": self.confidence,
            "review_required": self.review_required,
            "provider": self.provider,
            "model": self.model,
            "metadata": dict(self.metadata),
        }
        result["evidence"] = self.evidence.to_dict() if self.evidence else None
        return result


def _bounded(value: float) -> float:
    return round(max(0.0, min(1.0, float(value))), 4)


def _claim_count(answer: str) -> int:
    """Approximate claim count without pretending to perform semantic parsing."""
    fragments = [part.strip() for part in answer.replace("\n", ".").split(".")]
    return max(1, len([part for part in fragments if part])) if answer.strip() else 0


def assess_grounding(
    answer: str,
    evidence: Sequence[EvidenceItem] = (),
    citations: Sequence[Citation] = (),
    *,
    contradictions: Sequence[str] = (),
) -> GroundingAssessment:
    """Compute transparent evidence signals.

    This is a conservative baseline, not a replacement for a semantic
    entailment model.  A later verifier can supply stronger entailment scores
    while preserving this result contract.
    """
    items = tuple(evidence)
    refs = tuple(citations)
    retrieval = max((item.relevance for item in items), default=0.0)
    if refs:
        grounded = sum(_bounded(citation.entailment) for citation in refs) / len(refs)
    else:
        grounded = 0.0 if answer.strip() else 1.0
    coverage = _bounded(len(refs) / max(1, _claim_count(answer))) if answer.strip() else 1.0
    return GroundingAssessment(
        retrieval_score=_bounded(retrieval),
        groundedness_score=_bounded(grounded),
        citation_coverage=coverage,
        contradictions=tuple(str(item) for item in contradictions),
        citations=refs,
    )


def decide_inference(
    answer: str,
    assessment: GroundingAssessment,
    policy: InferencePolicy,
    *,
    provider: str | None = None,
    model: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> InferenceResult:
    """Apply fail-closed quality gates to an already generated answer."""
    if assessment.contradictions:
        return InferenceResult(
            status="abstained",
            reason="conflicting evidence was detected",
            evidence=assessment,
            review_required=policy.require_human_review,
            provider=provider,
            model=model,
            metadata=metadata or {},
        )
    if not answer.strip():
        return InferenceResult(
            status="needs_more_information",
            reason="the model returned an empty answer",
            evidence=assessment,
            review_required=policy.require_human_review,
            provider=provider,
            model=model,
            metadata=metadata or {},
        )
    if policy.require_grounding:
        failures: list[str] = []
        if assessment.retrieval_score < policy.min_retrieval_score:
            failures.append("retrieval evidence is below the required threshold")
        if assessment.groundedness_score < policy.min_groundedness_score:
            failures.append("groundedness is below the required threshold")
        if policy.require_citations and assessment.citation_coverage < policy.min_citation_coverage:
            failures.append("citation coverage is below the required threshold")
        if failures:
            return InferenceResult(
                status="abstained",
                reason="; ".join(failures),
                evidence=assessment,
                review_required=policy.require_human_review,
                provider=provider,
                model=model,
                metadata=metadata or {},
            )
    confidence = _bounded(
        (assessment.retrieval_score + assessment.groundedness_score + assessment.citation_coverage) / 3
    )
    status = "pending_human_approval" if policy.require_human_review else "answered"
    return InferenceResult(
        status=status,
        answer=answer,
        evidence=assessment,
        confidence=confidence,
        review_required=policy.require_human_review,
        provider=provider,
        model=model,
        metadata=metadata or {},
    )


def result_fingerprint(result: InferenceResult) -> str:
    """Return a stable fingerprint for idempotency and audit correlation."""
    payload = json.dumps(result.to_dict(), sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


__all__ = [
    "Citation",
    "EvidenceItem",
    "GroundingAssessment",
    "InferencePolicy",
    "InferenceResult",
    "INFERENCE_STATUSES",
    "assess_grounding",
    "decide_inference",
    "result_fingerprint",
]
