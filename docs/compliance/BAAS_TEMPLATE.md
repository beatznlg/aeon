# AEON OS — Business Associate Agreement (BAA) Template

> **Process artifact, not a legal document.** This template is a starting point
> for negotiation with counsel. HIPAA compliance requires an executed BAA
> tailored to the actual parties, PHI flows, and subprocessors. Fill every
> bracketed field, have it reviewed by qualified legal counsel, and store the
> executed copy in the evidence ledger (`AEON_ASSURANCE_EVIDENCE_PATH`).

## Parties

- **Covered Entity:** [Legal name], [Address], [Contact] ("Covered Entity")
- **Business Associate:** [Legal name], [Address], [Contact] ("Business Associate")

Effective Date: [date]

## 1. Definitions

Terms used in this Agreement have the meanings set forth in 45 CFR § 160.103.
"PHI" means protected health information as defined therein.

## 2. Permitted Uses and Disclosures

Business Associate may use and disclose PHI only to:

1. Perform functions on behalf of Covered Entity as described in [Exhibit A —
   Services Description], which include: [list AEON OS services, e.g. AI-assisted
   documentation, data pipelines, analytics].
2. Manage the Business Associate's own operations, as permitted by 45 CFR
   § 164.504(e)(4)(ii), and as required by law.

Business Associate may not use or disclose PHI in any manner that would
violate the HIPAA Privacy Rule if done by the Covered Entity.

## 3. Safeguards

Business Associate agrees to implement administrative, physical, and technical
safeguards that reasonably and appropriately protect the confidentiality,
integrity, and availability of PHI (45 CFR § 164.530(c)(1) and § 164.314(a)(2)(i)),
including at minimum:

- Encryption of ePHI at rest and in transit (AEON KMS/encryption controls).
- Access control with least-privilege, workspace-scoped RBAC.
- Audit logging with tamper-evident (hash-chained) integrity.
- Breach-notification readiness per 45 CFR § 164.410.

## 4. Breach Notification

Business Associate shall report any breach of unsecured PHI to Covered Entity
without unreasonable delay, and in no case later than [60] days after
discovery, per 45 CFR § 164.410, including the information required by
45 CFR § 164.410(c).

## 5. Subcontractors

Business Associate shall ensure any subcontractor that receives PHI agrees to
the same restrictions, and shall maintain a current list of subcontractors
[available to Covered Entity on request].

## 6. Access, Amendment, and Accounting

Business Associate shall make PHI available for access (§ 164.524), amendment
(§ 164.526), and accounting of disclosures (§ 164.528) as required, in a
mutually agreed electronic format.

## 7. Termination

- Either party may terminate for material breach with [30] days' written notice
  and opportunity to cure.
- Upon termination, Business Associate shall return or destroy all PHI, or
  extend the protections if return/destruction is infeasible, and certify the
  disposition per 45 CFR § 164.314(a)(2)(i).

## 8. Miscellaneous

- This Agreement is governed by [state/federal law].
- No party may assign without the other's written consent.
- This Agreement survives termination where necessary to protect PHI.

## Exhibits

- **Exhibit A — Services Description:** [services, data flows, retention]
- **Exhibit B — Subprocessor List:** [names, jurisdictions, roles]

## Signature

Covered Entity: ______________________  Date: ________

Business Associate: __________________  Date: ________

---

**Evidence workflow:** after execution, record in the ledger:
`python scripts/assurance_evidence.py --profile healthcare --control baa_review --status verified --summary "BAA executed with [party]" --source "[party]"`.
