# AEON OS Compliance Readiness and Authorization Boundary

**Status: engineering readiness evidence only — not a certification or authorization.**

AEON OS includes deployment checks that make selected technical prerequisites
visible before a production-like launch. These checks do not establish legal
compliance, security effectiveness, or authorization. They do not create a
HIPAA certification, PCI DSS attestation, FedRAMP authorization, CJIS approval,
DORA compliance determination, or government ATO.

## What the repository evaluates

Set `AEON_COMPLIANCE_PROFILE` to one of:

| Profile | Technical deployment declarations |
|---|---|
| `baseline` | Production mode, strong JWT secret, KMS key reference, Postgres, explicit CORS origins, Redis, and HSTS |
| `healthcare` | Baseline plus PHI redaction, immutable audit declaration, mandatory human review, and BAA declaration |
| `financial` | Baseline plus immutable audit declaration, mandatory human review, and documented financial scope |
| `critical_infrastructure` | Baseline plus immutable audit declaration, mandatory human review, and approved change-control declaration |
| `government` | Baseline plus immutable audit declaration, mandatory human review, required SSO, and documented authorization boundary |

`GET /ready` returns HTTP `503` when the selected technical profile is not
satisfied. The response contains control names and booleans only; secret values
are never returned. `evaluate_environment(profile, environ={})` deliberately
uses the supplied mapping as-is so release tooling and tests cannot silently
fall back to an ambient developer environment.

## Evidence ledger and release gate

`aeon_assurance.py` provides a dependency-free, hash-chained NDJSON ledger for
recording observations from automated tests, operators, and external assessors.
It stores summaries and SHA-256 artifact digests—not PHI, credentials, or raw
assessment reports. The release helper is:

```bash
python scripts/assurance_evidence.py verify --ledger /secure/evidence.ndjson
python scripts/assurance_evidence.py append --ledger /secure/evidence.ndjson \\
  --profile baseline --control-id backup_restore --status verified \\
  --summary "Restore drill passed" --source "drill-2026-08-04" \\
  --artifact /secure/evidence/restore-report.txt
```

Set `AEON_ASSURANCE_EVIDENCE_PATH` to make the production readiness probe
require the selected profile's verified evidence. `AEON_ASSURANCE_LAST_HASH`
may hold an externally managed last-record hash; when present, readiness fails
if the ledger tail no longer matches that anchor. A local file and hash chain
are tamper-evident within the file, not independently immutable: production
must export or anchor the ledger in an access-controlled/WORM/KMS-governed
system and validate access, retention, key rotation, and recovery procedures.
The readiness result is an engineering evidence gate, never a legal or agency
certification.

A technically passing profile is **not** a certification. The report also lists
external assurance activities that remain outstanding for the selected profile.

## Tamper-evident audit chain

Every `audit_logs` row written through `add_audit_log` is now hash-chained to
the most recent hashed predecessor (SHA-256 over a canonical payload that
includes the row fields plus the previous record hash). This makes edits and
reordering detectable inside the chain:

- `GET /audit/integrity` (admin only) returns a verification report with
  counts and error descriptions only — never audit row contents. It returns
  `503` when the chain does not verify.
- Rows written before this feature (NULL `previous_hash`/`record_hash`) are
  reported as `legacy_unhashed` and make the report fail closed until the
  operator backfills or accepts the legacy window.
- When `AEON_AUDIT_IMMUTABLE=true` in a production profile, the readiness
  probe verifies the live audit chain and fails if it is broken. The
  declaration is therefore backed by a real technical control.

A local hash chain is tamper-evident within the database, not independently
immutable: production must anchor the last record hash in an access-controlled
or WORM/KMS-governed system (mirroring `AEON_ASSURANCE_LAST_HASH` for the
assurance ledger) to detect wholesale deletion of the chain tail, and writes
must be serialized so the chain cannot fork. The chain is an engineering
control, never a legal or agency certification.

## Existing repository evidence

The repository currently provides a useful evidence foundation:

- Tenant-scoped authentication, workspace memberships, RBAC, JWT rotation, and
  SSO/SCIM integration.
- PII/PHI redaction helpers, configurable CORS and security headers, production
  secret checks, and data-residency configuration.
- Workspace-scoped audit, governance, automation approvals, incident handling,
  SIEM integrations, backup/restore models, and Prometheus-compatible metrics.
- A tamper-evident audit hash chain with a verification endpoint and a
  fail-closed readiness check when immutable audit is declared.
