# AEON OS — Support and Escalation Procedure

**Owner**: Support lead. **Cadence**: annual review.

## 1. Support tiers

| Tier | Audience | Channel | Target first response |
|---|---|---|---|
| T1 | All customers | Ticket/portal, chat | 1 business day (Basic), 4 h (Enterprise) |
| T2 | Enterprise | T1 escalation | 2 h during support window |
| T3 | Enterprise, security incidents | Engineering | Per incident severity (see INCIDENT_RESPONSE.md) |

## 2. Intake and triage

1. Capture environment info, AEON version, logs (redacted), and reproduction
   steps.
2. Classify: support issue vs. security incident. Security signals (breach
   suspicion, credential exposure, data access anomaly) route immediately to
   the IR procedure — never wait for the support queue.
3. Confirm workspace and tenant scope before any data access; support staff
   access customer data only with justification, logged in the audit chain.

## 3. Escalation matrix

| Condition | Escalate to |
|---|---|
| SEV-1/SEV-2 signal | Security lead + on-call immediately |
| No response in SLA | Support lead |
| Bug with workaround absent | Engineering lead |
| Contractual/legal | Account manager + legal |

## 4. Customer onboarding and offboarding

- **Onboarding**: provision workspace, assign roles per ACCESS_REVIEW.md,
  configure SSO/SCIM, set retention, and complete a security questionnaire.
- **Offboarding**: revoke memberships and API keys on day one, export
  customer data on request, then dispose per RETENTION.md.

## 5. Reporting

Monthly metrics: tickets by tier, SLA attainment, security-intake count, and
open incidents. Publish quarterly to stakeholders.
