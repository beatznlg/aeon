# AEON OS — Sector & Industry Fine-Tuning Playbook

**Status: engineering playbook for reaching company-grade, sector-accurate LLM
output. This document is a process and control guide, not a certification, and
it does not grant clinical, financial, legal, or regulatory sign-off.** It pairs
with `docs/OPERATING_PROFILES.md`, `docs/COMPLIANCE_READINESS.md`,
`docs/security/THREAT_MODEL.md`, and `docs/DEMO_RUNBOOK.md`.

---

## 1. The honest framing

There is no configuration that makes an LLM "100% precise, zero errors" in a
sector. What enterprise and government buyers actually purchase is a **measured
accuracy contract**: a system whose errors are (a) rare, (b) caught before they
reach a decision, and (c) auditable when they happen.

AEON delivers that contract by combining five engineered layers:

1. **Grounding** — answers must cite evidence and meet minimum retrieval /
   groundedness / citation thresholds before they are released.
2. **Policy gates** — sector packs decide what tasks are allowed, which models
   are approved, and when a human must review.
3. **Evaluation** — a repeatable per-sector benchmark (`scripts/sector_eval.py`)
   that turns "is the model good?" into a number with a pass/fail gate.
4. **Adaptation** — prompt/system design, retrieval tuning, then fine-tuning
   (LoRA/QLoRA) only when cheaper rungs are exhausted.
5. **Oversight** — human review, audit trail, drift monitoring, and rollback.

Everything below maps to code that already exists in this repository.

---

## 2. What AEON already enforces at runtime

### 2.1 Sector packs (`aeon_sector_packs.py`)

Each `SectorPack` declares an `InferencePolicy` with fail-closed thresholds:

| Pack | Sector | Risk | Grounding | Min retrieval | Min groundedness | Citations (coverage) | Human review |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `general-business` | general | low | optional | — | — | — | no |
| `healthcare-us-provider` | health | high | required | 0.78 | 0.90 | required (1.0) | yes |
| `financial-services-global` | finance | high | required | 0.78 | 0.90 | required (1.0) | yes |
| `government-public-sector` | government | high | required | 0.78 | 0.90 | required (1.0) | yes |
| `defense-secure` | defense | critical | required | 0.78 | 0.90 | required (1.0) | yes |
| `critical-infrastructure` | utilities | critical | required | 0.78 | 0.90 | required (1.0) | yes |
| `manufacturing-enterprise` | manufacturing | high | required | 0.78 | 0.90 | required (1.0) | yes |

Packs also carry `allowed_task_types` / `blocked_task_types` (e.g. healthcare
blocks `autonomous_diagnosis`), `approved_model_tags` (e.g. `air_gapped`,
`private`, `grounded`), an `output_schema`, and jurisdiction notes.

### 2.2 The inference pipeline (`aeon_inference.py`, `aeon_enterprise_pipeline.py`)

`EnterpriseInferencePipeline.run(...)` executes one request through explicit
quality boundaries:

```text
query ──► sector pack resolution (get_sector_pack)
        ├─► task_allowed?          ── no  ──► status=blocked_by_policy
        ├─► evidence retrieval     (EvidenceItem: relevance, authority, freshness)
        ├─► provider generate      (request-local provider/model, no global state)
        ├─► output schema validator
        ├─► assess_grounding       (retrieval_score, groundedness_score,
        │                           citation_coverage, contradictions)
        └─► decide_inference       ── fail ──► status=abstained (fail-closed)
                                   ── pass ──► status=answered | pending_human_approval
```

Result statuses are stable and auditable: `answered`, `pending_human_approval`,
`abstained`, `blocked_by_policy`, `needs_more_information`, `failed`. Confidence
is the mean of retrieval + groundedness + citation coverage.

**This is your accuracy enforcement.** Fine-tuning only improves the generator
inside this pipeline; it never bypasses the gates.

---

## 3. The accuracy ladder (climb only as far as you must)

| Rung | Technique | When it's enough | Cost | Risk |
| --- | --- | --- | --- | --- |
| 0 | System prompt + output schema | General business, drafting, summaries | ~0 | low |
| 1 | Few-shot exemplars (sector-native) | Format-heavy tasks, extraction | ~0 | low |
| 2 | RAG grounding + citations | Any task where the answer must be true to your data | low | low |
| 3 | Retrieval tuning (chunking, rerank, hybrid search) | When answers are *correct but retrieved evidence is weak* | low-mid | low |
| 4 | Domain adapters (sector packs, validators) | Enforcing sector vocabulary, tone, schema, policy | low | low |
| 5 | Fine-tuning (LoRA/QLoRA) | Tasks with a stable, verifiable answer distribution that RAG cannot satisfy | mid | medium |
| 6 | Preference tuning (DPO/RLHF) | When the failure is *style/compliance judgement*, not fact | high | high |
| 7 | Routing / ensembles | Mixing a cheap local model with a frontier model per task | mid | low |

