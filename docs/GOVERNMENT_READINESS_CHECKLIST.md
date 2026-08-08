# AEON OS — Government Readiness Gap Checklist

**Status: engineering evidence is in place; certifications, agreements, and
organizational processes are NOT.** This checklist is the exact list of what
remains before AEON can be **sold** into government (pilots and controlled
assessments are possible now — see `docs/DEMO_RUNBOOK.md`).

**Machine-readable companion**: the same 40 items are emitted as an
SBOM-style JSON document for procurement tooling by
`python scripts/government_readiness_report.py --out scripts/output/government_readiness.json`
(`bomFormat: AEON-GovReadiness`, one `components` entry per control with
status/owner/cost/requirement properties, plus per-category and overall
rollups).

Legend: **[BLOCKING]** = no path to a paid regulated deployment without it ·
**[PARTIAL]** = repo tooling/docs exist, external evidence or process missing ·
**[GAP]** = nothing exists yet.

---

## 1. Certifications & authorizations

| # | Item | Why it is required | Owner | Est. cost / time | Status |
|---|---|---|---|---|---|
| 1.1 | **FedRAMP authorization** (Low → Moderate → High) | Required for most US federal SaaS procurement; only a 3PAO assessment + agency/JAB authorization can issue it — no repo can | External 3PAO + FedRAMP program | $150k–$500k+ / 9–18 months | **[BLOCKING]** |
| 1.2 | **SOC 2 Type II** (trust services criteria) | Commercial prerequisite and de-facto FedRAMP readiness input; independent auditor opinion | External CPA firm | $30k–$120k / 4–9 months | **[BLOCKING]** for enterprise deals |
| 1.3 | **ISO/IEC 27001 certification** | Common international/state requirement; certification body audit | Certification body | $20k–$80k / 6–12 months | **[GAP]** |
| 1.4 | **StateRAMP / Texas RAMP** | State-level FedRAMP-equivalent for US state/local procurement | 3PAO + state program | $30k–$150k / 6–12 months | **[GAP]** |
| 1.5 | **CMMC Level 2** (if DoD supply chain) | Required to hold CUI from DoD primes | C3PAO assessment | $50k–$200k / 6–12 months | **[GAP]** (not applicable unless DoD is a target) |
| 1.6 | **NIST SP 800-171 / DFARS 252.204-7012** | DoD CUI handling; self-assessment + eventual CMMC | Internal + C3PAO | Variable | **[GAP]** (DoD only) |
| 1.7 | **HIPAA compliance posture + BAA** | If any covered entity / PHI (healthcare agencies, VA-adjacent) | Legal + security | Ongoing | **[PARTIAL]** — `docs/compliance/BAAS_TEMPLATE.md` + healthcare compliance profile exist; executed BAA + controls evidence do not |
| 1.8 | **CJIS approval** (law-enforcement/criminal justice) | Requires FBI CJIS Security Policy, **state/agency agreements**, personnel vetting, and an authorized boundary — explicitly not grantable by app features | Agency + state CJIS units | Variable, per state | **[BLOCKING]** for LE demos; `docs/security/IDP_INTEROP_MATRIX.md` covers the PIV/CAC identity piece only |
| 1.9 | **PCI DSS** (if card data in scope) | Only if AEON ever processes/transmits cardholder data | QSA | $20k–$60k / 3–6 months | **[GAP]** — not in scope unless finance module holds PAN data |
| 1.10 | **Section 508 / WCAG 2.1 AA accessibility conformance** | Federal procurement requirement for IT products | UX + testers | $15k–$50k | **[GAP]** |

## 2. Agreements & contracts

