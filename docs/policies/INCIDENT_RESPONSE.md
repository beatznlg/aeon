# AEON OS — Incident Response Procedure

**Owner**: Security lead / on-call engineer. **Review**: quarterly.

## 1. Purpose and scope

This procedure defines how AEON operators detect, contain, eradicate, and
recover from security and availability incidents, including AI-specific
events. It is a procedural document: actual incident response must be
exercised in drills and evaluated by an independent assessor for regulated
use.

## 2. Roles

| Role | Responsibility |
|---|---|
| On-call engineer | First responder; triage; containment |
| Incident commander | Coordinates response; declares severity; communications |
| Security lead | Forensics, evidence chain, root cause |
| Engineering lead | Code fix, release, rollback |
| Communications | Customer/agency notifications per contract |

## 3. Severity levels

| Level | Definition | Response target |
|---|---|---|
| SEV-1 | Tenant data breach, RCE, credential exposure, extended outage | Immediate, 15 min response |
| SEV-2 | Prompt-injection data exfiltration attempt, isolation breach suspicion, service degradation | 30 min |
| SEV-3 | Single-tenant issue, minor error, suspicious audit-chain break | 4 hours |
| SEV-4 | Cosmetic or tooling issue | Next business day |

## 4. Detection sources

- `/health`, `/live`, `/ready` probes and Prometheus alerts.
- `audit_logs` hash-chain verification (`GET /audit/integrity`) fails.
- SIEM integrations and outbound alerting.
- Support/security intake (see `docs/policies/SUPPORT.md`).
- Automated test evidence failures in CI/release gates.

## 5. Response steps

1. **Triage**: confirm scope, tenant, data classification, and severity.
2. **Contain**: revoke API keys/tokens (rotation endpoints), disable the
   affected workspace/automation, block the offending provider endpoint.
3. **Preserve evidence**: export audit rows, traces, and logs; verify the
   audit hash chain; snapshot affected state. Never edit evidence files.
4. **Eradicate**: apply the fix, rotate secrets (including
   `AEON_MASTER_KMS_KEY`-governed secrets), re-run regression suites.
5. **Recover**: restore from verified backups per `docs/policies/RETENTION.md`;
   record measured RTO/RPO with `scripts/dr_drill.py`.
6. **Post-incident review**: root cause, timeline, corrective actions, and
   assurance-ledger evidence entry within 5 business days.

## 6. AI-specific incident types

- **Prompt injection with tool use**: identify the tool invoked, revoke the
  agent's tool permissions for that workspace, review audit trail, and
  harden the capability registry allow-list.
- **Data exfiltration via LLM**: treat as SEV-2+; capture the exact prompt,
  response, and provider contract; verify whether provider retains data.
- **Model/provider outage or poisoning**: fail over to a secondary provider
  (request-local provider switching) and document.

## 7. Notifications and records

Notify affected customers per contract; for government customers, follow the
agency's incident-reporting requirements (e.g., CISA/state requirements).
Retain all records in the assurance ledger with artifact digests.
