# AEON OS Operating Profiles

Operating profiles are AEON's adaptation layer for companies, sectors, and public-sector deployments. A profile is a **reviewable set of defaults and recommendations**; selecting one never grants permissions, enables connectors, or represents a compliance certification.

## Supported profiles

The built-in catalog currently includes:

- **General Business** — neutral defaults for startups, SMEs, nonprofits, and enterprise teams.
- **Regulated Enterprise** — stronger approval, evidence, data-governance, and residency recommendations.
- **Healthcare Provider** — HIPAA/HITECH-oriented patient-safety and human-review defaults.
- **Financial Services** — fraud, credit, payment, risk, PCI DSS, and audit controls.
- **Critical Infrastructure** — resilience and change-control defaults for utilities, energy, telecom, and transport, including air-gapped and edge deployments.
- **Government Agency** — transparent, accountable, residency-aware public-sector defaults for agencies and municipalities.
- **Defense / Air-Gapped** — fail-closed, disconnected-operation defaults for mission-sensitive environments.
- **Education** — student-safety and privacy recommendations for schools and universities.
- **Manufacturing Operations** — plant, quality, supply-chain, and production-change controls.

Each profile declares supported sectors, organization types, deployment modes, data classifications, compliance references, recommended plugins/capabilities, and approval-gated action classes.

## Architecture

```text
workspace context
      │
      ▼
operating profile catalog ──► recommendation ranking
      │
      ▼
workspace selection (non-secret JSON state)
      │
      ├── effective plugin recommendations
      ├── capability recommendations
      ├── approval-gated action classes
      └── compliance/evidence references
```

The registry is implemented in `aeon_operating_profiles.py`. Workspace selections are stored under `AEON_ROOT/operating_profiles.json` using an atomic replace. Secrets and connector credentials remain in the existing API-key/configuration systems and are never written to this file.

## HTTP API

All routes require authentication and a workspace membership. Catalog reads require the `VIEWER` role. Workspace selection changes require an `ADMIN` or `SUPER_ADMIN` role.

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/operating-profiles` | List profiles, optionally filtered by `sector`, `organization_type`, or `deployment_mode` |
| GET | `/operating-profiles/recommend` | Rank profiles by sector, organization, deployment, and classification |
| GET | `/operating-profiles/<profile_id>` | Read one profile manifest |
| GET | `/workspace/operating-profile` | Read the current workspace selection and effective recommendations |
| PUT | `/workspace/operating-profile` | Select a profile and non-secret workspace context |

The Next.js proxies are available at `/api/os/operating-profiles` and `/api/os/operating-profile`. The product page is `/os/operating-profiles`.

Example selection:

```json
{
  "profile_id": "government-agency",
  "sector": "government",
  "organization_type": "government-agency",
  "deployment_mode": "air-gapped",
  "data_classification": "restricted",
  "compliance_frameworks": ["agency-specific-control-baseline"]
}
```

The selection is validated against the profile's supported context. An incompatible combination is rejected rather than silently falling back to a weaker profile.

## Governance and safety

- Profiles only recommend existing marketplace plugins and built-in capabilities; they do not auto-install or auto-enable them.
- Plugin execution remains controlled by marketplace permissions, capability roles, workspace policies, and approval workflows.
- External writes, production changes, restricted-data access, clinical decisions, benefits decisions, payment actions, and mission actions can be listed as approval-required areas.
- Air-gapped and defense profiles do not create network access. External connectors must be explicitly configured and reviewed.
- Compliance framework names are planning metadata, not evidence of ISO 27001, SOC 2, HIPAA, FedRAMP, CJIS, PCI DSS, CMMC, or any other certification.
- Profile selection is audit-recorded as `OPERATING_PROFILE_SELECTED` without storing credentials or sensitive prompt data.

## Extension guide

To add a new sector or organization pattern:

1. Add or verify the sector's tools in `aeon_sectors.py` and `web/lib/sector-registry.ts`.
2. Add the corresponding plugin IDs to the marketplace catalog if a new capability is required.
3. Add a declarative `OperatingProfile` entry and keep all IDs inside the validation allowlists.
4. Add tests for at least one valid selection and one incompatible selection.
5. Update this document with the operational and compliance boundaries.

A profile should remain declarative and small. Business-specific policy, authorization, data retention, and connector configuration belong in their dedicated modules.