| # | Item | Why it is required | Owner | Status |
|---|---|---|---|---|
| 2.1 | **Business Associate Agreement (BAA)** signed per customer | HIPAA; template exists, executed agreements do not | Legal | **[PARTIAL]** |
| 2.2 | **CJIS security addendum + state agreements** | CJIS requires agency/state agreements + personnel policies; no app feature can grant | Legal + agency | **[BLOCKING]** (LE) |
| 2.3 | **FedRAMP agency authorization agreement** (if Agency ATO path) | Authorizing agency must accept the package | Agency CIO/CISO | **[BLOCKING]** |
| 2.4 | **Data use / data processing agreements** per state | State-specific privacy and records requirements | Legal | **[GAP]** |
| 2.5 | **FAR/DFARS clauses + TAA (Trade Agreements Act) compliance** | Federal contract boilerplate; affects source-of-manufacture of infrastructure | Legal + supply chain | **[GAP]** |
| 2.6 | **Pilot MOUs / NDAs** | First agency engagements should be structured pilots, not procurement | BD + Legal | **[GAP]** (fastest to close) |

## 3. Organizational & operational processes (docs exist — must be operationalized with evidence)

| # | Item | Why it is required | Owner | Status |
|---|---|---|---|---|
| 3.1 | **Incident response exercised**, with measured detection/containment times and evidence in the assurance ledger | Docs exist (`docs/policies/INCIDENT_RESPONSE.md`); auditors require executed drills + records | Security lead | **[PARTIAL]** |
| 3.2 | **Recurring access reviews** on a published cadence with records | `docs/policies/ACCESS_REVIEW.md` exists; recurring execution + sign-off does not | Security lead | **[PARTIAL]** |
| 3.3 | **Enforced retention & legal hold** schedules | `docs/policies/RETENTION.md` exists; automated enforcement + hold process in the production boundary does not | Legal + Ops | **[PARTIAL]** |
| 3.4 | **Support/SLA process** — severity tiers, response targets, 24×7 coverage where contracted | `docs/policies/SUPPORT.md` exists; staffing + SLAs do not | Ops | **[PARTIAL]** |
| 3.5 | **Change management & release process** for the ATO boundary | Auditors need evidence of controlled change | Engineering | **[PARTIAL]** — CI gate exists; formal CAB/change records do not |
| 3.6 | **Vulnerability management program** — scheduled scans, triage SLAs, remediation tracking | Bandit/pip-audit run per commit; continuous program + reporting does not | Security | **[PARTIAL]** |
| 3.7 | **Independent penetration testing** (annual minimum, plus pre-pilot) | `docs/security/THREAT_MODEL.md` defines scope; an external firm's report is required | External firm | **[BLOCKING]** for enterprise/government |
| 3.8 | **Business continuity / DR program** — scheduled drills with measured RTO/RPO and recovery evidence | `scripts/dr_drill.py` + CI evidence exist; scheduled drills in the production boundary do not | Ops | **[PARTIAL]** |
| 3.9 | **Privacy program** — PIA/SORN inputs, privacy notices, data-subject handling | Privacy office + legal | **[GAP]** |

## 4. Personnel & identity

| # | Item | Why it is required | Owner | Status |
|---|---|---|---|---|
| 4.1 | **Background checks** per agency requirements (incl. CJIS fingerprinting where applicable) | Personnel vetting is a CJIS/fed prerequisite | HR | **[GAP]** |
| 4.2 | **PIV/CAC issuance** for staff who will access federal-facing environments | HSPD-12; identity for operator/admin access | Security/HR | **[GAP]** |
| 4.3 | **Annual role-based security awareness training** with records | Audit evidence | HR/Security | **[GAP]** |
| 4.4 | **Privileged-access controls** — MFA everywhere, break-glass, least privilege, two-person rule where required | Control evidence for audits | Security | **[PARTIAL]** — RBAC/MFA primitives exist; formal privileged-access program does not |

## 5. Technical items that need an external environment (not repo code)

