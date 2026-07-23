# Security Policy

Thank you for helping keep **AEON** and its users safe. This document explains how to report security issues, what we support, and how we handle vulnerabilities.

## Supported Versions

Security updates are applied to the following branches:

| Branch | Supported |
|--------|-----------|
| `main` | ✅ Yes — current stable branch |
| `staging` | ⚠️ Best effort — pre-release fixes only |
| older release tags | ❌ No — please migrate to `main` |

The latest code lives on `main`. We recommend running the most recent commit and keeping dependencies up to date via Dependabot.

## Reporting a Vulnerability

If you discover a security vulnerability in AEON, please report it privately so we can fix it before public disclosure.

**Please do not open a public issue or pull request for security bugs.**

### How to report

1. **GitHub Private Vulnerability Reporting**
   - Go to the repository and click **Security → Advisories → Report a vulnerability**.
   - Include a clear description, reproduction steps, affected versions, and potential impact.

2. **Email (fallback)**
   - Send an encrypted or plain email to the maintainer listed in the repository owner profile.
   - Allow up to 72 hours for an initial response.

## Disclosure Policy

We follow a coordinated disclosure process:

1. **Acknowledgment** — We acknowledge receipt of your report within 72 hours.
2. **Investigation** — We confirm the issue and determine severity and affected scope.
3. **Fix** — We develop and test a patch on a private branch.
4. **Release** — We publish the fix, release notes, and a security advisory.
5. **Public disclosure** — We disclose the issue publicly after the fix is available, typically within 90 days of report receipt or sooner if the fix is released.

We credit researchers who report valid vulnerabilities with attribution in the advisory, unless they prefer to remain anonymous.

## Response Time

| Severity | Initial Response | Target Fix |
|----------|------------------|------------|
| Critical | ≤ 24 hours | ≤ 7 days |
| High | ≤ 48 hours | ≤ 14 days |
| Medium | ≤ 72 hours | ≤ 30 days |
| Low | ≤ 7 days | Best effort |

Severity is determined using the [CVSS v3.1](https://www.first.org/cvss/v3.1/specification) scoring model.

## Security Hardening Already in Place

- **CodeQL** — Automated static analysis for Python and JavaScript/TypeScript via `.github/workflows/codeql.yml`.
- **Dependabot** — Automated dependency updates and security alerts via `.github/dependabot.yml`.
- **CI checks** — Every push runs compile checks, self-tests, notebook validation, and TypeScript type-checks via `.github/workflows/aeon-ci.yml`.
- **Secret scanning** — GitHub secret scanning and push protection are enabled on the repository.
- **CODEOWNERS** — Critical files require review by the project maintainer.
- **Governance module** — Audit logging, compliance checks, and retention policies are available via `aeon_governance.py` and the `/os/governance` dashboard.

## Scope

In scope for security reports:

- The `aeon.py` kernel and self-improvement loop
- `aeon_server.py` API endpoints and agent execution pipeline
- `web/` frontend authentication, authorization, and API routes
- Supabase migrations and database access patterns
- Integration connectors and webhook handlers
- GitHub Actions workflows and CI/CD configuration

Out of scope:

- Third-party dependencies (please report to the upstream project)
- Infrastructure or hosting provider issues (report to the provider)
- Theoretical attacks without a working proof of concept

## Security-Related Configuration

- Do not commit secrets, API keys, or private keys to the repository.
- Environment variables are managed through the platform Keys tab; never paste them into source files.
- Use the provided `freebuff-env` tooling to set secrets safely when deploying on Freebuff Cloud.

## Questions?

If you have questions about this policy or a previous report, please open a private security advisory on GitHub or contact the maintainer directly.
