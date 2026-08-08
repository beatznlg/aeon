# AEON OS — Access Review Procedure

**Owner**: Workspace admins / security lead. **Cadence**: quarterly.

## 1. Purpose

Verify that every account, membership, role, API key, SSO link, and service
credential is authorized, current, and least-privileged.

## 2. Review items

1. **Users**: all registered users; disable or delete dormant accounts
   (no login in 90 days).
2. **Workspace memberships**: every `workspace_memberships` row matches a
   current employee/contractor; remove leavers immediately.
3. **Roles**: confirm RBAC assignments (VIEWER/OPERATOR/ADMIN/SUPER_ADMIN)
   match the role catalogue; flag SUPER_ADMIN sprawl.
4. **API keys**: enumerate, rotate stale keys, revoke keys of leavers
   (`POST /api-keys/<id>/rotate`, revoke).
5. **SSO/SCIM**: reconcile identity-provider groups with SCIM groups;
   confirm JIT provisioning did not create orphaned accounts.
6. **Service credentials**: confirm DB, Redis, Stripe, LLM provider, and
   object-storage credentials are stored in the secret manager and rotated
   on staff changes.
7. **Admin accounts**: verify the seeded admin was renamed and uses a strong
   unique password or SSO.

## 3. Procedure

1. Export user, membership, role, and key inventories from the admin API.
2. Compare against the HR directory or IdP directory (Entra ID, Okta).
3. Record exceptions and remediation owners in a review ticket.
4. Apply changes through the normal change-control process.
5. Append the review summary and artifact digest to the assurance ledger
   (`scripts/assurance_evidence.py append --control-id access_review ...`).

## 4. Evidence and auditability

Access changes are written to `audit_logs`; the quarterly review must include
an audit-chain integrity check (`GET /audit/integrity`).
