# AEON OS — External Assurance RFP Brief

> **Status:** Draft for procurement. This document is the request-for-proposal (RFP) package
> for the independent assurance engagements that must precede regulated sales. It does **not**
> make any claim of current certification. See
> [`docs/GOVERNMENT_READINESS_CHECKLIST.md`](GOVERNMENT_READINESS_CHECKLIST.md) for the full
> gap list this RFP responds to.

## 1. Purpose and background

AEON OS is an open-source AI agent orchestration platform (multi-tenant workspaces, LLM
routing, RAG knowledge bases, workflow/automation builder, plugin marketplace, MCP support,
model registry, and compliance tooling). The product is currently positioned as
**pilot-ready, not certified** — this RFP procures the independent evidence required before
representing it as production-ready for regulated industries (government, healthcare,
financial services).

The following engagements are being procured as separate work packages so they can be
awarded independently and sequenced against revenue:

| WP | Engagement | Driver | Target timeline |
| --- | --- | --- | --- |
| WP1 | Independent penetration test (pre-pilot + annual) | SOC 2, ISO 27001, FedRAMP, PCI DSS, customer security reviews | T+0 (start immediately) |
| WP2 | SOC 2 Type II audit-readiness + Type II audit | Commercial prerequisites, FedRAMP readiness input | T+1–3 months |
| WP3 | FedRAMP readiness assessment + 3PAO assessment | US federal / state procurement | T+6–12 months |
| WP4 | ISO/IEC 27001 certification audit (Stage 1 + Stage 2) | International / state requirements | T+3–6 months |
| WP5 (optional) | HIPAA security assessment + BAA support; PCI DSS scope determination | Healthcare / card data targets | T+6 months |

## 2. Product technology stack (for scope understanding)

- **Backend:** Python 3.11, Flask, SQLAlchemy/PostgreSQL, Celery + Redis (workers), JWT + API-key auth, OIDC/SAML SSO adapter, Prometheus metrics, Flask SIEM/audit endpoints.
- **Frontend:** Next.js/React web dashboard.
- **AI layer:** multi-provider LLM gateway (OpenAI-compatible, Ollama, vLLM, OpenRouter, private gateways), RAG pipeline, per-sector operating profiles, model registry with eval evidence, sector eval harness.
- **Integrations:** plugin marketplace, MCP server/client, outbound webhooks, Stripe billing, Supabase (optional auth/storage), Docker Compose deployment.
- **Evidence tooling:** hash-chained audit ledger, SBOM generator, DR-drill harness (RTO/RPO), threat model, control matrix, IdP interoperability harness.

## 3. WP1 — Independent penetration test

### 3.1 Objectives
Independently verify the security claims of the threat model
([`docs/security/THREAT_MODEL.md`](security/THREAT_MODEL.md)) against a live staging
deployment, and produce a findings report that maps every issue to a control in
[`docs/compliance/CONTROL_MATRIX.md`](compliance/CONTROL_MATRIX.md).

### 3.2 Mandatory scope (must cover, at minimum)
1. **Prompt injection** over chat, RAG, plugin tool descriptions, MCP schemas, and automation templates (including indirect injection).
2. **Tenant isolation:** workspace-ID traversal, agent-key forgery, cache-key collisions, storage-prefix confusion, export leakage.
3. **SSRF:** custom LLM endpoints, integration proxy, webhook deliveries, redirects, DNS rebinding, cloud metadata endpoints.
4. **Data exfiltration:** history, audit, logs, SDK error output, outbound webhooks, provider request payloads.
5. **Authentication:** JWT/API-key/SSO token handling, replay, rotation, revocation, RBAC bypass, admin abuse.
6. **Automations:** approval bypass, dry-run escape, action-chain injection, sub-automation recursion abuse.
7. **Denial of service:** rate limiting, payload-size limits, queue exhaustion, LLM cost abuse.
8. **Supply chain:** dependency advisories, build provenance, secret scanning.

### 3.3 Environment and rules of engagement
- Test target: one isolated staging deployment (Docker Compose, PostgreSQL) with seeded demo workspaces, provided under credentials escrow.
- Authorized techniques: application-level black/grey box on the staging environment, including authenticated testing.
- Prohibited: destructive actions against production, social engineering, third-party provider abuse beyond configured test endpoints.
- Timing: testing windows agreed in advance; a dry-run against the API contract docs is provided on day one.