| # | Item | Why it is required | Owner | Status |
|---|---|---|---|---|
| 5.1 | **FedRAMP-authorized hosting** (CSP with its own FedRAMP authorization) with documented data residency | FedRAMP requires authorized infrastructure; current self-host path is not assessed | Hosting/Cloud | **[BLOCKING]** |
| 5.2 | **KMS/HSM-managed secrets** with key rotation procedures and key-usage audit | Secrets are env-config today; regulated deployments require managed keys | Security/Infra | **[PARTIAL]** |
| 5.3 | **Live IdP tenants** — Entra ID, Okta, and PIV/CAC integration verified against real tenants | `tests/test_sso_interop.py` + `docs/security/IDP_INTEROP_MATRIX.md` exist; live-tenant verification does not | Security | **[PARTIAL]** |
| 5.4 | **SIEM/SOC ingestion in production** with 24×7 monitoring and defined alert SLAs | `aeon_siem.py` + audit exports exist; operating SOC does not | SOC/Provider | **[PARTIAL]** |
| 5.5 | **Backup/restore + DR validated in the production boundary**, retention enforced, tested per 3.8 | Scripts + models exist; boundary validation does not | Ops | **[PARTIAL]** |
| 5.6 | **SBOM attestation practice** — signed SBOMs, vulnerability-response SLA, CISA-aligned reporting | `scripts/sbom_report.py` + CI artifact exist; signing + attestation practice does not | Security | **[PARTIAL]** |

## 6. Procurement readiness (company-level)

| # | Item | Why it is required | Owner | Status |
|---|---|---|---|---|
| 6.1 | **SAM.gov registration, UEI, CAGE code** | Required to sell to US federal entities | BD | **[GAP]** |
| 6.2 | **Security contact + reps & certs** in SAM.gov | Federal requirement | BD | **[GAP]** |
| 6.3 | **Pricing vehicles** — GSA schedule, state contracts, or approved catalog pricing | Procurement path for agencies | BD | **[GAP]** |
| 6.4 | **Incident reporting procedures to CISA/US-CERT** and per-contract notification | FedRAMP/contractual requirement | Security | **[GAP]** |
| 6.5 | **Records management** — NARA-aligned retention of government records | FedRAMP control family + contract terms | Legal/Records | **[GAP]** |

---

## What the repo already provides (do not re-buy)

- Deployment readiness profiles + evidence gate: `docs/COMPLIANCE_READINESS.md`
- Controls matrix + SSP skeleton + BAA template: `docs/compliance/CONTROL_MATRIX.md`, `docs/compliance/SSP_SKELETON.md`, `docs/compliance/BAAS_TEMPLATE.md`
- Threat model + pen-test scope: `docs/security/THREAT_MODEL.md`
- IdP interop matrix + harness (Entra/Okta/PIV-CAC): `docs/security/IDP_INTEROP_MATRIX.md` + `tests/test_sso_interop.py`
- Procedures: `docs/policies/{INCIDENT_RESPONSE,ACCESS_REVIEW,RETENTION,SUPPORT}.md`
- Evidence tooling: SBOM (`scripts/sbom_report.py`), DR drill (`scripts/dr_drill.py`), assurance ledger, hash-chained audit chain, model registry, CI quality gate
- Honest sales language: `docs/COMPLIANCE_READINESS.md` → *Sales language*; `docs/DEMO_RUNBOOK.md` → *What NOT to claim*

## Fastest path to a first paid pilot (without full certification)

1. Sign a **pilot MOU/NDA** (2.6) — days.
2. Stand up **production-grade hosting + KMS + real IdP tenant** (5.1–5.3) — 2–4 weeks of infrastructure work.
3. Commission an **independent pen test** scoped from `docs/security/THREAT_MODEL.md` (3.7) — 2–4 weeks.
4. Run **SOC 2 Type II** (1.2) in parallel — 4–9 months, unlocks commercial enterprise deals and feeds FedRAMP.
5. Enter **FedRAMP** (1.1) once SOC 2 evidence + production boundary are stable — 9–18 months, with the SSP skeleton as the starting package.
6. Close **SAM.gov + UEI + CAGE** (6.1–6.2) the day you decide federal is a channel — hours, done by BD.
