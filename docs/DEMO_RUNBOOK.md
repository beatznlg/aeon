# AEON OS — Demo Runbook (company & government briefings)

**Framing that must stay true in every demo**: AEON is an enterprise AI
orchestration platform with configurable governance, tenant isolation, human
approvals, auditability, and deployment-readiness controls **for pilots and
controlled assessments**. It is NOT certified (FedRAMP, HIPAA, PCI DSS,
CJIS, SOC 2). Never claim certification (see docs/COMPLIANCE_READINESS.md).

## 1. Pre-demo checklist (run the day before)

1. `python3 -m pytest tests -q` — all green (record the count).
2. `python3 scripts/sbom_report.py --out scripts/output/sbom.json` — SBOM present.
3. `python3 scripts/dr_drill.py --workspace-id demo --mode simulate --out scripts/output/dr_report.json` — evidence report.
4. `bandit -c bandit.yaml -r aeon*.py` and `pip-audit -r requirements.txt -r requirements-dev.txt --desc` — clean.
5. Seed an admin, create 2 demo workspaces (acme-health, gov-city) with distinct LLM preferences.
6. Configure providers: OpenAI/Anthropic (if keys), plus a **custom OpenAI-compatible** endpoint and a local stub, to demo provider/model switching live.
7. Verify `/health`, `/live`, `/ready`, `/metrics` respond; check `/audit/integrity` reports a verified chain.
8. Dry-run each scripted scenario below so timing is predictable.

## 2. The 15-minute arc (companies)

1. **Landing**: show the dashboard — workspaces, automations, approvals, capabilities.
2. **Multi-LLM control**: open `/llm`; switch provider and model per workspace and chat — demonstrate that two tenants run different models without cross-talk (provider isolation).
3. **RAG**: upload a document, ask a question, show grounded citations.
4. **Workflows + automations**: run a workflow; trigger an automation; show the execution history and metrics.
5. **Human-in-the-loop**: show a pending approval in `/os/approvals`, approve it, and show the deferred action executing.
6. **Marketplace + MCP**: install a plugin, connect an MCP server, invoke a tool from the chat.
7. **Governance**: show the compliance profile page, `/ready`, the audit chain integrity check, and SSO/SCIM config (redacted).
8. **Close with evidence**: SBOM, load/SLO report, DR drill report — and the honest certification status.

## 3. Sector scenarios (scripted)

- **Healthcare**: diagnostics module — show mandatory human review + BAA profile declaration; explicitly state this is demo data, not clinical advice.
- **Finance**: fraud/credit modules — show risk scoring with human approval gates; state no autonomous lending/credit decisions.
- **Government**: citizen-services workspace — show RBAC, SSO, immutable audit, readiness gate; state CJIS/FedRAMP require agency processes.
- **Manufacturing**: maintenance/logistics modules with automation condition engine (run_if, thresholds).
- **Retail**: inventory/forecast with parallel action branches.
- **Cybersecurity**: threats/vulnerabilities feeds through SIEM integration.

Each scenario: pre-seed data, walk one workflow, show audit trail entries, and hand over the demo runbook appendix for their security team.

## 4. What NOT to claim

- No certification or ATO (FedRAMP, HIPAA, PCI, CJIS, ISO, SOC 2) — the repo docs say this explicitly and buyers verify.
- No autonomous high-impact decisions (diagnosis, credit, fraud, OT control, law enforcement) without customer-approved human review and model-risk process.
- No guarantee of a finished pen test — the threat model + automated controls exist; independent engagement is the documented next step.

## 5. Live demo risk notes

- Provider/model selection is request-local per workspace (fixed and regression-tested); tenants cannot leak model choice.
- Cross-tenant requests to workspace routes return 403 (regression-tested).
- Audit metadata is PII/secret-redacted before persistence (regression-tested).
- If a live LLM key is unavailable, fall back to the stub/custom provider path — the demo still works.

## 6. Handout appendix for security teams

- docs/security/THREAT_MODEL.md — threat model + pen-test scope checklist.
- docs/security/IDP_INTEROP_MATRIX.md — IdP interop evidence matrix.
- docs/compliance/CONTROL_MATRIX.md and docs/compliance/SSP_SKELETON.md.
- docs/policies/INCIDENT_RESPONSE.md, ACCESS_REVIEW.md, RETENTION.md, SUPPORT.md.
- scripts/output/ artifacts: sbom.json, slo_report.md, dr_report.json.
