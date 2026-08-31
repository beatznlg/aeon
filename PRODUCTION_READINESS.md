# AEON OS Production Readiness

## Target architecture

AEON production is Oracle-only: Caddy -> Next.js -> Flask API -> PostgreSQL/Redis -> Celery Worker/Beat. PostgreSQL, Redis, and application services are private Docker services; Caddy is the only published service.

## Gate status

### P0 — release blockers
- [x] Oracle production compose includes PostgreSQL, Redis, backend, worker, Beat, web, and Caddy.
- [x] PostgreSQL and Redis are not published to the host in the Oracle stack.
- [x] Required production secrets fail fast instead of silently using development defaults.
- [x] Oracle deployment verifies all production services and API health.
- [x] Deployment has automatic rollback on health failure.
- [x] Local database backups are retained outside containers.
- [ ] Complete adversarial tenant-isolation test suite.
- [ ] Complete authentication/authorization attack matrix.
- [ ] Complete production secret-leak scan of history and runtime logs.

### P1 — required before declaring production proven
- [x] Redis persistence enabled.
- [x] Celery worker and Beat deployed in Oracle.
- [x] Backup script supports an off-host S3-compatible destination (including OCI Object Storage).
- [ ] Execute and verify an off-host backup from the real Oracle VM.
- [ ] Execute a clean database restore drill from an off-host backup.
- [ ] Verify worker retries, idempotency, and failure recovery under load.
- [ ] Verify Beat recovery and duplicate-schedule protection.
- [ ] Verify Stripe webhook signature and idempotency behavior end-to-end.
- [ ] Verify LLM provider failure/fallback behavior end-to-end.
- [ ] Execute browser E2E authentication/workspace/RAG/workflow tests.
- [ ] Execute API load and soak tests against the Oracle deployment.

### P2 — scale/enterprise
- [ ] Multi-VM high availability.
- [ ] Database high availability.
- [ ] Autoscaling.
- [ ] Dedicated object-storage-backed knowledge assets.
- [ ] Formal compliance evidence package.

## Release rule

AEON must not be labeled "100% production proven" until all P0 items and all P1 execution/verification items are checked on the real Oracle deployment. Code presence alone is not considered proof.

## Operational acceptance

A release is accepted only when:

1. CI passes.
2. Oracle Compose validates.
3. All seven services are healthy.
4. `/health` and `/api/health` succeed.
5. Database backup succeeds.
6. Restore drill succeeds in an isolated environment.
7. Authentication and tenant isolation tests pass.
8. Worker/Beat recovery tests pass.
9. E2E smoke tests pass.
10. Load/soak test meets documented latency and error-rate thresholds.
11. Rollback to the previous known-good commit succeeds.
