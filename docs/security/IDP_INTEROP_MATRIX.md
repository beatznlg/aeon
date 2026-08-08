# IdP Interoperability Matrix (manual evidence capture)

**Purpose**: engineering checklist + evidence log for real identity-provider
interoperability. Passing automated tests (see `tests/test_sso.py` and
`tests/test_sso_interop.py`) are necessary but not sufficient: each target
IdP must be exercised against a live tenant and the evidence recorded here
and in the assurance ledger before regulated or government use.

## 1. Automated coverage today

| Capability | Automated | Notes |
|---|---|---|
| OIDC provider CRUD | Yes | `tests/test_sso.py` |
| OIDC callback + token issue | Yes | mocked `complete_oidc_login` |
| id_token signature (JWKS) | Yes | joserfc, `tests/test_sso.py` |
| nonce / tamper / expiry rejection | Yes | `tests/test_sso.py` |
| End-to-end OIDC flow (Entra-shaped mock) | Yes | `tests/test_sso_interop.py` |
| SAML degrade path (lib missing) | Yes | `tests/test_sso.py` |
| SAML assertion verification (real lib) | No | requires python3-saml + fixture IdP |
| JIT provisioning assertions | Partial | mocked in interop harness |

## 2. Target IdP matrix

For each target, run the checklist below against a real or dedicated test
tenant and record pass/fail + evidence digests in the assurance ledger
(`scripts/assurance_evidence.py append ...`).

| IdP | Protocol | Government relevance | Status |
|---|---|---|---|
| Microsoft Entra ID (Azure AD) | OIDC, SAML | Common for state/local agencies | Not yet evidenced |
| Okta | OIDC, SAML | Enterprise | Not yet evidenced |
| Google Workspace | OIDC, SAML | General | Not yet evidenced |
| Keycloak | OIDC, SAML | Self-hosted / sovereign cloud | Not yet evidenced |
| ADFS / PIV-CAC (gov smart-card) | SAML / PKI | Federal, CJIS-adjacent | Not yet evidenced |
| Custom OIDC (regional gov) | OIDC | EU/other sovereign IdPs | Not yet evidenced |

## 3. Per-IdP evidence checklist

1. Discovery document parses (issuer, authorization_endpoint, token_endpoint,
   jwks_uri, scopes_supported).
2. Authorization redirect URL built with state + nonce; state round-trips.
3. Token exchange succeeds; `id_token` present.
4. Signature verifies against the IdP JWKS; nonce matches; expiry enforced.
5. Email/sub claims map to a provisioned user (JIT) with default role from
   `attribute_mapping`.
6. Session/token issued and accepted by `/auth/me` and workspace routes.
7. Logout/revocation behaves (token invalidation where supported).
8. SAML: SP metadata downloadable; AuthnRequest signed where configured;
   assertion signature, audience, and recipient validated; JIT provisioning.
9. Gov/PIV-CAC: certificate-based authn, assertion signed by agency CA,
   audience restricted to the SP entity ID.
10. Failure paths: wrong nonce, expired token, tampered signature, unknown
    email domain (if restricted) all rejected without user creation.

## 4. How to record evidence

```bash
python scripts/assurance_evidence.py append \
  --ledger /secure/evidence.ndjson \
  --profile government --control-id sso_entra_interop --status verified \
  --summary "Entra ID OIDC flow: login + JIT provisioning passed" \
  --source "idp-interop-2026-08-08" \
  --artifact /secure/evidence/entra-idp-report.txt
```

Retain each report with the IdP vendor, tenant, test account, timestamp,
configuration (redacted), and any vendor-specific quirks.
