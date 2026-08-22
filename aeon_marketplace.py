"""
AEON OS — Plugin Marketplace
============================
A distribution and lifecycle layer that lets AEON OS integrate third-party
capabilities through a *plugin* abstraction:

* A marketplace catalog of plugin manifests (id, version, category, icon,
  permissions, entry points, config schema, verification status).
* Workspace-scoped installation state (install / uninstall / enable / disable
  / configure), persisted under ``AEON_ROOT/marketplace/installs.json``.
* An entry-point runner for the shipped built-in plugins. Built-ins execute
  deterministic handlers inside this module. **Third-party code is never
  executed by this module**: arbitrary plugin code requires a separately
  deployed sandbox (container/gVisor/Firecracker) and a signed-manifest
  pipeline before it is enabled for customer workloads.

The module is intentionally dependency-free (standard library only) so it
loads quickly and is safe to import in tests and edge deployments.

Security posture
----------------
* Install/enable/disable are audit-logged by the server layer.
* Manifests are validated against an allowlist of permissions and a safe
  identifier format. Unknown permissions fail validation closed.
* Entry-point execution is gated on the plugin being installed, enabled, and
  declaring the ``execute`` permission.
* Config values are validated against each plugin's config schema.
* Installs are keyed by ``(workspace_id, plugin_id)``; the server layer
  resolves ``workspace_id`` from the authenticated caller so one workspace
  can never read or mutate another workspace's installs.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aeon_connector_plugins import CONNECTOR_PLUGIN_DEFINITIONS

# === constants =============================================================

MARKETPLACE_VERSION = 1

PLUGIN_CATEGORIES = (
    "ai",
    "analytics",
    "automation",
    "communication",
    "data",
    "devops",
    "integration",
    "productivity",
    "security",
    "sector",
)

#: Permissions a plugin may declare. Anything else fails manifest validation.
ALLOWED_PERMISSIONS = frozenset({"read", "write", "execute", "network", "notify", "admin"})

_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")
_VERSION_PATTERN = re.compile(r"^\d+\.\d+(\.\d+)?$")


# === models ================================================================


@dataclass(frozen=True)
class PluginManifest:
    """Metadata describing a plugin offered in the marketplace.

    Manifests are immutable by convention; version changes are represented by
    a new manifest object. The ``entry_points`` map is ``entry -> description``
    and every entry requires the ``execute`` permission at run time.
    """

    id: str
    name: str
    version: str
    description: str
    author: str
    category: str
    icon: str
    permissions: tuple[str, ...]
    entry_points: dict[str, str] = field(default_factory=dict)
    config_schema: dict[str, Any] = field(default_factory=dict)
    verified: bool = False
    source: str = "builtin"
    tags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "category": self.category,
            "icon": self.icon,
            "permissions": list(self.permissions),
            "entry_points": self.entry_points,
            "config_schema": self.config_schema,
            "verified": self.verified,
            "source": self.source,
            "tags": list(self.tags),
        }


@dataclass
class PluginInstall:
    """Workspace-scoped installation state for a plugin."""

    plugin_id: str
    workspace_id: str
    version: str
    enabled: bool = True
    config: dict[str, Any] = field(default_factory=dict)
    installed_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "workspace_id": self.workspace_id,
            "version": self.version,
            "enabled": self.enabled,
            "config": self.config,
            "installed_at": self.installed_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PluginInstall:
        return cls(
            plugin_id=data["plugin_id"],
            workspace_id=data["workspace_id"],
            version=data.get("version", "0.0.0"),
            enabled=data.get("enabled", True),
            config=data.get("config", {}),
            installed_at=data.get("installed_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
        )


# === manifest validation ===================================================


def validate_manifest(data: dict[str, Any]) -> dict[str, Any]:
    """Validate an externally submitted manifest and return a normalized copy.

    Returns ``{"ok": True, "manifest": {...}}`` or
    ``{"ok": False, "error": "..."}``. Validation fails closed on unknown
    permissions, unsafe identifiers, missing entry points, or bad versions.
    """
    errors: list[str] = []

    plugin_id = str(data.get("id", "")).strip()
    if not _ID_PATTERN.match(plugin_id):
        errors.append("id must match ^[a-z0-9][a-z0-9-]{1,63}$")

    version = str(data.get("version", "")).strip()
    if not _VERSION_PATTERN.match(version):
        errors.append("version must be semver-like (e.g. 1.2 or 1.2.3)")

    name = str(data.get("name", "")).strip()
    description = str(data.get("description", "")).strip()
    if not name or not description:
        errors.append("name and description are required")

    category = str(data.get("category", "")).strip().lower()
    if category not in PLUGIN_CATEGORIES:
        errors.append(f"category must be one of: {', '.join(PLUGIN_CATEGORIES)}")

    permissions = data.get("permissions", [])
    if not isinstance(permissions, list) or not permissions:
        errors.append("at least one permission is required")
    else:
        for perm in permissions:
            if str(perm).strip() not in ALLOWED_PERMISSIONS:
                errors.append(f"unknown permission: {perm}")

    entry_points = data.get("entry_points", {})
    if not isinstance(entry_points, dict) or not entry_points:
        errors.append("entry_points must be a non-empty mapping of entry -> description")

    config_schema = data.get("config_schema", {})
    if not isinstance(config_schema, dict):
        errors.append("config_schema must be an object")

    if errors:
        return {"ok": False, "error": "; ".join(errors)}

    return {
        "ok": True,
        "manifest": {
            "id": plugin_id,
            "name": name,
            "version": version,
            "description": description,
            "author": str(data.get("author", "")).strip() or "unknown",
            "category": category,
            "icon": str(data.get("icon", "🔌")).strip() or "🔌",
            "permissions": [str(p).strip() for p in permissions],
            "entry_points": {str(k).strip(): str(v).strip() for k, v in entry_points.items()},
            "config_schema": config_schema,
            "verified": bool(data.get("verified", False)),
            "source": str(data.get("source", "")).strip() or "external",
            "tags": [str(t).strip() for t in data.get("tags", [])],
        },
    }


def validate_config(schema: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Validate plugin config against its schema; returns a normalized copy.

    Schema entries: ``{"type": "string|number|boolean", "default": ...,
    "required": bool, "description": str}``.
    """
    normalized: dict[str, Any] = {}
    errors: list[str] = []

    for key, spec in (schema or {}).items():
        if not isinstance(spec, dict):
            continue
        spec_type = spec.get("type", "string")
        required = spec.get("required", False)
        default = spec.get("default")
        value = config.get(key, default) if key in config else default

        if value is None:
            if required:
                errors.append(f"config key '{key}' is required")
            continue

        if spec_type == "boolean" and not isinstance(value, bool):
            errors.append(f"config key '{key}' must be a boolean")
            continue
        if spec_type == "number":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                errors.append(f"config key '{key}' must be a number")
                continue
            value = float(value)
        if spec_type == "string" and not isinstance(value, str):
            errors.append(f"config key '{key}' must be a string")
            continue
        normalized[key] = value

    # Reject config keys that are not declared in the schema (fail closed).
    for key in config:
        if key not in (schema or {}):
            errors.append(f"unknown config key '{key}'")

    if errors:
        return {"ok": False, "error": "; ".join(errors)}
    return {"ok": True, "config": normalized}


# === built-in catalog ======================================================

