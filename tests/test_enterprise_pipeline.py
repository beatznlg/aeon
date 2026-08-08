from aeon_enterprise_pipeline import EnterpriseInferencePipeline, json_object_validator
from aeon_inference import EvidenceItem, InferencePolicy


class FakeProvider:
    def __init__(self, text="supported answer"):
        self.text = text
        self.calls = []

    def generate(self, prompt, system=None, max_new_tokens=512):
        self.calls.append((prompt, system, max_new_tokens))
        return {"text": self.text, "backend": "fake:model", "tokens_used": 4}


def test_pipeline_abstains_when_strict_policy_has_no_evidence():
    provider = FakeProvider()
    result = EnterpriseInferencePipeline(provider).run(
        "What is the approved process?",
        policy=InferencePolicy(require_grounding=True, min_retrieval_score=0.8),
        workspace_id="ws-1",
    )
    assert result.status == "abstained"
    assert provider.calls


def test_pipeline_retrieves_context_and_returns_auditable_answer():
    provider = FakeProvider()
    pipeline = EnterpriseInferencePipeline(
        provider,
        evidence_resolver=lambda query: [
            EvidenceItem("policy", "chunk-1", "The approved process is documented.", relevance=0.95)
        ],
    )
    result = pipeline.run(
        "What is the approved process?",
        policy=InferencePolicy(
            require_grounding=True,
            min_retrieval_score=0.8,
            min_groundedness_score=0.8,
            min_citation_coverage=1.0,
            require_citations=True,
        ),
        task_type="policy_qa",
        workspace_id="ws-1",
        sector="government",
    )
    assert result.status == "answered"
    assert result.evidence is not None
    assert result.evidence.citations[0].source_id == "policy"
    assert result.metadata["task_type"] == "policy_qa"
    assert "Evidence:" in provider.calls[0][0]


def test_json_object_validator():
    assert json_object_validator('{"answer": "ok"}') == (True, None)
    assert json_object_validator("not-json")[0] is False
    assert json_object_validator("[]")[0] is False


def test_sector_pack_supplies_strict_policy_and_review_state():
    provider = FakeProvider()
    pipeline = EnterpriseInferencePipeline(
        provider,
        evidence_resolver=lambda query: [
            EvidenceItem("clinical-policy", "chunk-1", "Use the approved documentation workflow.", relevance=0.95)
        ],
    )
    result = pipeline.run(
        "How should this be documented?",
        task_type="clinical_documentation",
        sector_pack_id="healthcare-us-provider",
        workspace_id="health-ws",
    )
    assert result.status == "pending_human_approval"
    assert result.review_required is True
    assert result.metadata["sector_pack_id"] == "healthcare-us-provider"
    assert result.metadata["risk_level"] == "high"


def test_sector_pack_blocks_disallowed_autonomous_task_before_generation():
    provider = FakeProvider()
    result = EnterpriseInferencePipeline(provider).run(
        "Diagnose the patient autonomously.",
        task_type="autonomous_diagnosis",
        sector="health",
        workspace_id="health-ws",
    )
    assert result.status == "blocked_by_policy"
    assert "not allowed" in (result.reason or "")
    assert provider.calls == []
    assert result.metadata["sector_pack_id"] == "healthcare-us-provider"


def test_unknown_sector_falls_back_to_general_pack():
    provider = FakeProvider()
    result = EnterpriseInferencePipeline(provider).run(
        "Summarize the request.",
        task_type="general",
        sector="unknown-sector",
    )
    assert result.status == "answered"
    assert result.metadata["sector_pack_id"] == "general-business"


def test_explicit_policy_can_override_pack_defaults_but_not_task_blocklist():
    provider = FakeProvider()
    result = EnterpriseInferencePipeline(provider).run(
        "Draft a report.",
        task_type="report_draft",
        sector_pack_id="financial-services-global",
        policy=InferencePolicy(),
    )
    assert result.status == "answered"
    assert result.review_required is False

    blocked = EnterpriseInferencePipeline(provider).run(
        "Approve credit autonomously.",
        task_type="autonomous_credit_decision",
        sector_pack_id="financial-services-global",
        policy=InferencePolicy(),
    )
    assert blocked.status == "blocked_by_policy"
