# AEON OS Production Readiness

This document describes the current engineering baseline. It does not claim that AEON OS is certified for regulated or government production; certification requires independent assessment and evidence from the target deployment.

## Current baseline

- Multi-tenant workspaces with workspace memberships and role checks.
- JWT access tokens with production secret validation and development-only fallback behavior.
- Workspace-scoped automation approvals, including Slack actions.
- SSO configuration redaction and workspace ownership checks.
- Fernet envelope encryption that fails closed when `cryptography` is unavailable.
- Configurable CORS; wildcard CORS is non-credentialed only. Credentialed CORS requires an explicit origin allowlist.
- Docker backend/frontend images, Postgres, Redis, Celery worker/beat services, health probes, Prometheus metrics, and monitoring configuration.
- Python, TypeScript, SDK, OpenAPI, automation, governance, SSO, SCIM, residency, incident, and disaster-recovery test coverage.
- A hash-chained, non-sensitive assurance evidence ledger with optional external tail anchoring and a CLI release check; this records observations but does not create legal certification.
- A registry-backed sector contract at `/sectors/catalog` covering 58 tools across 16 sectors: cybersecurity, health, finance, retail, transport, manufacturing, tourism, utilities, cultural heritage, SME, telecom, agriculture, education, public safety, real estate, and professional services. Sector reads/writes are authenticated, workspace-scoped, normalized through the cultural-heritage alias, and reject unknown tools or invalid dataset shapes.

## Sector data boundaries

The sector layer is an extensible orchestration and dashboard contract, not a certification of domain outcomes. Generated data is explicitly seed/demo data unless a deployment replaces it with validated customer connectors. The current modules must not be used as autonomous or final decision-makers for diagnosis, treatment, lending, credit, pricing regulated products, critical infrastructure control, law enforcement, or government eligibility decisions.

Before enabling a sector in a customer or government environment, the deployment owner must document the data source, data quality controls, model/version provenance, human-review step, appeal path, retention/deletion policy, access audit trail, incident process, and domain-specific validation. Keep high-impact actions behind policy and human approval workflows, and verify that all tenant-owned connectors and exports preserve workspace isolation.

The supported public identifiers are:

- `cybersecurity`: `threats`, `vulnerabilities`, `compliance`, `ip-reputation`, `news`
- `health`: `diagnostics`, `vitals`, `drug-interactions`, `telehealth`
- `finance`: `risk`, `market`, `fraud`, `credit`, `payments`
- `retail`: `forecast`, `inventory`, `suppliers`, `pricing`
- `transport`: `traffic`, `fleet`, `routes`
- `manufacturing`: `maintenance`, `quality`, `logistics`
- `tourism`: `bookings`, `pricing`, `concierge`, `visitors`
- `utilities`: `resources`, `services`, `waste`, `grid`
- `heritage` (also `cultural_heritage`): `visitors`, `sites`, `exhibitions`, `tours`
- `sme`: `workflows`, `documents`, `support`, `supply-chain`
- `telecom`: `network`, `capacity`, `faults`
- `agriculture`: `yield`, `irrigation`, `pests`
- `education`: `at-risk`, `interventions`, `outcomes`
- `public_safety`: `incidents`, `dispatch`, `briefs`
- `real_estate`: `valuations`, `market`, `comparables`
- `professional`: `legal`, `accounting`, `data-management`

The catalog endpoint is the source of truth for clients and SDK generators; the UI may expose additional presentation-only modules, but those are not backend capabilities until they appear in the catalog.

## Required production configuration

Set these through the deployment platform's secret manager, not in the repository:

- `AEON_ENV=production`
- `AEON_JWT_SECRET` (or `NEXTAUTH_SECRET`) with at least 32 random characters
- `AEON_MASTER_KMS_KEY`; use a KMS/HSM-managed secret in production
- `AEON_DATABASE_URL` pointing to managed PostgreSQL
- `AEON_CORS_ALLOWED_ORIGINS` containing only the production frontend origin(s)
- `AEON_HSTS=true` behind a TLS-terminating proxy
- `AEON_REDIS_URL` for distributed caching/rate limiting and Celery
- A real LLM provider and its secret, if AI generation is enabled
- Stripe, SSO, SCIM, SIEM, object-storage, and webhook credentials only when those modules are enabled

The backend honors the platform-provided `PORT` when `AEON_PYTHON_PORT` is not set. Docker and Railway deployments should use the backend health endpoint at `/health` and the liveness endpoint at `/live`. In a production compliance profile, `/ready` also fails closed when required assurance evidence is missing, failed, or tampered.

## Validation evidence

The repository's latest local validation recorded:

- `pytest -q`: 446 passed
- Python compilation: passed
- Frontend `npx tsc --noEmit`: passed
- Frontend `npm run lint`: passed
- `git diff --check`: passed

Run the complete quality gate before every release, including Bandit, pip-audit, frontend production build, Docker image builds, and deployment smoke tests.

## SLO & load evidence

Two stdlib-only scripts generate point-in-time load and SLO evidence:

- `scripts/loadtest_api.py` — concurrent HTTP load harness. Run it against a
  production-shaped deployment, e.g.:

      AEON_TEST_TOKEN=... python scripts/loadtest_api.py \
          --base-url http://<host>:<port> \
          --concurrency 20 --total 400 \
          --endpoints /health,/metrics,/marketplace/agent-tools \
          --out scripts/output/load_report.json

- `scripts/slo_report.py` — evaluates the report against SLO targets
  (availability, error rate, p50/p95/p99 latency) and renders a markdown
  evidence report:

      python scripts/slo_report.py --report scripts/output/load_report.json \
          --out scripts/output/slo_report.md

SLO targets default to 99.9% availability, ≤0.5% error rate, p50 ≤500 ms,
p95 ≤1500 ms, p99 ≤3000 ms and are overridable in code for contract-specific
SLOs. The evaluation logic (`scripts/slo_report.py:compute_slos`) is covered
by `tests/test_slo.py`. Evidence is point-in-time: rerun per release and retain
reports with the assurance ledger. For high-availability evidence, also run
failover drills (`aeon_dr`) and record RTO/RPO measurements in the evidence
ledger (`scripts/assurance_evidence.py`).

## Remaining evidence before regulated sales

The codebase is a feature-rich enterprise pilot foundation. Before representing it as ready for unrestricted commercial, healthcare, financial, or government production, obtain and retain evidence for:

1. Independent penetration testing and threat modeling.
2. A complete tenant-isolation review across every route, query, worker, cache key, object-storage prefix, and export.
3. Production PostgreSQL migration, rollback, backup, restore, and disaster-recovery drills with measured RTO/RPO.
4. High-availability and load testing for Flask, Celery, Redis, Postgres, and the LLM provider path.
5. KMS/HSM integration, key rotation, revocation, and secret-manager procedures.
6. SBOM, dependency scanning, image signing/verification, vulnerability remediation, and supply-chain controls. Keep assurance ledger exports and any external last-hash anchor in an access-controlled, immutable evidence system.
7. Identity-provider interoperability tests for the customer targets (for example Entra ID, Okta, and government identity systems).
8. Real customer data connectors and domain validation for any sector module that influences decisions.
9. Formal privacy, retention, incident response, access review, support, and customer onboarding procedures.
10. A compliance mapping and external audit for the target market, such as SOC 2, ISO 27001, GDPR, HIPAA, CJIS, or FedRAMP.

Until that evidence exists, position AEON OS as suitable for development, demonstrations, architecture reviews, controlled pilots, and self-hosted enterprise proof-of-concepts—not as an already certified high-assurance system.
