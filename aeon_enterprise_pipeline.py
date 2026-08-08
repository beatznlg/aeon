"""Composable enterprise inference pipeline for AEON.

The pipeline is deliberately dependency-light and uses injected adapters for
retrieval, policy, and output validation. This lets existing chat/workflow
routes adopt the control plane incrementally without replacing the AEON kernel.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from aeon_inference import (
    Citation,
    EvidenceItem,
    InferencePolicy,
    InferenceResult,
    assess_grounding,
    decide_inference,
)
from aeon_sector_packs import get_sector_pack, task_allowed


EvidenceResolver = Callable[[str], Sequence[EvidenceItem]]
OutputValidator = Callable[[str], tuple[bool, str | None]]


class EnterpriseInferencePipeline:
    """Run one request through explicit quality and safety boundaries."""

    def __init__(
        self,
        provider: Any,
        *,
        evidence_resolver: EvidenceResolver | None = None,
        output_validator: OutputValidator | None = None,
    ) -> None:
        if provider is None or not callable(getattr(provider, "generate", None)):
            raise ValueError("provider must expose generate(prompt, system=...)" )
        self.provider = provider
        self.evidence_resolver = evidence_resolver
        self.output_validator = output_validator

    def run(
        self,
        query: str,
        *,
        system: str | None = None,
        policy: InferencePolicy | None = None,
        task_type: str = "general",
        workspace_id: str | None = None,
        sector: str | None = None,
        sector_pack_id: str | None = None,
        model: str | None = None,
        provider_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> InferenceResult:
        """Generate and validate an answer without mutating global provider state."""
        pack = get_sector_pack(sector_pack_id, sector=sector)
        active_policy = policy or pack.inference_policy
        output_metadata = self._metadata(metadata, task_type, workspace_id, sector)
        output_metadata.update(
            {
                "sector_pack_id": pack.id,
                "sector_pack_version": pack.version,
                "risk_level": pack.risk_level,
            }
        )

        if not str(query or "").strip():
            return InferenceResult(
                status="needs_more_information",
                reason="query is required",
                review_required=active_policy.require_human_review,
                provider=provider_id,
                model=model,
                metadata=output_metadata,
            )

        if not task_allowed(pack, task_type):
            return InferenceResult(
                status="blocked_by_policy",
                reason=f"task '{task_type}' is not allowed by sector pack '{pack.id}'",
                review_required=active_policy.require_human_review,
                provider=provider_id,
                model=model,
                metadata=output_metadata,
            )

        if pack.approved_model_tags:
            output_metadata["approved_model_tags"] = list(pack.approved_model_tags)
        output_metadata["output_schema"] = dict(pack.output_schema)
        evidence = tuple(self.evidence_resolver(query)) if self.evidence_resolver else ()
        context = self._context(evidence)
        prompt = query if not context else f"Evidence:\n{context}\n\nQuestion: {query}\nAnswer:"

        try:
            response = self.provider.generate(prompt, system=system, max_new_tokens=512)
        except Exception as exc:  # provider failures become explicit result state
            return InferenceResult(
                status="failed",
                reason=f"provider generation failed: {type(exc).__name__}",
                review_required=active_policy.require_human_review,
                provider=provider_id,
                model=model,
                metadata=self._metadata(metadata, task_type, workspace_id, sector),
            )

        answer = str((response or {}).get("text") or "").strip()
        output_metadata["backend"] = (response or {}).get("backend", "unknown")
        output_metadata["tokens_used"] = (response or {}).get("tokens_used", 0)

        if self.output_validator is not None:
            valid, reason = self.output_validator(answer)
            if not valid:
                return InferenceResult(
                    status="failed",
                    reason=reason or "output schema validation failed",
                    review_required=active_policy.require_human_review,
                    provider=provider_id,
                    model=model,
                    metadata=output_metadata,
                )

        citations = self._citations(evidence)
        assessment = assess_grounding(answer, evidence, citations)
        return decide_inference(
            answer,
            assessment,
            active_policy,
            provider=provider_id,
            model=model,
            metadata=output_metadata,
        )

    @staticmethod
    def _context(evidence: Sequence[EvidenceItem]) -> str:
        return "\n\n".join(
            f"[{item.source_id}/{item.chunk_id}] {item.text}" for item in evidence if item.text
        )

    @staticmethod
    def _citations(evidence: Sequence[EvidenceItem]) -> tuple[Citation, ...]:
        # The first adapter is intentionally conservative: citations point to
        # retrieved chunks and use relevance as a provisional entailment signal.
        # A semantic verifier can replace these scores before production gates.
        return tuple(
            Citation(
                source_id=item.source_id,
                chunk_id=item.chunk_id,
                quote=item.text[:500],
                entailment=item.relevance,
            )
            for item in evidence
        )

    @staticmethod
    def _metadata(
        metadata: Mapping[str, Any] | None,
        task_type: str,
        workspace_id: str | None,
        sector: str | None,
    ) -> dict[str, Any]:
        result = dict(metadata or {})
        result.update(
            {
                "task_type": task_type,
                "workspace_id": workspace_id,
                "sector": sector,
            }
        )
        return result


def json_object_validator(answer: str) -> tuple[bool, str | None]:
    """Validate that a model response is a JSON object."""
    try:
        value = json.loads(answer)
    except (TypeError, ValueError):
        return False, "response must be valid JSON"
    if not isinstance(value, dict):
        return False, "response must be a JSON object"
    return True, None


__all__ = ["EnterpriseInferencePipeline", "json_object_validator"]
