# Privacy Policy

AEON v3.0 — Last updated: July 2026

## Overview

AEON is a self-improving autonomous agent framework. This Privacy Policy explains what data we collect, how we use it, how long we keep it, and what rights you have.

## Data We Collect

### When you use the AEON chat interface

- **Messages** you send to the agent
- **Metadata** such as timestamps, backend used, and session identifiers
- **User account information** (email, user ID, workspace ID) if you are authenticated

### When the agent runs autonomously

- **Agent ticks, reflections, and tool executions**
- **Episodic memory** stored locally and optionally mirrored to Supabase
- **Usage metrics** such as token counts, API calls, and billing events

### System data

- **Audit logs** of actions performed inside the AEON OS (CHAT, TICK, WORKFLOW_RUN, etc.)
- **Health and telemetry** data used to keep the service running

## How We Use Data

We use collected data only to:

- Provide the autonomous agent service
- Improve model responses through reflection and episodic memory
- Track usage for billing and quota enforcement
- Maintain audit trails for security and compliance
- Keep the system healthy and operational

We do **not**:

- Sell your data
- Use your data to train third-party models
- Share data with external services beyond those you explicitly configure (Supabase, Hugging Face, OpenAI, Anthropic, etc.)

## Data Storage

- **Local state**: stored in `AEON_ROOT` (default `./aeon_state`)
- **Cloud mirror**: optional Supabase Postgres sink when `SUPABASE_URL` and a valid key are configured
- **Secrets**: stored in environment variables and platform secret managers, never in source code

## Retention

| Data type | Default retention | Configurable |
|-----------|-------------------|--------------|
| Audit logs | 365 days | Yes — via `/governance/retention` |
| Chat episodes | 365 days | Yes — governed by workspace retention policy |
| Usage metrics | 365 days | Yes |
| Error logs | 90 days | No |

You can configure retention policies per workspace through the Governance dashboard at `/os/governance`.

## Your Rights

Depending on your jurisdiction, you may have the right to:

- Access your data
- Correct inaccurate data
- Delete your data
- Export your data
- Object to certain processing

To exercise these rights, contact the project maintainer using the contact information in `SECURITY.md`.

## Security

We implement the following safeguards:

- PII detection and redaction in audit metadata
- Encrypted connections to Supabase (TLS)
- Secret scanning and push protection on the repository
- CodeQL static analysis and automated dependency updates
- Branch protection and required CODEOWNERS review

## Third-Party Services

AEON can be configured to integrate with third-party services. Each integration is controlled by you and only sends data you explicitly choose to send:

- **Supabase**: optional cloud persistence
- **Hugging Face**: optional model downloads and inference
- **OpenAI / Anthropic**: optional LLM backends
- **GitHub**: optional code search integration

## Changes to This Policy

We may update this policy as the project evolves. Significant changes will be noted in commit messages and release notes.

## Contact

For privacy questions or data requests, see the contact section of `SECURITY.md`.