**Decision rule:** for every task type, run the evaluation harness at the current
rung. If the gate passes, stop. If it fails and the failure is factual, move up
rungs 2–3 first (retrieval, not weights). Only reach for fine-tuning when the
remaining errors are *systematic, verifiable, and stable* — i.e. the same input
shape keeps failing the same way.

**Why RAG-first matters:** fine-tuned weights cannot cite their sources. In
regulated sectors, "the model was right" is not enough — *where did it come
from?* is the question. Grounding answers that question; weights don't.

---

## 4. Per-sector playbooks

Each card: the target outcome, the model posture, the adaptation strategy, and
the eval gates you must pass before a pilot.

### 4.1 General Business (`general-business`)

- **Posture:** any hosted or local provider; broadest model choice.
- **Strategy:** rungs 0–2. Schema-enforced answers, light RAG for company docs.
- **Fine-tuning:** rarely needed; consider small LoRA for *brand voice* or
  *proprietary terminology* only after eval shows systematic style errors.
- **Eval gate:** accuracy ≥ 0.90 on the business QA set; abstain rate ≤ 0.05.

### 4.2 Healthcare (`healthcare-us-provider`, US jurisdiction)

- **Posture:** private/hosted with BAA, or on-prem; `approved_model_tags`:
  `private`, `healthcare`, `grounded`.
- **Strategy:** rungs 2–5. Grounding is mandatory (min retrieval 0.78,
  groundedness 0.90, citations 1.0). Tasks: `retrieval_qa`, `summarization`,
  `clinical_documentation`. Never `autonomous_diagnosis`.
- **Fine-tuning:** LoRA on a de-identified clinical corpus (ICD/LOINC/specialty
  notes) **only** to reduce terminology drift; every fine-tuned answer still
  passes the grounding gates. Human review is mandatory by policy.
- **Data notes:** use `aeon_sector_data_gen.py` / `aeon_seed_sectors.py` for
  demo data; production corpora must be de-identified (HIPAA) and jurisdiction
  checked before they touch a model.
- **Eval gate:** accuracy ≥ 0.95 on the clinical-documentation set; hallucination
  (ungrounded release) rate = 0.0; abstain on any below-threshold evidence.

### 4.3 Financial Services (`financial-services-global`)

- **Posture:** private hosted or on-prem; tags: `private`, `finance`,
  `grounded`, `calculation_verified`.
- **Strategy:** rungs 2–5. Tasks: `retrieval_qa`, `reconciliation`,
  `risk_analysis`, `report_draft`. Never `autonomous_credit_decision` or
  `autonomous_payment`.
- **Fine-tuning:** LoRA on approved policy/regulation documents and
  *calculation templates* (the `calculation_verified` tag implies a deterministic
  arithmetic checker in the output validator — verify sums independently of the
  model). Add a validator that recomputes every number the model emits.
- **Eval gate:** accuracy ≥ 0.95 on the reconciliation set; 100% of numeric
  claims pass the deterministic calculator; citation coverage 1.0.

### 4.4 Government (`government-public-sector`)

- **Posture:** residency-aware, often air-gapped; tags: `private`,
  `government`, `provenance`, `grounded`.
- **Strategy:** rungs 2–4, plus provenance. Tasks: `policy_research`,
  `policy_qa`, `procurement_support`, `records_assistance`, `drafting`. Never
  `autonomous_benefits_decision` or `autonomous_enforcement`.
- **Fine-tuning:** small LoRA on published statute/policy corpora for citation
  format and plain-language drafting conventions. Everything must carry
  provenance (source + version) because FOIA/records requirements demand it.
- **Eval gate:** accuracy ≥ 0.90; every answer cites a real, versioned source
  from the approved corpus; abstain rather than cite unverified material.

### 4.5 Defense (`defense-secure`) and Critical Infrastructure (`critical-infrastructure`)

- **Posture:** air-gapped/edge mandatory; tags include `air_gapped`, `edge`.
  No network egress assumptions. External connectors must be explicitly
  reviewed.