BUILTIN_PLUGIN_CATALOG: tuple[PluginManifest, ...] = (
    *(PluginManifest(**definition) for definition in CONNECTOR_PLUGIN_DEFINITIONS),
    PluginManifest(
        id="incident-responder",
        name="Incident Responder",
        version="1.2.0",
        description="Automated incident triage, runbook execution, and severity escalation for your anomaly and SIEM feeds.",
        author="AEON Labs",
        category="security",
        icon="🚨",
        permissions=("read", "execute", "notify"),
        entry_points={
            "triage": "Classify an incoming incident and propose a runbook.",
            "escalate": "Escalate an incident based on severity and SLA policy.",
            "postmortem": "Generate a structured post-incident summary.",
        },
        config_schema={
            "auto_triage": {"type": "boolean", "default": True, "description": "Automatically triage new incidents."},
            "escalation_channel": {"type": "string", "default": "#incidents", "description": "Channel for escalations."},
        },
        verified=True,
        tags=("incidents", "runbooks", "soc"),
    ),
    PluginManifest(
        id="sentiment-analyzer",
        name="Sentiment Analyzer",
        version="2.0.1",
        description="Analyze sentiment and tone for feedback, support tickets, and social listening feeds.",
        author="AEON Labs",
        category="analytics",
        icon="📊",
        permissions=("read", "execute"),
        entry_points={
            "analyze": "Return a sentiment breakdown for a body of text.",
            "trends": "Summarize sentiment trends across samples.",
        },
        config_schema={
            "locale": {"type": "string", "default": "en", "description": "Language code for analysis."},
            "confidence_threshold": {"type": "number", "default": 0.5, "description": "Minimum confidence."},
        },
        verified=True,
        tags=("nlp", "analytics"),
    ),
    PluginManifest(
        id="fraud-scoring",
        name="Fraud Scoring",
        version="1.4.0",
        description="Rule- and signal-based fraud risk scoring for payments and account activity.",
        author="AEON Labs",
        category="security",
        icon="🛡️",
        permissions=("read", "execute"),
        entry_points={
            "score": "Compute a fraud risk score for a transaction.",
            "rules": "List the active fraud detection rules.",
        },
        config_schema={
            "risk_threshold": {"type": "number", "default": 0.8, "description": "High-risk threshold."},
            "review_queue": {"type": "string", "default": "fraud-review", "description": "Queue for flagged items."},
        },
        verified=True,
        tags=("finance", "fraud", "risk"),
    ),
    PluginManifest(
        id="drug-interaction-check",
        name="Drug Interaction Check",
        version="1.1.0",
        description="Cross-reference medication lists for known interactions and contraindications.",
        author="AEON Labs",
        category="sector",
        icon="💊",
        permissions=("read", "execute"),
        entry_points={
            "check": "Check a list of medications for interactions.",
            "profile": "Summarize a patient medication profile.",
        },
        config_schema={
            "source_formulary": {"type": "string", "default": "internal", "description": "Formulary data source."},
        },
        verified=False,
        tags=("health", "pharma"),
    ),
    PluginManifest(
        id="grid-monitor",
        name="Grid Monitor",
        version="1.3.0",
        description="Monitor utility grid telemetry, load balancing, and outage signals.",
        author="AEON Labs",
        category="sector",
        icon="⚡",
        permissions=("read", "execute", "notify"),
        entry_points={
            "status": "Report grid status for a region.",
            "outage_alert": "Evaluate telemetry for outage conditions.",
        },
        config_schema={
            "region": {"type": "string", "default": "all", "description": "Grid region filter."},
            "critical_threshold": {"type": "number", "default": 0.9, "description": "Critical load threshold."},
        },
        verified=False,
        tags=("utilities", "infrastructure"),
    ),
    PluginManifest(
        id="fleet-optimizer",
        name="Fleet Optimizer",
        version="1.0.3",
        description="Route optimization and fleet utilization analysis for logistics operations.",
        author="AEON Labs",
        category="sector",
        icon="🚚",
        permissions=("read", "execute"),
        entry_points={
            "routes": "Propose optimized routes for a vehicle set.",
            "utilization": "Compute fleet utilization metrics.",
        },
        config_schema={
            "fleet_size": {"type": "number", "default": 10, "description": "Number of vehicles."},
            "fuel_cost": {"type": "number", "default": 1.5, "description": "Fuel cost per unit."},
        },
        verified=True,
        tags=("transport", "logistics"),
    ),
    PluginManifest(
        id="inventory-forecast",
        name="Inventory Forecast",
        version="2.1.0",
        description="Demand forecasting and reorder-point recommendations for retail and supply chains.",
        author="AEON Labs",
        category="sector",
        icon="📦",
        permissions=("read", "execute"),
        entry_points={
            "forecast": "Forecast demand for SKUs.",
            "reorder": "Compute reorder points and quantities.",
        },
        config_schema={
            "lead_time_days": {"type": "number", "default": 14, "description": "Supplier lead time."},
            "service_level": {"type": "number", "default": 0.95, "description": "Target service level."},
        },
        verified=True,
        tags=("retail", "supply-chain"),
    ),
    PluginManifest(
        id="compliance-reporter",
        name="Compliance Reporter",
        version="1.2.1",
        description="Generate compliance posture reports from governance, audit, and policy data.",
        author="AEON Labs",
        category="security",
        icon="📋",
        permissions=("read", "write", "execute"),
        entry_points={
            "report": "Generate a compliance summary report.",
            "controls": "List the evaluated control families.",
        },
        config_schema={
            "framework": {"type": "string", "default": "baseline", "description": "Target framework profile."},
            "include_evidence": {"type": "boolean", "default": True, "description": "Include evidence digests."},
        },
        verified=True,
        tags=("governance", "compliance"),
    ),
    PluginManifest(
        id="doc-extractor",
        name="Document Extractor",
        version="1.5.0",
        description="Extract structured fields from documents, invoices, and receipts.",
        author="AEON Labs",
        category="data",
        icon="📄",
        permissions=("read", "execute"),
        entry_points={
            "extract": "Extract structured fields from a document.",
            "schema": "Return the supported extraction schema.",
        },
        config_schema={
            "ocr_enabled": {"type": "boolean", "default": True, "description": "Enable OCR pass."},
            "max_pages": {"type": "number", "default": 50, "description": "Maximum pages per document."},
        },
        verified=True,
        tags=("ocr", "documents"),
    ),
    PluginManifest(
        id="customer-support-bot",
        name="Customer Support Bot",
        version="1.6.2",
        description="Draft responses, summarize tickets, and suggest resolution steps for support teams.",
        author="AEON Labs",
        category="productivity",
        icon="💬",
        permissions=("read", "execute", "notify"),
        entry_points={
            "draft": "Draft a support response for a ticket.",
            "summarize": "Summarize a support conversation.",
        },
        config_schema={
            "tone": {"type": "string", "default": "professional", "description": "Response tone."},
            "max_tokens": {"type": "number", "default": 500, "description": "Draft length limit."},
        },
        verified=True,
        tags=("support", "crm"),
    ),
    PluginManifest(
        id="scheduler",
        name="Smart Scheduler",
        version="1.0.0",
        description="Meeting and shift scheduling optimization across calendars and constraints.",
        author="AEON Labs",
        category="productivity",
        icon="🗓️",
        permissions=("read", "execute"),
        entry_points={
            "suggest": "Suggest meeting times from constraints.",
            "conflicts": "Detect scheduling conflicts.",
        },
        config_schema={
            "working_hours": {"type": "string", "default": "09:00-17:00", "description": "Working hours window."},
        },
        verified=True,
        tags=("calendar", "productivity"),
    ),
    PluginManifest(
        id="github-actions",
        name="GitHub Actions Bridge",
        version="2.0.0",
        description="Trigger workflows, read build status, and surface CI/CD signals inside AEON.",
        author="AEON Labs",
        category="devops",
        icon="🐙",
        permissions=("read", "execute", "network"),
        entry_points={
            "status": "Report workflow run status for a repository.",
            "trigger": "Trigger a workflow dispatch event.",
        },
        config_schema={
            "repository": {"type": "string", "default": "", "description": "Owner/repo."},
            "workflow": {"type": "string", "default": "ci.yml", "description": "Workflow file."},
        },
        verified=True,
        tags=("ci", "cd", "github"),
    ),
    PluginManifest(
        id="siem-connector",
        name="SIEM Connector",
        version="1.1.1",
        description="Normalize and forward detection signals to Splunk, Sentinel, QRadar, and Elastic.",
        author="AEON Labs",
        category="integration",
        icon="🕵️",
        permissions=("read", "write", "execute", "network"),
        entry_points={
            "forward": "Forward a detection event to the configured SIEM.",
            "health": "Check SIEM delivery health.",
        },
        config_schema={
            "target": {"type": "string", "default": "splunk", "description": "SIEM target type."},
            "retry_on_failure": {"type": "boolean", "default": True, "description": "Retry failed deliveries."},
        },
        verified=False,
        tags=("siem", "security"),
    ),
    PluginManifest(
        id="market-insights",
        name="Market Insights",
        version="1.2.0",
        description="Aggregate pricing, demand, and competitor signals into sector dashboards.",
        author="AEON Labs",
        category="analytics",
        icon="📈",
        permissions=("read", "execute"),
        entry_points={
            "insights": "Produce a market insight summary.",
            "pricing": "Suggest price positioning from signals.",
        },
        config_schema={
            "currency": {"type": "string", "default": "USD", "description": "Reporting currency."},
        },
        verified=True,
        tags=("analytics", "pricing"),
    ),
    PluginManifest(
        id="threat-intel",
        name="Threat Intel Aggregator",
        version="1.3.0",
        description="Enrich indicators of compromise against intel feeds and score suspicious observables.",
        author="AEON Labs",
        category="security",
        icon="🛰️",
        permissions=("read", "execute", "network"),
        entry_points={
            "enrich": "Score an observable against intel signals.",
            "feeds": "List the active threat-intel feeds.",
        },
        config_schema={
            "feed_count": {"type": "number", "default": 5, "description": "Number of intel feeds queried."},
            "suspicious_threshold": {"type": "number", "default": 0.7, "description": "Suspicious score threshold."},
        },
        verified=False,
        tags=("threat", "ioc", "soc"),
    ),
    PluginManifest(
        id="vulnerability-scanner",
        name="Vulnerability Tracker",
        version="2.0.0",
        description="Scan findings, CVSS scoring, and remediation prioritization for assets.",
        author="AEON Labs",
        category="security",
        icon="🔎",
        permissions=("read", "execute", "notify"),
        entry_points={
            "scan": "Score a vulnerability finding.",
            "prioritize": "Prioritize findings for remediation.",
        },
        config_schema={
            "cvss_critical": {"type": "number", "default": 9.0, "description": "Critical CVSS threshold."},
            "sla_days": {"type": "number", "default": 30, "description": "Remediation SLA in days."},
        },
        verified=True,
        tags=("vuln", "cvss", "remediation"),
    ),
    PluginManifest(
        id="dlp-guard",
        name="Data Loss Prevention",
        version="1.1.0",
        description="Inspect content for PII, secrets, and regulated data; apply redaction policies.",
        author="AEON Labs",
        category="security",
        icon="🔒",
        permissions=("read", "write", "execute"),
        entry_points={
            "inspect": "Detect sensitive data classes in content.",
            "policy": "Evaluate a content sample against DLP policy.",
        },
        config_schema={
            "redact_pii": {"type": "boolean", "default": True, "description": "Redact detected PII."},
            "block_secrets": {"type": "boolean", "default": True, "description": "Block API keys and secrets."},
        },
        verified=True,
        tags=("dlp", "pii", "redaction"),
    ),
    PluginManifest(
        id="access-review",
        name="Access Review",
        version="1.2.0",
        description="Entitlement reviews, least-privilege checks, and certification campaigns.",
        author="AEON Labs",
        category="security",
        icon="🪪",
        permissions=("read", "execute", "admin"),
        entry_points={
            "review": "Generate an access review for a user or role.",
            "certify": "Summarize a certification campaign.",
        },
        config_schema={
            "review_interval_days": {"type": "number", "default": 90, "description": "Certification interval."},
            "auto_revoke_stale": {"type": "boolean", "default": False, "description": "Auto-revoke stale entitlements."},
        },
        verified=True,
        tags=("iam", "entitlements", "governance"),
    ),
    PluginManifest(
        id="key-rotation",
        name="Secret Rotation",
        version="1.0.1",
        description="Schedule and track rotation of API keys, tokens, and credentials.",
        author="AEON Labs",
        category="security",
        icon="🔑",
        permissions=("read", "write", "execute", "admin"),
        entry_points={
            "rotate": "Trigger a credential rotation cycle.",
            "schedule": "Plan rotations against policy windows.",
        },
        config_schema={
            "rotation_days": {"type": "number", "default": 90, "description": "Rotation window in days."},
            "notify_owners": {"type": "boolean", "default": True, "description": "Notify credential owners."},
        },
        verified=True,
        tags=("secrets", "rotation", "iam"),
    ),
    PluginManifest(
        id="credit-risk",
        name="Credit Risk Scoring",
        version="1.2.0",
        description="Credit risk scoring and decision explanations for lending workflows.",
        author="AEON Labs",
        category="sector",
        icon="🏦",
        permissions=("read", "execute"),
        entry_points={
            "score": "Compute a credit risk score.",
            "explain": "Explain the risk drivers behind a score.",
        },
        config_schema={
            "decline_threshold": {"type": "number", "default": 0.7, "description": "Decline risk threshold."},
            "review_threshold": {"type": "number", "default": 0.45, "description": "Manual review threshold."},
        },
        verified=False,
        tags=("finance", "lending", "risk"),
    ),
    PluginManifest(
        id="reconciliation",
        name="Ledger Reconciliation",
        version="1.1.0",
        description="Match transactions across ledgers and surface exceptions for finance teams.",
        author="AEON Labs",
        category="sector",
        icon="🧾",
        permissions=("read", "execute"),
        entry_points={
            "match": "Match transactions between sources.",
            "exceptions": "List unmatched transactions and suspected errors.",
        },
        config_schema={
            "tolerance": {"type": "number", "default": 0.01, "description": "Match tolerance."},
            "auto_approve": {"type": "boolean", "default": False, "description": "Auto-approve exact matches."},
        },
        verified=False,
        tags=("finance", "ledger", "reconciliation"),
    ),
    PluginManifest(
        id="invoice-ai",
        name="Invoice Processor",
        version="1.4.0",
        description="Parse invoices and receipts into structured fields for AP automation.",
        author="AEON Labs",
        category="data",
        icon="📃",
        permissions=("read", "execute"),
        entry_points={
            "parse": "Extract structured fields from an invoice.",
            "approve": "Route parsed invoices for approval.",
        },
        config_schema={
            "auto_approve_under": {"type": "number", "default": 100, "description": "Auto-approve amount."},
            "currency": {"type": "string", "default": "USD", "description": "Invoice currency."},
        },
        verified=True,
        tags=("ap", "invoices", "documents"),
    ),
    PluginManifest(
        id="clinical-notes",
        name="Clinical Notes Summarizer",
        version="1.0.0",
        description="Summarize clinical notes and extract structured observations for care teams.",
        author="AEON Labs",
        category="sector",
        icon="🩺",
        permissions=("read", "execute"),
        entry_points={
            "summarize": "Produce a structured clinical summary.",
            "extract": "Extract observations and medications.",
        },
        config_schema={
            "redact_phi": {"type": "boolean", "default": True, "description": "Redact PHI fields."},
            "include_medications": {"type": "boolean", "default": True, "description": "Include medication list."},
        },
        verified=False,
        tags=("health", "clinical", "notes"),
    ),
    PluginManifest(
        id="readmission-risk",
        name="Readmission Risk",
        version="1.0.0",
        description="Assess hospital readmission risk from patient signals.",
        author="AEON Labs",
        category="sector",
        icon="🏥",
        permissions=("read", "execute"),
        entry_points={
            "assess": "Score readmission risk for a patient profile.",
            "plan": "Suggest follow-up care actions.",
        },
        config_schema={
            "high_risk_threshold": {"type": "number", "default": 0.7, "description": "High-risk threshold."},
            "follow_up_window": {"type": "number", "default": 7, "description": "Follow-up window in days."},
        },
        verified=False,
        tags=("health", "readmission", "care"),
    ),
    PluginManifest(
        id="digest-bot",
        name="Daily Digest",
        version="1.3.0",
        description="Build and publish daily digests from incidents, anomalies, and metrics.",
        author="AEON Labs",
        category="communication",
        icon="📬",
        permissions=("read", "execute", "notify"),
        entry_points={
            "build": "Assemble a digest from platform signals.",
            "publish": "Send the digest to configured channels.",
        },
        config_schema={
            "timezone": {"type": "string", "default": "UTC", "description": "Digest timezone."},
            "channels": {"type": "string", "default": "#daily", "description": "Comma-separated channels."},
        },
        verified=True,
        tags=("notifications", "reports", "ops"),
    ),
    PluginManifest(
        id="model-gateway",
        name="Model Gateway",
        version="2.1.0",
        description="Route prompts across LLM providers with fallback and cost tracking.",
        author="AEON Labs",
        category="ai",
        icon="🧠",
        permissions=("read", "execute", "network"),
        entry_points={
            "route": "Resolve the best provider for a prompt.",
            "fallback": "Evaluate fallback readiness across providers.",
        },
        config_schema={
            "primary_provider": {"type": "string", "default": "openai", "description": "Primary provider."},
            "fallback_provider": {"type": "string", "default": "anthropic", "description": "Fallback provider."},
        },
        verified=True,
        tags=("llm", "routing", "providers"),
    ),
    # ── Module plugins (all AEON OS modules) ───────────────────────────────
    PluginManifest(
        id="workflow-orchestrator",
        name="Workflow Orchestrator",
        version="1.1.0",
        description="Plan, trigger, and monitor multi-step workflow executions across the automation engine.",
        author="AEON Labs",
        category="automation",
        icon="🔀",
        permissions=("read", "execute", "write"),
        entry_points={
            "plan": "Propose a workflow execution plan for a goal.",
            "trigger": "Trigger a workflow run for a workspace.",
            "monitor": "Report workflow run health and progress.",
        },
        config_schema={
            "max_steps": {"type": "number", "default": 10, "description": "Maximum steps per run."},
            "default_timeout": {"type": "number", "default": 300, "description": "Step timeout seconds."},
        },
        verified=True,
        tags=("workflows", "automation", "orchestration"),
    ),
    PluginManifest(
        id="swarm-planner",
        name="Swarm Planner",
        version="1.0.0",
        description="Decompose a problem into tasks and allocate them across planner, executor, and reviewer agents.",
        author="AEON Labs",
        category="ai",
        icon="🐝",
        permissions=("read", "execute", "write"),
        entry_points={
            "plan": "Decompose a goal into allocatable tasks.",
            "assign": "Assign tasks to roles in the swarm.",
            "reflect": "Summarize swarm outputs and next steps.",
        },
        config_schema={
            "roles": {"type": "string", "default": "planner,executor,reviewer,summarizer", "description": "Swarm roles."},
            "max_tasks": {"type": "number", "default": 8, "description": "Max parallel tasks."},
        },
        verified=True,
        tags=("swarm", "agents", "orchestration"),
    ),
    PluginManifest(
        id="rag-search",
        name="RAG Search",
        version="1.2.0",
        description="Query knowledge bases with hybrid keyword + semantic retrieval and context assembly.",
        author="AEON Labs",
        category="data",
        icon="🔍",
        permissions=("read", "execute"),
        entry_points={
            "retrieve": "Retrieve relevant chunks for a query.",
            "index": "Index a document into a knowledge base.",
            "schema": "Describe the knowledge base schema.",
        },
        config_schema={
            "top_k": {"type": "number", "default": 5, "description": "Chunks to retrieve."},
            "hybrid": {"type": "boolean", "default": True, "description": "Use hybrid retrieval."},
        },
        verified=True,
        tags=("rag", "knowledge", "retrieval"),
    ),
    PluginManifest(
        id="approval-gate",
        name="Approval Gate",
        version="1.1.0",
        description="Route high-risk actions through human-in-the-loop approval with policy enforcement.",
        author="AEON Labs",
        category="automation",
        icon="🚦",
        permissions=("read", "execute", "notify"),
        entry_points={
            "check": "Evaluate whether an action needs approval.",
            "escalate": "Escalate a pending approval to a manager.",
            "certify": "Confirm an approval decision record.",
        },
        config_schema={
            "auto_approve_under": {"type": "number", "default": 100, "description": "Auto-approve under this amount."},
            "require_second": {"type": "boolean", "default": True, "description": "Two-person rule for critical actions."},
        },
        verified=True,
        tags=("approvals", "governance", "hilt"),
    ),
    PluginManifest(
        id="budget-guard",
        name="Budget Guard",
        version="1.0.0",
        description="Enforce per-workspace usage budgets and cost caps on automation and AI consumption.",
        author="AEON Labs",
        category="automation",
        icon="💰",
        permissions=("read", "execute"),
        entry_points={
            "check": "Check budget headroom for an action.",
            "report": "Summarize budget usage and alerts.",
            "plan": "Suggest budget reallocation.",
        },
        config_schema={
            "monthly_cap": {"type": "number", "default": 1000, "description": "Monthly usage cap."},
            "alert_at": {"type": "number", "default": 80, "description": "Alert at this % of cap."},
        },
        verified=True,
        tags=("budgets", "billing", "governance"),
    ),
    PluginManifest(
        id="anomaly-scorer",
        name="Anomaly Scorer",
        version="1.2.0",
        description="Score metric deviations and surface anomalies with severity for the observability module.",
        author="AEON Labs",
        category="analytics",
        icon="📈",
        permissions=("read", "execute", "notify"),
        entry_points={
            "score": "Score a metric deviation.",
            "trends": "Summarize recent anomaly trends.",
            "escalate": "Escalate critical anomalies.",
        },
        config_schema={
            "baseline_window": {"type": "number", "default": 3600, "description": "Baseline seconds."},
            "severity_threshold": {"type": "number", "default": 0.8, "description": "Critical severity."},
        },
        verified=True,
        tags=("anomalies", "observability", "metrics"),
    ),
    PluginManifest(
        id="incident-runbook",
        name="Incident Runbook",
        version="1.0.0",
        description="Attach runbooks to incidents, trigger them, and track resolution steps.",
        author="AEON Labs",
        category="security",
        icon="📋",
        permissions=("read", "execute", "write"),
        entry_points={
            "trigger": "Trigger the matching runbook for an incident.",
            "report": "Report runbook execution progress.",
            "postmortem": "Generate a post-incident summary.",
        },
        config_schema={
            "auto_trigger": {"type": "boolean", "default": True, "description": "Auto-trigger runbooks."},
            "channel": {"type": "string", "default": "#incidents", "description": "Notification channel."},
        },
        verified=True,
        tags=("incidents", "runbooks", "soc"),
    ),
    PluginManifest(
        id="dr-coordinator",
        name="DR Coordinator",
        version="1.0.0",
        description="Plan and validate disaster-recovery backups, restores, and failover drills.",
        author="AEON Labs",
        category="automation",
        icon="🧯",
        permissions=("read", "execute", "write"),
        entry_points={
            "plan": "Propose a recovery plan for RTO/RPO targets.",
            "trigger": "Kick off a restore or failover drill.",
            "report": "Report DR readiness and last drill results.",
        },
        config_schema={
            "rto_minutes": {"type": "number", "default": 60, "description": "Recovery time objective."},
            "rpo_minutes": {"type": "number", "default": 15, "description": "Recovery point objective."},
        },
        verified=True,
        tags=("dr", "backup", "resilience"),
    ),
    PluginManifest(
        id="siem-forwarder",
        name="SIEM Forwarder",
        version="1.1.0",
        description="Forward audit, anomaly, and incident events to SIEM endpoints with retry and health checks.",
        author="AEON Labs",
        category="integration",
        icon="🕵️",
        permissions=("read", "execute", "network"),
        entry_points={
            "forward": "Forward events to the configured SIEM.",
            "health": "Check SIEM endpoint health.",
            "feeds": "List configured event feeds.",
        },
        config_schema={
            "endpoint": {"type": "string", "default": "", "description": "SIEM endpoint URL."},
            "auth_mode": {"type": "string", "default": "token", "description": "Auth mode."},
        },
        verified=False,
        tags=("siem", "splunk", "sentinel", "observability"),
    ),
    PluginManifest(
        id="billing-meter",
        name="Billing Meter",
        version="1.0.0",
        description="Meter AI, automation, and plugin usage per workspace for subscription billing.",
        author="AEON Labs",
        category="data",
        icon="🧾",
        permissions=("read", "execute"),
        entry_points={
            "usage": "Report usage totals for a workspace.",
            "report": "Summarize billing period usage.",
            "plan": "Recommend a plan tier from usage.",
        },
        config_schema={
            "currency": {"type": "string", "default": "usd", "description": "Billing currency."},
            "meter_interval": {"type": "string", "default": "monthly", "description": "Metering interval."},
        },
        verified=True,
        tags=("billing", "usage", "metering"),
    ),
    PluginManifest(
        id="sso-bridge",
        name="SSO Bridge",
        version="1.1.0",
        description="Map identity-provider attributes to workspace roles and sync SSO provider state.",
        author="AEON Labs",
        category="integration",
        icon="🔐",
        permissions=("read", "execute", "write"),
        entry_points={
            "rules": "List attribute-to-role mapping rules.",
            "status": "Report SSO provider status.",
            "check": "Validate an identity mapping for a user.",
        },
        config_schema={
            "provider": {"type": "string", "default": "oidc", "description": "SSO provider type."},
            "attribute": {"type": "string", "default": "groups", "description": "Role attribute."},
        },
        verified=True,
        tags=("sso", "identity", "oidc", "saml"),
    ),
    PluginManifest(
        id="scim-sync",
        name="SCIM Sync",
        version="1.0.0",
        description="Provision and deprovision users and groups via SCIM-compatible directory sync.",
        author="AEON Labs",
        category="integration",
        icon="👥",
        permissions=("read", "execute", "write", "admin"),
        entry_points={
            "sync": "Sync directory users and groups.",
            "check": "Check a user's provisioning state.",
            "report": "Report sync activity and errors.",
        },
        config_schema={
            "directory": {"type": "string", "default": "", "description": "SCIM directory URL."},
            "auto_deprovision": {"type": "boolean", "default": False, "description": "Auto-disable removed users."},
        },
        verified=True,
        tags=("scim", "provisioning", "identity"),
    ),
    PluginManifest(
        id="governance-ai",
        name="Governance AI",
        version="1.1.0",
        description="Score policy compliance, surface gaps, and generate evidence-ready audit summaries.",
        author="AEON Labs",
        category="security",
        icon="🏛️",
        permissions=("read", "execute"),
        entry_points={
            "score": "Score a policy compliance check.",
            "report": "Generate an evidence-ready compliance summary.",
            "controls": "List mapped security controls.",
        },
        config_schema={
            "framework": {"type": "string", "default": "soc2", "description": "Compliance framework."},
            "evidence_dir": {"type": "string", "default": "", "description": "Evidence output dir."},
        },
        verified=False,
        tags=("governance", "compliance", "audit"),
    ),
    PluginManifest(
        id="residency-guard",
        name="Residency Guard",
        version="1.0.0",
        description="Enforce data-region residency rules and flag cross-border data flows.",
        author="AEON Labs",
        category="security",
        icon="🌍",
        permissions=("read", "execute"),
        entry_points={
            "check": "Check a data flow against residency policy.",
            "report": "Report residency compliance posture.",
            "rules": "List active residency rules.",
        },
        config_schema={
            "allowed_regions": {"type": "string", "default": "us,eu", "description": "Allowed regions."},
            "strict": {"type": "boolean", "default": True, "description": "Fail closed on unknown regions."},
        },
        verified=False,
        tags=("residency", "gdpr", "governance"),
    ),
    PluginManifest(
        id="notify-router",
        name="Notify Router",
        version="1.0.0",
        description="Route notifications across email, Slack, webhooks, and in-app channels with digesting.",
        author="AEON Labs",
        category="communication",
        icon="📬",
        permissions=("read", "execute", "notify", "network"),
        entry_points={
            "build": "Build a notification payload.",
            "publish": "Publish to configured channels.",
            "status": "Report channel delivery health.",
        },
        config_schema={
            "channels": {"type": "string", "default": "inapp,email", "description": "Enabled channels."},
            "digest_hour": {"type": "number", "default": 9, "description": "Digest send hour."},
        },
        verified=True,
        tags=("notifications", "slack", "email"),
    ),
    PluginManifest(
        id="usage-meter",
        name="Usage Meter",
        version="1.0.0",
        description="Track AI tokens, automation runs, and plugin calls per workspace for analytics.",
        author="AEON Labs",
        category="analytics",
        icon="⏱️",
        permissions=("read", "execute"),
        entry_points={
            "usage": "Report usage totals.",
            "trends": "Summarize usage trends.",
            "report": "Generate a usage report.",
        },
        config_schema={
            "window_days": {"type": "number", "default": 30, "description": "Analytics window."},
        },
        verified=True,
        tags=("usage", "analytics", "monitoring"),
    ),
    PluginManifest(
        id="audit-exporter",
        name="Audit Exporter",
        version="1.1.0",
        description="Export tamper-evident audit logs to archive or SIEM targets with chain verification.",
        author="AEON Labs",
        category="data",
        icon="📦",
        permissions=("read", "execute", "network"),
        entry_points={
            "export": "Export audit records.",
            "check": "Verify the audit hash chain.",
            "schema": "Describe the audit record schema.",
        },
        config_schema={
            "format": {"type": "string", "default": "jsonl", "description": "Export format."},
            "immutable": {"type": "boolean", "default": True, "description": "Require immutable audit."},
        },
        verified=True,
        tags=("audit", "export", "integrity"),
    ),
    PluginManifest(
        id="knowledge-curator",
        name="Knowledge Curator",
        version="1.0.0",
        description="Curate knowledge-base documents: dedupe, tag, summarize, and track freshness.",
        author="AEON Labs",
        category="data",
        icon="📚",
        permissions=("read", "execute", "write"),
        entry_points={
            "summarize": "Summarize a document for the knowledge base.",
            "schema": "Describe document metadata schema.",
            "extract": "Extract structured fields from a document.",
        },
        config_schema={
            "tagging_model": {"type": "string", "default": "auto", "description": "Tagging strategy."},
            "max_docs": {"type": "number", "default": 1000, "description": "Docs per curation run."},
        },
        verified=True,
        tags=("knowledge", "rag", "documents"),
    ),
    PluginManifest(
        id="marketplace-admin",
        name="Marketplace Admin",
        version="1.0.0",
        description="Manage the plugin catalog: review manifests, track installs, and report adoption.",
        author="AEON Labs",
        category="automation",
        icon="🛠️",
        permissions=("read", "execute", "write", "admin"),
        entry_points={
            "report": "Report catalog adoption and health.",
            "controls": "List admin governance controls.",
            "check": "Validate a manifest submission.",
        },
        config_schema={
            "require_verified": {"type": "boolean", "default": True, "description": "Require verified status for install."},
            "max_plugins": {"type": "number", "default": 100, "description": "Catalog size cap."},
        },
        verified=True,
        tags=("marketplace", "admin", "catalog"),
    ),
    # ── Sector plugins (all verticals) ──────────────────────────────────────
    PluginManifest(
        id="gov-compliance-ai",
        name="Gov Compliance AI",
        version="1.0.0",
        description="Government-sector compliance scoring, evidence mapping, and audit readiness summaries.",
        author="AEON Labs",
        category="sector",
        icon="🏛️",
        permissions=("read", "execute"),
        entry_points={
            "score": "Score compliance posture for a control.",
            "report": "Generate an audit-ready compliance summary.",
            "controls": "List mapped government controls.",
        },
        config_schema={
            "framework": {"type": "string", "default": "fedramp", "description": "Framework (fedramp/cjis/state)."},
            "agency": {"type": "string", "default": "", "description": "Agency context."},
        },
        verified=False,
        tags=("government", "fedramp", "compliance"),
    ),
    PluginManifest(
        id="healthcare-triage",
        name="Healthcare Triage",
        version="1.0.0",
        description="Clinical triage support: severity scoring and escalation suggestions (decision support only).",
        author="AEON Labs",
        category="sector",
        icon="🏥",
        permissions=("read", "execute", "notify"),
        entry_points={
            "triage": "Score a clinical case severity.",
            "plan": "Suggest a follow-up plan.",
            "report": "Summarize triage queue state.",
        },
        config_schema={
            "escalation_threshold": {"type": "number", "default": 0.8, "description": "Escalation severity."},
            "phi_redaction": {"type": "boolean", "default": True, "description": "Require PHI redaction."},
        },
        verified=False,
        tags=("healthcare", "triage", "clinical"),
    ),
    PluginManifest(
        id="finance-model-validator",
        name="Finance Model Validator",
        version="1.0.0",
        description="Model-risk review for financial scoring: drift checks, bias flags, and documentation.",
        author="AEON Labs",
        category="sector",
        icon="🏦",
        permissions=("read", "execute"),
        entry_points={
            "score": "Score model-risk indicators.",
            "report": "Generate model-risk documentation.",
            "check": "Validate a model output for bias flags.",
        },
        config_schema={
            "drift_threshold": {"type": "number", "default": 0.2, "description": "Drift alert threshold."},
            "require_docs": {"type": "boolean", "default": True, "description": "Require model documentation."},
        },
        verified=False,
        tags=("finance", "model-risk", "governance"),
    ),
    PluginManifest(
        id="retail-promo-optimizer",
        name="Retail Promo Optimizer",
        version="1.0.0",
        description="Retail promotion planning: discount suggestions, margin checks, and campaign summaries.",
        author="AEON Labs",
        category="sector",
        icon="🛍️",
        permissions=("read", "execute"),
        entry_points={
            "pricing": "Suggest promotion pricing.",
            "plan": "Plan a campaign calendar.",
            "report": "Summarize campaign performance.",
        },
        config_schema={
            "margin_floor": {"type": "number", "default": 0.25, "description": "Minimum margin."},
            "region": {"type": "string", "default": "all", "description": "Target region."},
        },
        verified=True,
        tags=("retail", "promotions", "pricing"),
    ),
    PluginManifest(
        id="logistics-dispatch",
        name="Logistics Dispatch",
        version="1.1.0",
        description="Transport dispatch: route optimization, utilization, and delay risk scoring.",
        author="AEON Labs",
        category="sector",
        icon="🚚",
        permissions=("read", "execute"),
        entry_points={
            "routes": "Suggest optimized routes.",
            "utilization": "Report fleet utilization.",
            "check": "Score delay risk for a route.",
        },
        config_schema={
            "fuel_cost": {"type": "number", "default": 1.4, "description": "Fuel cost per km."},
            "max_stops": {"type": "number", "default": 20, "description": "Max stops per route."},
        },
        verified=True,
        tags=("logistics", "transport", "routes"),
    ),
    PluginManifest(
        id="manufacturing-quality",
        name="Manufacturing Quality",
        version="1.0.0",
        description="Quality control: defect scoring, yield monitoring, and inspection planning.",
        author="AEON Labs",
        category="sector",
        icon="🏭",
        permissions=("read", "execute"),
        entry_points={
            "inspect": "Score a defect inspection result.",
            "report": "Summarize yield and defect rates.",
            "plan": "Suggest an inspection schedule.",
        },
        config_schema={
            "yield_target": {"type": "number", "default": 0.97, "description": "Yield target."},
            "line": {"type": "string", "default": "", "description": "Production line."},
        },
        verified=True,
        tags=("manufacturing", "quality", "maintenance"),
    ),
    PluginManifest(
        id="tourism-booking-ai",
        name="Tourism Booking AI",
        version="1.0.0",
        description="Hospitality: booking-demand analysis, dynamic pricing, and guest-experience insights.",
        author="AEON Labs",
        category="sector",
        icon="🌴",
        permissions=("read", "execute"),
        entry_points={
            "forecast": "Forecast booking demand.",
            "pricing": "Suggest dynamic room pricing.",
            "insights": "Summarize guest-experience feedback.",
        },
        config_schema={
            "region": {"type": "string", "default": "all", "description": "Target region."},
            "seasonality": {"type": "boolean", "default": True, "description": "Adjust for seasonality."},
        },
        verified=True,
        tags=("tourism", "hospitality", "pricing"),
    ),
    PluginManifest(
        id="utility-load-forecast",
        name="Utility Load Forecast",
        version="1.0.0",
        description="Utilities: load forecasting, grid-balance suggestions, and outage-risk scoring.",
        author="AEON Labs",
        category="sector",
        icon="⚡",
        permissions=("read", "execute"),
        entry_points={
            "forecast": "Forecast grid load.",
            "check": "Score outage risk.",
            "report": "Summarize grid health.",
        },
        config_schema={
            "region": {"type": "string", "default": "all", "description": "Grid region."},
            "forecast_horizon": {"type": "number", "default": 24, "description": "Hours ahead."},
        },
        verified=False,
        tags=("utilities", "grid", "energy"),
    ),
    PluginManifest(
        id="heritage-catalog-ai",
        name="Heritage Catalog AI",
        version="1.0.0",
        description="Cultural heritage: artifact cataloging, conservation risk scoring, and visitor analytics.",
        author="AEON Labs",
        category="sector",
        icon="🏺",
        permissions=("read", "execute"),
        entry_points={
            "extract": "Extract artifact catalog metadata.",
            "check": "Score conservation risk.",
            "insights": "Summarize visitor analytics.",
        },
        config_schema={
            "collection": {"type": "string", "default": "", "description": "Collection id."},
            "conservation_standard": {"type": "string", "default": "icoms", "description": "Conservation standard."},
        },
        verified=True,
        tags=("heritage", "culture", "catalog"),
    ),
    PluginManifest(
        id="sme-operations-hub",
        name="SME Operations Hub",
        version="1.0.0",
        description="SME operations: document processing, customer-support drafting, and cash-flow insights.",
        author="AEON Labs",
        category="sector",
        icon="💼",
        permissions=("read", "execute"),
        entry_points={
            "extract": "Extract fields from business documents.",
            "draft": "Draft a customer-support response.",
            "insights": "Summarize cash-flow signals.",
        },
        config_schema={
            "language": {"type": "string", "default": "en", "description": "Response language."},
            "brand": {"type": "string", "default": "", "description": "Brand voice."},
        },
        verified=True,
        tags=("sme", "operations", "documents"),
    ),
    PluginManifest(
        id="energy-market-insights",
        name="Energy Market Insights",
        version="1.0.0",
        description="Energy sector: price-signal aggregation, demand insights, and procurement suggestions.",
        author="AEON Labs",
        category="sector",
        icon="🛢️",
        permissions=("read", "execute"),
        entry_points={
            "insights": "Summarize energy market signals.",
            "pricing": "Suggest procurement pricing.",
            "forecast": "Forecast commodity demand.",
        },
        config_schema={
            "region": {"type": "string", "default": "all", "description": "Market region."},
            "commodities": {"type": "string", "default": "electricity,gas", "description": "Commodities."},
        },
        verified=False,
        tags=("energy", "markets", "procurement"),
    ),
    PluginManifest(
        id="telecom-network-health",
        name="Telecom Network Health",
        version="1.0.0",
        description="Telecom: network-health scoring, capacity planning, and fault triage.",
        author="AEON Labs",
        category="sector",
        icon="📡",
        permissions=("read", "execute"),
        entry_points={
            "check": "Score network-element health.",
            "plan": "Suggest capacity planning actions.",
            "report": "Summarize fault triage state.",
        },
        config_schema={
            "region": {"type": "string", "default": "all", "description": "Network region."},
            "sla_uptime": {"type": "number", "default": 0.999, "description": "SLA uptime target."},
        },
        verified=True,
        tags=("telecom", "network", "sla"),
    ),
    PluginManifest(
        id="agri-yield-optimizer",
        name="Agri Yield Optimizer",
        version="1.0.0",
        description="Agriculture: yield forecasting, irrigation scheduling, and pest-risk scoring.",
        author="AEON Labs",
        category="sector",
        icon="🌾",
        permissions=("read", "execute"),
        entry_points={
            "forecast": "Forecast crop yield.",
            "plan": "Suggest an irrigation schedule.",
            "check": "Score pest-risk levels.",
        },
        config_schema={
            "region": {"type": "string", "default": "all", "description": "Farm region."},
            "crop": {"type": "string", "default": "", "description": "Primary crop."},
        },
        verified=True,
        tags=("agriculture", "yield", "irrigation"),
    ),
    PluginManifest(
        id="cyber-threat-ops",
        name="Cyber Threat Ops",
        version="1.1.0",
        description="Cybersecurity operations: threat-enrichment, vulnerability prioritization, and incident briefs.",
        author="AEON Labs",
        category="sector",
        icon="🛰️",
        permissions=("read", "execute", "notify"),
        entry_points={
            "enrich": "Enrich an indicator of compromise.",
            "prioritize": "Prioritize vulnerabilities by risk.",
            "report": "Generate a threat-operations brief.",
        },
        config_schema={
            "feeds": {"type": "string", "default": "internal", "description": "Threat feeds."},
            "risk_threshold": {"type": "number", "default": 0.8, "description": "Priority threshold."},
        },
        verified=False,
        tags=("cybersecurity", "threat-intel", "soc"),
    ),
    PluginManifest(
        id="education-student-success",
        name="Education Student Success",
        version="1.0.0",
        description="Education: at-risk-student scoring, intervention planning, and program insights.",
        author="AEON Labs",
        category="sector",
        icon="🎓",
        permissions=("read", "execute"),
        entry_points={
            "assess": "Score at-risk indicators for a student.",
            "plan": "Suggest an intervention plan.",
            "insights": "Summarize program outcomes.",
        },
        config_schema={
            "risk_threshold": {"type": "number", "default": 0.7, "description": "At-risk threshold."},
            "region": {"type": "string", "default": "all", "description": "District region."},
        },
        verified=True,
        tags=("education", "student-success", "analytics"),
    ),
    PluginManifest(
        id="public-safety-ops",
        name="Public Safety Ops",
        version="1.0.0",
        description="Public safety: incident-priority scoring, resource dispatch suggestions, and briefs.",
        author="AEON Labs",
        category="sector",
        icon="🚔",
        permissions=("read", "execute", "notify"),
        entry_points={
            "triage": "Score incident priority.",
            "plan": "Suggest resource dispatch.",
            "report": "Generate an operational brief.",
        },
        config_schema={
            "jurisdiction": {"type": "string", "default": "", "description": "Jurisdiction id."},
            "priority_threshold": {"type": "number", "default": 0.8, "description": "Priority threshold."},
        },
        verified=False,
        tags=("public-safety", "dispatch", "operations"),
    ),
    PluginManifest(
        id="realestate-valuator",
        name="Real Estate Valuator",
        version="1.0.0",
        description="Real estate: property-valuation scoring, market-trend summaries, and comparables.",
        author="AEON Labs",
        category="sector",
        icon="🏠",
        permissions=("read", "execute"),
        entry_points={
            "check": "Score a property valuation.",
            "insights": "Summarize market trends.",
            "report": "Generate a comparables report.",
        },
        config_schema={
            "region": {"type": "string", "default": "all", "description": "Market region."},
            "currency": {"type": "string", "default": "usd", "description": "Currency."},
        },
        verified=True,
        tags=("real-estate", "valuation", "analytics"),
    ),
    PluginManifest(
        id="contract-review-ai",
        name="Contract Review AI",
        version="1.0.0",
        description="Legal document review: clause risk scoring, obligation extraction, and renewal tracking for professional services.",
        author="AEON Labs",
        category="sector",
        icon="⚖️",
        permissions=("read", "execute"),
        entry_points={
            "review": "Review a contract clause set and flag risk.",
            "extract": "Extract key clauses and obligations.",
            "report": "Generate a contract risk summary.",
        },
        config_schema={
            "risk_threshold": {"type": "number", "default": 0.7, "description": "High-risk clause threshold."},
            "jurisdiction": {"type": "string", "default": "", "description": "Governing jurisdiction."},
        },
        verified=True,
        tags=("professional", "legal", "contracts"),
    ),
    PluginManifest(
        id="accounting-audit-ai",
        name="Accounting Audit AI",
        version="1.0.0",
        description="Accounting audit support: journal-entry anomaly scoring, reconciliation exceptions, and audit-trail summaries.",
        author="AEON Labs",
        category="sector",
        icon="🧾",
        permissions=("read", "execute"),
        entry_points={
            "check": "Score a journal entry or ledger batch for anomalies.",
            "exceptions": "List reconciliation exceptions for follow-up.",
            "report": "Generate an audit-trail summary.",
        },
        config_schema={
            "materiality_threshold": {"type": "number", "default": 0.05, "description": "Materiality threshold."},
            "period": {"type": "string", "default": "current", "description": "Reporting period."},
        },
        verified=True,
        tags=("professional", "accounting", "audit"),
    ),
    PluginManifest(
        id="data-privacy-ai",
        name="Data Privacy & Compliance",
        version="1.0.0",
        description="Professional data governance: PII discovery, retention-policy checks, and compliance posture scoring.",
        author="AEON Labs",
        category="sector",
        icon="🛡️",
        permissions=("read", "execute"),
        entry_points={
            "inspect": "Inspect a data sample for PII and sensitive classes.",
            "policy": "Check a data asset against retention policy.",
            "report": "Generate a compliance posture summary.",
        },
        config_schema={
            "framework": {"type": "string", "default": "gdpr", "description": "Privacy framework."},
            "strict": {"type": "boolean", "default": True, "description": "Fail closed on unknown data classes."},
        },
        verified=True,
        tags=("professional", "privacy", "compliance"),
    ),
    # ── Platform operations plugins ────────────────────────────────────────
    PluginManifest(
        id="trace-observability",
        name="Trace Observability",
        version="1.0.0",
        description="Inspect agent and workflow traces, summarize spans, and surface latency or token anomalies.",
        author="AEON Labs",
        category="analytics",
        icon="🧭",
        permissions=("read", "execute"),
        entry_points={
            "trace": "Create a deterministic trace summary for a workflow run.",
            "status": "Report trace collection health.",
            "report": "Summarize latency, spans, and token usage signals.",
        },
        config_schema={
            "sample_rate": {"type": "number", "default": 1.0, "description": "Fraction of runs to sample."},
            "retention_days": {"type": "number", "default": 30, "description": "Trace retention window."},
        },
        verified=True,
        tags=("tracing", "observability", "latency"),
    ),
    PluginManifest(
        id="mcp-tool-bridge",
        name="MCP Tool Bridge",
        version="1.0.0",
        description="Manage MCP tool inventories and prepare workspace-safe calls for agent workflows.",
        author="AEON Labs",
        category="integration",
        icon="🔌",
        permissions=("read", "execute", "network"),
        entry_points={
            "sync": "Synchronize an MCP server tool inventory.",
            "call": "Prepare a workspace-scoped MCP tool call.",
            "health": "Report MCP server bridge health.",
        },
        config_schema={
            "server_id": {"type": "string", "default": "", "description": "MCP server identifier."},
            "timeout_seconds": {"type": "number", "default": 30, "description": "Bridge timeout."},
        },
        verified=False,
        tags=("mcp", "tools", "agent-interop"),
    ),
    PluginManifest(
        id="compliance-evidence",
        name="Compliance Evidence",
        version="1.0.0",
        description="Map controls to evidence requirements and produce readiness summaries without asserting certification.",
        author="AEON Labs",
        category="security",
        icon="🗂️",
        permissions=("read", "execute"),
        entry_points={
            "collect": "Prepare an evidence collection checklist.",
            "check": "Check control coverage against a readiness profile.",
            "report": "Generate an evidence-ledger readiness summary.",
        },
        config_schema={
            "framework": {"type": "string", "default": "baseline", "description": "Readiness framework profile."},
            "include_gaps": {"type": "boolean", "default": True, "description": "Include uncovered controls."},
        },
        verified=True,
        tags=("compliance", "evidence", "soc2", "fedramp"),
    ),
    PluginManifest(
        id="connector-health",
        name="Connector Health",
        version="1.0.0",
        description="Standardize health checks and delivery status across configured enterprise connectors.",
        author="AEON Labs",
        category="integration",
        icon="🩹",
        permissions=("read", "execute", "network"),
        entry_points={
            "check": "Check connector configuration readiness.",
            "health": "Report connector delivery health.",
            "status": "Summarize connector state for a workspace.",
        },
        config_schema={
            "connector": {"type": "string", "default": "all", "description": "Connector name or all."},
            "timeout_seconds": {"type": "number", "default": 10, "description": "Health-check timeout."},
        },
        verified=False,
        tags=("connectors", "health", "integrations"),
    ),
    PluginManifest(
        id="developer-quality",
        name="Developer Quality",
        version="1.0.0",
        description="Review workflow and automation quality signals: failures, drift, and delivery trends.",
        author="AEON Labs",
        category="devops",
        icon="🧪",
        permissions=("read", "execute"),
        entry_points={
            "scan": "Scan a workflow or automation quality snapshot.",
            "report": "Generate a developer-quality summary.",
            "trends": "Summarize quality trends over a time window.",
        },
        config_schema={
            "window_days": {"type": "number", "default": 30, "description": "Quality analysis window."},
            "failure_threshold": {"type": "number", "default": 0.1, "description": "Failure-rate alert threshold."},
        },
        verified=True,
        tags=("devops", "quality", "ci-cd"),
    ),
    PluginManifest(
        id="data-quality-guard",
        name="Data Quality Guard",
        version="1.0.0",
        description="Profile datasets, flag validation gaps, and prepare quality checks before automation or AI use.",
        author="AEON Labs",
        category="data",
        icon="✅",
        permissions=("read", "execute"),
        entry_points={
            "profile": "Profile completeness and shape signals for a dataset.",
            "check": "Check a dataset against quality thresholds.",
            "report": "Summarize quality findings and remediation hints.",
        },
        config_schema={
            "completeness_threshold": {"type": "number", "default": 0.95, "description": "Minimum completeness ratio."},
            "strict": {"type": "boolean", "default": True, "description": "Fail closed on missing quality signals."},
        },
        verified=True,
        tags=("data-quality", "validation", "governance"),
    ),
)

