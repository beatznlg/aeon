from aeon_inference import (
    Citation,
    EvidenceItem,
    InferencePolicy,
    assess_grounding,
    decide_inference,
    result_fingerprint,
)


def test_strict_grounding_abstains_without_evidence():
    assessment = assess_grounding("A consequential answer.")
    result = decide_inference(
        "A consequential answer.",
        assessment,
        InferencePolicy(
            require_grounding=True,
            min_retrieval_score=0.8,
            min_groundedness_score=0.9,
            min_citation_coverage=1.0,
            require_citations=True,
        ),
    )
    assert result.status == "abstained"
    assert result.ok is False
    assert "retrieval" in (result.reason or "")


def test_grounded_answer_includes_evidence_and_confidence():
    evidence = [EvidenceItem("policy-1", "chunk-1", "Approved policy text.", relevance=0.95)]
    citations = [Citation("policy-1", "chunk-1", "Approved policy text.", entailment=0.96)]
    assessment = assess_grounding("Approved policy text.", evidence, citations)
    result = decide_inference(
        "Approved policy text.",
        assessment,
        InferencePolicy(
            require_grounding=True,
            min_retrieval_score=0.8,
            min_groundedness_score=0.9,
            min_citation_coverage=1.0,
            require_citations=True,
        ),
        provider="private-gateway",
        model="enterprise-model",
    )
    assert result.status == "answered"
    assert result.ok is True
    assert result.confidence is not None
    assert result.evidence is not None
    assert result.evidence.citations[0].source_id == "policy-1"


def test_high_risk_answer_can_require_human_review():
    evidence = [EvidenceItem("source", "chunk", "Supported claim.", relevance=1.0)]
    citations = [Citation("source", "chunk", "Supported claim.", entailment=1.0)]
    result = decide_inference(
        "Supported claim.",
        assess_grounding("Supported claim.", evidence, citations),
        InferencePolicy(require_grounding=True, require_human_review=True),
    )
    assert result.status == "pending_human_approval"
    assert result.review_required is True
    assert result.ok is False


def test_result_fingerprint_is_stable():
    result = decide_inference(
        "A deterministic answer.",
        assess_grounding("A deterministic answer."),
        InferencePolicy(),
    )
    assert result_fingerprint(result) == result_fingerprint(result)