- **Strategy:** rungs 2–4 with the strictest gates. Tasks (defense):
  `logistics_analysis`, `maintenance_support`, `document_retrieval` — read-only
  by default. Tasks (utilities): `maintenance`, `incident_analysis`,
  `forecasting`, `runbook_support`. Never autonomous control/kinetic action.
- **Fine-tuning:** LoRA on locally approved, air-gapped corpora; models deployed
  via local runtimes (Ollama/vLLM through `get_llm_provider`). Human approval
  interlocks are non-negotiable; the pipeline's `pending_human_approval` status
  is the release path.
- **Eval gate:** accuracy ≥ 0.95 on runbook/incident sets; zero ungrounded
  releases; every operational recommendation is review-gated.

### 4.6 Manufacturing (`manufacturing-enterprise`)

- **Posture:** private/edge; tags: `private`, `edge`, `manufacturing`,
  `grounded`.
- **Strategy:** rungs 2–4. Tasks: `quality_analysis`, `maintenance`,
  `root_cause_analysis`, `work_instruction`. Never `autonomous_safety_override`
  or unapproved machine control.
- **Fine-tuning:** LoRA on work-instruction and maintenance histories; combine
  with a schema validator that forces step/part/tool structure in output.
- **Eval gate:** accuracy ≥ 0.90; work instructions validate against the output
  schema 100% of the time.

---

## 5. Data preparation

1. **Sources.** Start from the sector machinery already in the repo:
   `aeon_sectors.py` (catalog), `aeon_seed_sectors.py` (seed data),
   `aeon_sector_data_gen.py` (time-varying demo data), then layer your
   organization's real corpora (policies, manuals, transcripts, tickets).
2. **Synthetic data.** Use the generators to bootstrap demo/QA sets, but never
   train production fine-tunes on unverified synthetic data alone — synthetic
   drift is real. Every synthetic example must be spot-checked by a domain
   expert before it enters the training or eval set.
3. **De-identification.** For health, finance, government, and defense: strip
   PHI/PII/PCI before any data touches a model or leaves the trust boundary.
   AEON's redaction/security layer (`aeon_security.py`) is a runtime control,
   not a substitute for de-identifying training corpora.
4. **Split.** 80/10/10 train/validation/test, split *by source document*, not
   by row, to prevent leakage. Keep the test set frozen and versioned.
5. **Contamination check.** Before eval, verify none of your eval questions
   appear verbatim in any provider's public training corpus claims; keep
   eval-set hashes in the assurance ledger (`scripts/assurance_evidence.py`).
6. **Golden sets.** Maintain a human-reviewed golden set per sector with an
   expert annotation cadence (e.g. quarterly refresh) — this is what keeps the
   "measured accuracy" promise honest over time.

---

## 6. Fine-tuning recipes

Use this only after rungs 0–4 fail the eval gate for a *stable* error class.

| Parameter | Recommendation |
| --- | --- |
| Method | LoRA / QLoRA (rank 16–64) on a strong base (7B–70B depending on task) |
| Base selection | Match the pack tags: `private`/`air_gapped` → local-capable base; otherwise the best frontier model your budget allows |
| Data volume | Start at 1k–5k high-quality examples; scale to 50k only if eval shows monotonic gains |
| Format | Sector-native instruction + expected-output pairs; mirror the `output_schema` of the pack |
| Eval cadence | Before training, every 500 steps on the frozen test set, and after each adapter merge |
| Deployment | Register the adapter version; route via `get_llm_provider` (hosted or local runtime); pin versions |
| Rollback | Never delete the previous adapter; keep the last N registered and auditable |
| Cost | QLoRA on a single GPU is the default starting point; never fine-tune to fix retrieval — fix retrieval |

**Never fine-tune away the guards.** The pack policy, grounding thresholds,
citations, and human-review gates remain active before and after any fine-tune.
A fine-tune that makes the model *assert* instead of *cite* is a regression even
if benchmark accuracy rises.

---

## 7. Evaluation methodology

### 7.1 The harness

`scripts/sector_eval.py` runs a per-sector QA benchmark through the **real**
`EnterpriseInferencePipeline` (sector pack → policy → grounding → decide). Two
modes:

- `--stub` — deterministic offline provider; used in CI and demos with no keys.
- `--provider <name> --model <model>` — live provider via `get_llm_provider`.

```bash
# offline evidence run (CI-safe)
python scripts/sector_eval.py --sector finance --stub \
    --out scripts/output/sector_eval_finance.json

# live gate run against a real model
python scripts/sector_eval.py --questions scripts/eval_sets/sample_sector_eval.json \
    --provider openai --model gpt-4o --min-accuracy 0.85 \
    --out scripts/output/sector_eval_live.json
```