- Sector route normalization, registered tool contracts, payload validation, and
  workspace isolation regression tests.
- Docker deployment, ordered database migrations, health/readiness probes, CI
  tests, Ruff, Bandit, dependency audit, and CodeQL workflows.
- A non-sensitive assurance ledger with hash-chain verification, optional
  external tail anchoring, profile-specific evidence gates, and a CLI for
  recording artifact digests.

These features are evidence inputs, not proof that every control operates
correctly in a customer deployment.

## External gates before regulated sales

### Common to all sectors

1. Freeze the intended product and deployment boundary; document data flows,
   sub-processors, trust boundaries, and supported use cases.
2. Complete a threat model and independent penetration test, including prompt
   injection, data exfiltration, tenant isolation, SSRF, supply chain, and
   administrative abuse.
3. Produce a system security plan/control matrix, asset inventory, SBOM,
   vulnerability-management records, secure SDLC evidence, and release/change
   approvals.
4. Use production KMS/HSM-backed key management, immutable or tamper-evident
   audit export, centralized monitoring, retention controls, and tested backup
   restoration.
5. Run load, availability, incident-response, failover, and disaster-recovery
   exercises with measured RTO/RPO and documented corrective actions; record
   the resulting artifact digests in the assurance ledger.
6. Validate all high-impact AI actions with human review, bounded permissions,
   explainable decision records, model/version tracking, and a safe rollback.

### Healthcare

- HIPAA has no general government-issued “HIPAA certification.” Complete a HIPAA
  Security Rule risk analysis and safeguard implementation, validate PHI data
  flows and deletion, and execute BAAs where AEON is a business associate.
- Do not market clinical or diagnostic features as safe or compliant without
  clinical, privacy, safety, and legal review of the exact use case.

### Financial services

- Determine whether AEON handles payment-card data. If it does, define the PCI
  DSS scope and complete the applicable QSA Report on Compliance or SAQ process.
  Prefer a tokenized integration that keeps raw PAN out of AEON.
- For EU financial customers, map the service to DORA ICT-risk management,
  incident reporting, resilience testing, contractual requirements, and any
  applicable oversight by the customer’s competent authority.
- Do not allow autonomous credit, fraud, trading, or payment decisions without
  an approved model-risk and human-oversight process.

### Critical infrastructure

- A generic “critical infrastructure certified” claim is not valid. Identify
  the country, sector, operator, safety impact, and authority requirements.
- Prove segmentation, least privilege, offline/isolated operating modes,
  failover, recovery, change control, and safety review before connecting AEON
  to operational technology or control systems.
- Treat sector dashboards and generated data as demonstration-only until real
  connectors, data quality, safety cases, and authority approvals exist.

### Government and criminal justice

- FedRAMP requires a defined cloud service boundary, control implementation and
  evidence, independent assessment, and an authorization path involving an
  agency or the FedRAMP program. Repository code cannot issue an ATO.
- CJIS deployments require the applicable agency/state agreements, policy
  controls, personnel/process requirements, and authorized boundary. Do not
  claim CJIS approval from application features alone.
- Government sales also require procurement, accessibility, records, privacy,
  supply-chain, incident-reporting, and hosting requirements for the target
  jurisdiction and data classification.

## Authoritative references

- [HHS HIPAA Security Rule](https://www.hhs.gov/hipaa/for-professionals/security/laws-regulations/index.html)
- [PCI Security Standards Council](https://www.pcisecuritystandards.org/)
- [EU Digital Operational Resilience Act overview](https://www.eiopa.europa.eu/digital-operational-resilience-act-dora_en)
- [NIST SP 800-53 Rev. 5](https://csrc.nist.gov/pubs/sp/800/53/r5/upd1/final)
- [NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework)
- [NIST Secure Software Development Framework](https://csrc.nist.gov/pubs/sp/800/218/final)
- [FedRAMP](https://www.fedramp.gov/)
- [FBI CJIS Security Policy](https://le.fbi.gov/informational-pages/cjis-security-policy-resource-center)

## Sales language

Until the external gates above are complete, describe AEON as:

> “An enterprise AI orchestration platform with configurable governance,
> tenant isolation, human approvals, auditability, and deployment-readiness
> controls for pilots and controlled production assessments.”

Do **not** market it as “certified,” “FedRAMP authorized,” “HIPAA certified,”
“PCI DSS compliant,” “CJIS approved,” or approved for safety-critical control
unless the exact external evidence, contracts, assessment, and authorization
are complete and current.