### 3.4 Deliverables
- Executive summary with risk-ranked findings (Critical/High/Medium/Low).
- Per-finding: reproduction steps, evidence, CVSS vector, affected control ID (from the control matrix), and a recommended remediation.
- Remediation support: one re-test pass within 60 days of fix delivery.
- Retest evidence retained for the assurance ledger.

## 4. WP2 — SOC 2 Type II

- **Firm requirements:** licensed CPA firm with SOC 2 attestation practice and FedRAMP familiarity.
- **Scope:** trust services criteria (security; availability and confidentiality as optional additions per commercial demand).
- **Phases:** (a) readiness gap assessment with remediation support; (b) Type II examination over a 3–6 month period; (c) final report of independent accountants.
- **Deliverables:** gap report, remediation plan, Type II attestation report, control documentation (leveraging the existing control matrix).

## 5. WP3 — FedRAMP readiness + 3PAO assessment

- **Accreditation required:** the assessor must be a **FedRAMP-accredited 3PAO**; the agency/JAB authorization itself is issued by the government, not by the vendor or its assessor.
- **Phases:** (a) readiness assessment against the FedRAMP baseline (Low → Moderate) with an SSP/POA&M workplan; (b) gap remediation support; (c) the 3PAO security assessment report and penetration test under 3PAO rules.
- **Deliverables:** readiness report, system security plan (SSP) inputs, POA&M, 3PAO assessment report, and the continuous monitoring plan.
- **Note for bidders:** the current baseline is self-hosted/on-prem capable; FedRAMP requires authorized cloud infrastructure (a FedRAMP-authorized CSP boundary) as a precondition.

## 6. WP4 — ISO/IEC 27001 certification (optional)

- **Body requirements:** accredited certification body (e.g., ANAB-accredited), Stage 1 (documentation) and Stage 2 (implementation) audits.
- **Scope:** AEON OS platform + the organization's ISMS (policies already drafted in [`docs/policies/`](policies/)).

## 7. WP5 — HIPAA / PCI (optional, per go-to-market)

- **HIPAA:** security assessment against the Security Rule + BAA support (template exists at [`docs/compliance/BAAS_TEMPLATE.md`](compliance/BAAS_TEMPLATE.md)).
- **PCI DSS:** scope determination / QSA or SAQ path, only if cardholder data will be in scope.

## 8. Vendor qualifications (all WPs)

- WP1: minimum 5 years application-security testing; testers holding OSCP/OSCE/CREST or equivalent; prior AI/LLM application testing experience preferred (prompt-injection and tenant-isolation experience required).
- WP2: licensed CPA firm, SOC 2 attestation practice, three relevant references.
- WP3: current **FedRAMP 3PAO accreditation**, government-focused assessment team, no conflicts of interest with the product.
- WP4: accredited ISO 27001 certification body.
- All: independence from AEON OS development; no financial interest in the product; liability insurance (cyber); signed NDA and data-handling addendum.

## 9. Budget and schedule framework

Indicative ranges from the readiness checklist; final pricing is part of the proposal:

| Engagement | Cost range | Duration |
| --- | --- | --- |
| WP1 Pen test (pre-pilot + retest) | $30k–$150k | 2–4 weeks |
| WP2 SOC 2 Type II (readiness + exam) | $30k–$120k | 4–9 months |
| WP3 FedRAMP (readiness + 3PAO) | $150k–$500k+ | 9–18 months |
| WP4 ISO 27001 | $20k–$80k | 6–12 months |
| WP5 HIPAA / PCI (each) | $20k–$60k | 3–6 months |

## 10. Proposal requirements

Each bidder must submit:
1. Company profile, accreditations, and relevant certifications.
2. Proposed team with named testers/auditors and credentials.
3. Methodology aligned to the scope sections above (including the 8-point pen-test scope).
4. Firm fixed-price or capped pricing per deliverable, with optional-year pricing for annual pen tests.
5. Timeline and staffing plan.
6. Two references for engagements of similar scope in the last 24 months.
7. Signed NDA and any conflict-of-interest disclosure.

## 11. Evaluation criteria

| Criterion | Weight |
| --- | --- |
| Scope coverage and methodology | 30% |
| Relevant experience (AI/LLM, multi-tenant SaaS, regulated sectors) | 25% |
| Team credentials | 15% |
| Price | 15% |
| Timeline and availability | 10% |
| References | 5% |

## 12. Contact and process

- Responses to be submitted as a single PDF per work package.
- Questions will be answered within 5 business days; shortlisted vendors will receive the full technical package (threat model, control matrix, architecture description, staging-environment access plan).
- Award is subject to negotiation; engagements may be phased and tied to customer pilot revenue.