The harness exits non-zero when `--min-accuracy` is not met, so it can gate CI.

### 7.2 Metrics that matter

| Metric | Definition | Target (by risk) |
| --- | --- | --- |
| Accuracy (pass@expected) | fraction of items where all expected content appears in a released answer (`answered` or `pending_human_approval`) | low ≥ 0.90, high ≥ 0.95, critical ≥ 0.95 |
| Abstain rate | `abstained` / total — the system refusing to answer on weak evidence | low ≤ 0.10, high ≤ 0.05, critical ≤ 0.05 |
| Hallucination rate | released answers that fail grounding gates / total | **0.0 at high/critical** |
| Citation coverage | mean `citation_coverage` on released answers | 1.0 at high/critical |
| Mean confidence | mean of the pipeline's confidence score | record, trend it |
| Human-review rate | `pending_human_approval` share | expected at high/critical; track cost |
| Blocked rate | `blocked_by_policy` — guardrails firing | > 0 proves the guardrails work; trend down over time |

### 7.3 Release gates per risk level

- **Low risk (general):** accuracy gate + abstain cap; no human review required.
- **High risk (health, finance, government, manufacturing):** accuracy ≥ 0.95 on
  the sector golden set, zero ungrounded releases, citations 1.0, and a live
  human-in-the-loop review on every production answer (`pending_human_approval`).
- **Critical (defense, utilities):** everything in high, plus air-gapped eval
  evidence and documented approval interlocks per action class.

### 7.4 Continuous evaluation

Run the harness on every model change and every data refresh; store reports in
`scripts/output/` (git-ignored) and ship them as CI artifacts. Track drift on a
weekly cadence with a frozen golden set. Any gate regression blocks promotion.

---

## 8. Governance, audit, and operations- **Model registry:** `aeon_model_registry.py` records provider, model, adapter version, and eval report hash (SHA-256 fingerprint) for every deployment, with a fail-closed lifecycle (`registered → approved → active → rolled_back`, or → `deprecated`). Workspace admins manage it via `/models/registry` (register / approve / activate / rollback / deprecate / eval); approvals are appended to the assurance ledger. `scripts/sector_eval.py` auto-attaches its fingerprint and metrics to the matching deployment (provider + model + workspace, or `--registry-deployment <id>`; `--registry-required` fails the run if nothing matched), and evidence can also be attached manually with `POST /models/registry/<id>/eval`.
- **Prompt/system versions:** version system prompts with the models they were
  tuned with; a prompt change invalidates eval evidence.
- **Audit trail:** every inference result carries `status`, `confidence`,
  `review_required`, and fingerprint (`result_fingerprint`); wire sector runs to
  `aeon_siem`/tracing so the "who asked, what was answered, on what evidence"
  chain survives an audit.
- **Incidents:** an ungrounded release is an incident — follow
  `docs/policies/INCIDENT_RESPONSE.md`, then fix retrieval or tighten policy,
  never just re-prompt.
- **Residency:** for government/defense, keep eval corpora, adapters, and logs
  inside the same residency boundary as production (`aeon_residency.py`).

---

## 9. What code cannot do (read before any procurement conversation)

- Issue an independent penetration test or SOC 2/ISO 27001/FedRAMP/HIPAA/PCI/CJIS
  certification — those require external assessors and legal/agency agreements.
- Provide clinical, financial, legal, or regulatory sign-off on model output —
  that is a qualified human's decision, which is exactly why the high/critical
  packs force human review.
- Guarantee zero errors — it can only make errors rare, caught, and auditable.

Your honest demo script for this: show the eval harness failing a bad model and
passing a good one, show an `abstained` result on weak evidence, and show a
`pending_human_approval` release path. That is the company-grade story.

---

## 10. Quick-start checklist

1. [ ] Pick a sector; read its pack in `aeon_sector_packs.py`.
2. [ ] Run `python scripts/sector_eval.py --sector <sector> --stub` — confirm the
       harness works offline.
3. [ ] Build the golden set (≥ 100 expert-reviewed items) and split by document.
4. [ ] Run live eval with your candidate model: `--provider ... --model ...`.
5. [ ] If the gate fails: improve retrieval (rungs 2–3) before fine-tuning.
6. [ ] Only then: prepare a de-identified corpus, LoRA-tune, re-run the same gate.
7. [ ] Register the model + eval evidence; set weekly drift monitoring.
8. [ ] Record results in the assurance ledger; keep the honest framing in
       `docs/DEMO_RUNBOOK.md` intact.
