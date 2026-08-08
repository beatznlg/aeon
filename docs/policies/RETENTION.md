# AEON OS — Data Retention and Disposal Procedure

**Owner**: Security lead / DPO where applicable. **Cadence**: annual review.

## 1. Purpose

Define how long each data class is retained and how disposal is executed and
evidenced, including legal hold and regulated-data considerations.

## 2. Retention classes (defaults)

| Data class | Default retention | Disposal |
|---|---|---|
| Audit logs (hash-chained) | 7 years (configurable) | Immutable export to WORM/KMS-governed store; DB deletion after export |
| Conversation episodes | 90 days unless archived | Hard delete + storage cleanup |
| Automation executions | 180 days | Delete from execution store |
| Approvals (HITL) | 365 days | Delete with audit record retained |
| Backups | Per DR policy (see `aeon_dr`) | Retain N versions, then destroy |
| RAG documents/vectors | Until workspace deletion or explicit purge | Vector store + object storage delete |
| PII/PHI-bearing payloads | Shortest lawful period; redacted at audit boundary | Redact or delete; document |

Durations are defaults: customer contracts, agency requirements, and legal
hold override them.

## 3. Legal hold

On written notice, suspend all scheduled deletion for the affected workspaces
and data classes, record the hold in the audit chain, and notify the
operator. Holds must be reviewed quarterly until lifted.

## 4. Disposal execution

1. Identify scope via workspace ID + data class.
2. Export required records to the immutable evidence store.
3. Execute deletion through the API or maintenance procedure (never ad-hoc
   SQL outside change control).
4. Verify deletion (spot checks) and record disposal in the audit chain.
5. Append disposal evidence digest to the assurance ledger.

## 5. Regulated data (PHI, CJIS, financial)

Follow the stricter of this policy and the applicable regime (HIPAA, CJIS,
PCI DSS, GDPR). For GDPR, honor access/erasure requests within the required
window and log them.