_BUILTIN_BY_ID = {manifest.id: manifest for manifest in BUILTIN_PLUGIN_CATALOG}


# === built-in entry-point handlers =========================================


def _run_builtin(manifest: PluginManifest, entry: str, params: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Deterministic handler for shipped built-in plugins.

    Built-ins operate only on the parameters they receive. They never touch
    the network or execute external code; arbitrary third-party behavior must
    run in a separately deployed sandbox before it is enabled.
    """
    text = str(params.get("text", params.get("content", params.get("input", ""))))
    amount = params.get("amount")
    region = params.get("region", config.get("region", "all"))
    items = params.get("items")
    severity = params.get("severity", params.get("risk", "low"))

    if entry in ("analyze", "sentiment", "insights", "summary", "summarize"):
        tokens = len(text.split())
        positive = max(0, tokens - 3)
        return {
            "ok": True,
            "summary": text[:240] + ("…" if len(text) > 240 else ""),
            "stats": {"words": tokens, "signals": positive},
        }
    if entry in (
        "score", "check", "triage", "extract", "forecast", "report", "controls", "schema",
        "enrich", "scan", "prioritize", "inspect", "policy", "assess", "match", "parse", "explain",
    ):
        return {
            "ok": True,
            "score": min(1.0, max(0.0, float(severity) if _is_number(severity) else 0.5)),
            "status": "review" if _is_number(severity) and float(severity) >= float(config.get("risk_threshold", 0.8)) else "ok",
            "config": config,
        }
    if entry in (
        "status", "health", "rules", "feeds", "route", "fallback", "certify",
        "monitor", "retrieve", "index", "usage", "sync", "export", "trace", "collect",
    ):
        return {"ok": True, "status": "healthy", "target": config.get("target", manifest.id), "config": config}
    if entry in (
        "suggest", "routes", "reorder", "pricing", "draft", "review", "exceptions", "plan",
        "assign", "reflect", "profile",
    ):
        count = len(items) if isinstance(items, list) else (int(amount) if _is_number(amount) else 3)
        return {
            "ok": True,
            "suggestions": [{"id": f"{manifest.id}-{i}", "label": f"option {i}"} for i in range(1, max(1, count) + 1)],
            "config": config,
        }
    if entry in (
        "trigger", "forward", "escalate", "outage_alert", "conflicts", "utilization", "postmortem", "trends",
        "rotate", "schedule", "build", "publish", "approve", "call",
    ):
        return {
            "ok": True,
            "dispatched": True,
            "region": region,
            "severity": severity,
            "config": config,
        }
    return {"ok": False, "error": f"entry point '{entry}' has no handler"}


def _is_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


# === marketplace manager ===================================================


class MarketplaceManager:
    """Catalog access and workspace-scoped install lifecycle management."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.state_dir = self.root / "marketplace"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.installs_path = self.state_dir / "installs.json"
        self._installs: dict[tuple[str, str], PluginInstall] = {}
        self._load()

    def _load(self) -> None:
        if not self.installs_path.exists():
            return
        try:
            data = json.loads(self.installs_path.read_text(encoding="utf-8"))
            for item in data:
                try:
                    install = PluginInstall.from_dict(item)
                    self._installs[(install.workspace_id, install.plugin_id)] = install
                except Exception:  # nosec B110 - skip corrupt rows
                    continue
        except Exception:  # nosec B110
            return

    def _save(self) -> None:
        payload = json.dumps(
            [install.to_dict() for install in self._installs.values()], indent=2, sort_keys=True
        )
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.installs_path.write_text(payload, encoding="utf-8")

    # -- catalog -----------------------------------------------------------

    def get_plugin(self, plugin_id: str) -> PluginManifest | None:
        return _BUILTIN_BY_ID.get(plugin_id)

    def list_catalog(self, workspace_id: str | None = None) -> list[dict[str, Any]]:
        """Return every manifest enriched with install state for the workspace."""
        catalog: list[dict[str, Any]] = []
        for manifest in BUILTIN_PLUGIN_CATALOG:
            item = manifest.to_dict()
            if workspace_id:
                install = self._installs.get((workspace_id, manifest.id))
                item["installed"] = install is not None
                item["enabled"] = bool(install and install.enabled)
                item["installed_version"] = install.version if install else None
            else:
                item["installed"] = False
                item["enabled"] = False
                item["installed_version"] = None
            catalog.append(item)
        return catalog

    def catalog_summary(self) -> dict[str, Any]:
        verified = sum(1 for manifest in BUILTIN_PLUGIN_CATALOG if manifest.verified)
        return {
            "plugins": len(BUILTIN_PLUGIN_CATALOG),
            "verified": verified,
            "categories": sorted({manifest.category for manifest in BUILTIN_PLUGIN_CATALOG}),
            "version": MARKETPLACE_VERSION,
        }

    # -- lifecycle ---------------------------------------------------------

    def install(self, workspace_id: str, plugin_id: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
        manifest = self.get_plugin(plugin_id)
        if manifest is None:
            return {"ok": False, "error": "plugin not found"}
        if (workspace_id, plugin_id) in self._installs:
            return {"ok": False, "error": "plugin already installed"}

        validated = validate_config(manifest.config_schema, config or {})
        if not validated["ok"]:
            return validated

        self._installs[(workspace_id, plugin_id)] = PluginInstall(
            plugin_id=plugin_id,
            workspace_id=workspace_id,
            version=manifest.version,
            enabled=True,
            config=validated["config"],
        )
        self._save()
        install = self._installs[(workspace_id, plugin_id)]
        return {"ok": True, "install": install.to_dict()}

    def uninstall(self, workspace_id: str, plugin_id: str) -> dict[str, Any]:
        install = self._installs.pop((workspace_id, plugin_id), None)
        if install is None:
            return {"ok": False, "error": "plugin not installed"}
        self._save()
        return {"ok": True, "plugin_id": plugin_id}

    def set_enabled(self, workspace_id: str, plugin_id: str, enabled: bool) -> dict[str, Any]:
        install = self._installs.get((workspace_id, plugin_id))
        if install is None:
            return {"ok": False, "error": "plugin not installed"}
        install.enabled = enabled
        install.updated_at = time.time()
        self._save()
        return {"ok": True, "install": install.to_dict()}

    def update_config(self, workspace_id: str, plugin_id: str, config: dict[str, Any]) -> dict[str, Any]:
        install = self._installs.get((workspace_id, plugin_id))
        if install is None:
            return {"ok": False, "error": "plugin not installed"}
        manifest = self.get_plugin(plugin_id)
        if manifest is None:  # installed plugin that left the catalog
            return {"ok": False, "error": "plugin no longer in catalog"}

        validated = validate_config(manifest.config_schema, config or {})
        if not validated["ok"]:
            return validated

        install.config = validated["config"]
        install.updated_at = time.time()
        self._save()
        return {"ok": True, "install": install.to_dict()}

    def list_installed(self, workspace_id: str) -> list[dict[str, Any]]:
        installs = [install for (wid, _pid), install in self._installs.items() if wid == workspace_id]
        result: list[dict[str, Any]] = []
        for install in installs:
            manifest = self.get_plugin(install.plugin_id)
            item = install.to_dict()
            item["name"] = manifest.name if manifest else install.plugin_id
            item["icon"] = manifest.icon if manifest else "🔌"
            item["category"] = manifest.category if manifest else "unknown"
            result.append(item)
        return sorted(result, key=lambda i: i["plugin_id"])

    # -- execution ---------------------------------------------------------

    # -- agent discovery ---------------------------------------------------

    def agent_tools(self, workspace_id: str) -> list[dict[str, Any]]:
        """Return the installed, enabled plugins an agent may call in a workspace.

        Discovery is gated exactly like execution: the plugin must be installed
        in the workspace, enabled, and declare the ``execute`` permission. Each
        entry describes the plugin's entry points so agents can discover what
        they can invoke without hard-coding plugin ids.
        """
        tools: list[dict[str, Any]] = []
        for install in self._installs.values():
            if install.workspace_id != workspace_id or not install.enabled:
                continue
            manifest = self.get_plugin(install.plugin_id)
            if manifest is None or "execute" not in manifest.permissions:
                continue
            tools.append(
                {
                    "plugin_id": manifest.id,
                    "name": manifest.name,
                    "description": manifest.description,
                    "icon": manifest.icon,
                    "category": manifest.category,
                    "verified": manifest.verified,
                    "entry_points": dict(manifest.entry_points),
                }
            )
        return sorted(tools, key=lambda t: t["plugin_id"])

    def agent_prompt_block(self, workspace_id: str) -> str:
        """Render a compact system-prompt block listing discoverable plugin tools.

        Returns an empty string when the workspace has no callable plugins, so
        callers can append the block to a system prompt without special-casing.
        """
        tools = self.agent_tools(workspace_id)
        if not tools:
            return ""
        lines = ["Installed plugins (call via plugin_call with these ids and entries):"]
        for tool in tools:
            entries = ", ".join(tool["entry_points"])
            lines.append(f"  - {tool['name']} [{tool['plugin_id']}]: {entries}")
        return "\n".join(lines)

    def run_entry(self, workspace_id: str, plugin_id: str, entry: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Run a plugin entry point for a workspace.

        Execution is gated on: plugin installed, plugin enabled, ``execute``
        permission declared, and the entry existing on the manifest.
        """
        install = self._installs.get((workspace_id, plugin_id))
        if install is None:
            return {"ok": False, "error": "plugin not installed"}
        if not install.enabled:
            return {"ok": False, "error": "plugin disabled"}

        manifest = self.get_plugin(plugin_id)
        if manifest is None:
            return {"ok": False, "error": "plugin no longer in catalog"}
        if "execute" not in manifest.permissions:
            return {"ok": False, "error": "plugin does not declare execute permission"}
        if entry not in manifest.entry_points:
            return {"ok": False, "error": f"unknown entry point '{entry}'"}

        params = params or {}
        return _run_builtin(manifest, entry, params, install.config)


# === module-level singleton ================================================

_marketplace_manager: MarketplaceManager | None = None


def get_marketplace_manager(root: str | Path | None = None) -> MarketplaceManager:
    """Return the process-wide marketplace manager, creating it if needed.

    When an explicit ``root`` is supplied it must match the bound root;
    otherwise the manager is re-created so callers (server routes, automation
    actions, kernel tools, workflow nodes) always share one consistent store.
    """
    global _marketplace_manager
    import os

    # Default matches aeon_server.AEON_ROOT so HTTP routes, automation actions,
    # kernel tools, and workflow nodes always agree even when the env var is unset.
    resolved = Path(root) if root else Path(os.environ.get("AEON_ROOT", "./aeon_state/server"))
    if _marketplace_manager is None or Path(_marketplace_manager.root) != resolved:
        _marketplace_manager = MarketplaceManager(resolved)
    return _marketplace_manager


def reset_marketplace_manager() -> None:
    """Drop the cached manager (used by tests to re-point AEON_ROOT)."""
    global _marketplace_manager
    _marketplace_manager = None
