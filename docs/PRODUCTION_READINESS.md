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

The backend honors the platform-provided `PORT` when `AEON_PYTHON_PORT` is not set. Docker and Railway deployments should use the backend health endpoint at `/health` and the liveness endpoint at `/live`.

## Validation evidence

The repository's latest local validation recorded:

- `pytest -q`: 223 passed
- Python compilation: passed
- Frontend `npx tsc --noEmit`: passed
- Frontend `npm run lint`: passed
- `git diff --check`: passed

Run the complete quality gate before every release, including Bandit, pip-audit, frontend production build, Docker image builds, and deployment smoke tests.

## Remaining evidence before regulated sales

The codebase is a feature-rich enterprise pilot foundation. Before representing it as ready for unrestricted commercial, healthcare, financial, or government production, obtain and retain evidence for:

1. Independent penetration testing and threat modeling.
2. A complete tenant-isolation review across every route, query, worker, cache key, object-storage prefix, and export.
3. Production PostgreSQL migration, rollback, backup, restore, and disaster-recovery drills with measured RTO/RPO.
4. High-availability and load testing for Flask, Celery, Redis, Postgres, and the LLM provider path.
5. KMS/HSM integration, key rotation, revocation, and secret-manager procedures.
6. SBOM, dependency scanning, image signing/verification, vulnerability remediation, and supply-chain controls.
7. Identity-provider interoperability tests for the customer targets (for example Entra ID, Okta, and government identity systems).
8. Real customer data connectors and domain validation for any sector module that influences decisions.
9. Formal privacy, retention, incident response, access review, support, and customer onboarding procedures.
10. A compliance mapping and external audit for the target market, such as SOC 2, ISO 27001, GDPR, HIPAA, CJIS, or FedRAMP.

Until that evidence exists, position AEON OS as suitable for development, demonstrations, architecture reviews, controlled pilots, and self-hosted enterprise proof-of-concepts—not as an already certified high-assurance system.
