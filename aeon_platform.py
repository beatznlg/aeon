"""
AEON OS — Platform Foundation
=============================

The universal, multi-tenant core that lets one AEON instance serve many
companies without forking the codebase.

Architecture
------------
::

                    AEON OS
                       |
          ┌────────────▼────────────┐
          │      AEON PLATFORM      │
          └────────────┬────────────┘
                       |
       ┌───────────────┼────────────────┐
       │               │                │
       ▼               ▼                ▼
 TENANT ENGINE    MODULE ENGINE    CONNECTOR ENGINE
       │               │                │
       └───────────────┼────────────────┘
                       |
                 AEON DATA MODEL
                       |
                  AEON BRAIN

* **Tenant engine** — every configuration object is scoped by ``workspace_id``
  (a tenant is a workspace). No object exists without tenant context.
* **Module engine** — a universal catalog of modules (Core / Business / AI).
  A tenant simply activates the modules it needs.
* **Connector engine** — every external system (Sage, Microsoft 365, Indigo,
  Xero, …) implements the same contract: ``authenticate``, ``connect``,
  ``discover``, ``fetch``, ``normalize``, ``sync``, ``webhook``,
  ``health_check``, ``disconnect``.
* **Universal data model** — canonical entities (``Invoice``, ``Project``,
  ``Person``, …) so the AI speaks one language regardless of the source
  system: ``Sage Invoice → AEON Invoice``.
* **Industry packs** — AEON Core stays universal; sectors (Engineering,
  Restaurant, Services, Retail) are packs of modules + connectors + defaults.
* **Configuration engine** — per-tenant ``tenant_config`` JSON
  (company, industry, currency, country, modules, connectors). Onboarding a
  company is writing a config, never code.

AG Group is the reference engineering/construction tenant: a *configuration*
on top of this universal core, not a fork.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# ──────────────────────────────────────────────────────────────────────
# Module Engine — universal module catalog
# ──────────────────────────────────────────────────────────────────────
MODULE_CATEGORIES = ("core", "business", "ai")

MODULE_CATALOG: tuple[dict[str, Any], ...] = (
    # ── Core (always available, cannot be disabled) ────────────────────
    {"id": "identity", "name": "Identity", "icon": "👤", "category": "core", "required": True,
     "description": "Users, roles, sessions and tenant-scoped access control."},
    {"id": "permissions", "name": "Permissions", "icon": "🔐", "category": "core", "required": True,
     "description": "Granular RBAC and per-tenant permission grants."},
    {"id": "audit", "name": "Audit", "icon": "📜", "category": "core", "required": True,
     "description": "Immutable audit trail of every action per tenant."},
    {"id": "notifications", "name": "Notifications", "icon": "🔔", "category": "core", "required": True,
     "description": "In-app, email and webhook notifications."},
    {"id": "ai", "name": "AI", "icon": "🧠", "category": "core", "required": True,
     "description": "The AEON Brain: model gateway, AI ledger and tool framework."},
    {"id": "documents", "name": "Documents", "icon": "📄", "category": "core", "required": True,
     "description": "Universal document store with RAG-ready knowledge bases."},
    {"id": "workflows", "name": "Workflows", "icon": "🔀", "category": "core", "required": True,
     "description": "Visual workflow engine for tenant automations."},
    # ── Business modules ───────────────────────────────────────────────
    {"id": "finance", "name": "Finance", "icon": "💰", "category": "business", "required": False,
     "description": "Invoices, payments, budgets and financial analytics."},
    {"id": "hr", "name": "HR", "icon": "👥", "category": "business", "required": False,
     "description": "Employees, contracts, timesheets and workforce data."},
    {"id": "projects", "name": "Projects", "icon": "📋", "category": "business", "required": False,
     "description": "Projects, tasks, milestones, budgets and margins."},
    {"id": "crm", "name": "CRM", "icon": "🤝", "category": "business", "required": False,
     "description": "Customers, leads, deals and pipelines."},
    {"id": "procurement", "name": "Procurement", "icon": "🛒", "category": "business", "required": False,
     "description": "Suppliers, purchase orders and sourcing."},
    {"id": "inventory", "name": "Inventory", "icon": "📦", "category": "business", "required": False,
     "description": "Stock, warehouses, reorder points and valuation."},
    {"id": "sales", "name": "Sales", "icon": "🛍️", "category": "business", "required": False,
     "description": "Orders, quotes and revenue operations."},
    {"id": "operations", "name": "Operations", "icon": "⚙️", "category": "business", "required": False,
     "description": "Day-to-day operational tasks and checklists."},
    {"id": "analytics", "name": "Analytics", "icon": "📊", "category": "business", "required": False,
     "description": "Dashboards, reports and tenant KPIs."},
    # ── AI modules ─────────────────────────────────────────────────────
    {"id": "ai-assistant", "name": "AI Assistant", "icon": "💬", "category": "ai", "required": False,
     "description": "Tenant-aware chat with access to its modules and data."},
    {"id": "ai-agents", "name": "AI Agents", "icon": "🤖", "category": "ai", "required": False,
     "description": "Autonomous agents with tenant-scoped tools."},
    {"id": "forecasting", "name": "Forecasting", "icon": "📈", "category": "ai", "required": False,
     "description": "Predictive analytics for demand, revenue and capacity."},
    {"id": "risk-engine", "name": "Risk Engine", "icon": "⚠️", "category": "ai", "required": False,
     "description": "Risk scoring, alerts and mitigation workflows."},
    {"id": "automation", "name": "Automation", "icon": "🤖", "category": "ai", "required": False,
     "description": "AI-triggered automations and intelligent actions."},
)

_CORE_MODULE_IDS = tuple(m["id"] for m in MODULE_CATALOG if m["category"] == "core")
_MODULE_MAP = {m["id"]: m for m in MODULE_CATALOG}

# ──────────────────────────────────────────────────────────────────────
# Connector Engine — universal connector contract
# ──────────────────────────────────────────────────────────────────────
#: The universal contract every connector implements.
CONNECTOR_CONTRACT = (
    "authenticate", "connect", "discover", "fetch", "normalize",
    "sync", "webhook", "health_check", "disconnect",
)

CONNECTOR_CATALOG: tuple[dict[str, Any], ...] = (
    {"id": "sage", "name": "Sage", "icon": "🧮", "category": "Accounting / ERP",
     "description": "Invoicing, accounting and financials (Sage 50 / Sage Intacct).",
     "required_secrets": ["SAGE_CLIENT_ID", "SAGE_CLIENT_SECRET", "SAGE_REALM_ID"],
     "capabilities": ["authenticate", "connect", "discover", "fetch", "normalize", "sync", "webhook", "health_check", "disconnect"]},
    {"id": "microsoft365", "name": "Microsoft 365", "icon": "🟦", "category": "Productivity",
     "description": "Outlook, SharePoint, Teams, OneDrive and Calendar via Microsoft Graph.",
     "required_secrets": ["MS_GRAPH_TENANT_ID", "MS_GRAPH_CLIENT_ID", "MS_GRAPH_CLIENT_SECRET"],
     "capabilities": ["authenticate", "connect", "discover", "fetch", "normalize", "sync", "webhook", "health_check", "disconnect"]},
    {"id": "indigo", "name": "Indigo", "icon": "🟧", "category": "Project / PMIS",
     "description": "Project management and control data from Indigo.",
     "required_secrets": ["INDIGO_API_KEY", "INDIGO_BASE_URL"],
     "capabilities": ["authenticate", "connect", "discover", "fetch", "normalize", "sync", "health_check", "disconnect"]},
    {"id": "xero", "name": "Xero", "icon": "⬛", "category": "Accounting / ERP",
     "description": "Cloud accounting: invoices, bank feeds and reconciliation.",
     "required_secrets": ["XERO_CLIENT_ID", "XERO_CLIENT_SECRET", "XERO_TENANT_ID"],
     "capabilities": ["authenticate", "connect", "discover", "fetch", "normalize", "sync", "webhook", "health_check", "disconnect"]},
    {"id": "sap", "name": "SAP", "icon": "🟩", "category": "Accounting / ERP",
     "description": "SAP ERP and S/4HANA financial and supply chain data.",
     "required_secrets": ["SAP_BASE_URL", "SAP_CLIENT_ID", "SAP_CLIENT_SECRET"],
     "capabilities": ["authenticate", "connect", "discover", "fetch", "normalize", "sync", "health_check", "disconnect"]},
    {"id": "quickbooks", "name": "QuickBooks", "icon": "🟢", "category": "Accounting / ERP",
     "description": "QuickBooks Online invoices, expenses and reports.",
     "required_secrets": ["QUICKBOOKS_CLIENT_ID", "QUICKBOOKS_CLIENT_SECRET", "QUICKBOOKS_COMPANY_ID"],
     "capabilities": ["authenticate", "connect", "discover", "fetch", "normalize", "sync", "webhook", "health_check", "disconnect"]},
    {"id": "salesforce", "name": "Salesforce", "icon": "☁️", "category": "CRM",
     "description": "Accounts, contacts, opportunities and sales pipelines.",
     "required_secrets": ["SALESFORCE_CLIENT_ID", "SALESFORCE_CLIENT_SECRET", "SALESFORCE_INSTANCE_URL"],
     "capabilities": ["authenticate", "connect", "discover", "fetch", "normalize", "sync", "webhook", "health_check", "disconnect"]},
    {"id": "hubspot", "name": "HubSpot", "icon": "🟠", "category": "CRM",
     "description": "Contacts, deals, marketing and sales engagement.",
     "required_secrets": ["HUBSPOT_API_KEY"],
     "capabilities": ["authenticate", "connect", "discover", "fetch", "normalize", "sync", "webhook", "health_check", "disconnect"]},
    {"id": "workday", "name": "Workday", "icon": "🟣", "category": "HR",
     "description": "Workforce, payroll and human capital data.",
     "required_secrets": ["WORKDAY_BASE_URL", "WORKDAY_CLIENT_ID", "WORKDAY_CLIENT_SECRET"],
     "capabilities": ["authenticate", "connect", "discover", "fetch", "normalize", "sync", "health_check", "disconnect"]},
    {"id": "pos", "name": "POS", "icon": "🏪", "category": "Retail / POS",
     "description": "Point-of-sale sales, refunds and daily reconciliation.",
     "required_secrets": ["POS_API_KEY", "POS_BASE_URL"],
     "capabilities": ["authenticate", "connect", "discover", "fetch", "normalize", "sync", "webhook", "health_check", "disconnect"]},
)

_CONNECTOR_MAP = {c["id"]: c for c in CONNECTOR_CATALOG}

# ──────────────────────────────────────────────────────────────────────
# Universal Data Model — canonical entities
# ──────────────────────────────────────────────────────────────────────
#: canonical entity → canonical fields. ``sources`` lists real systems that
#: normalize into this entity via their connectors.
UNIVERSAL_ENTITIES: tuple[dict[str, Any], ...] = (
    # ── People & Organizations ────────────────────────────────────────
    {"id": "person", "name": "Person", "icon": "👤", "domain": "people", "fields": ["id", "name", "email", "phone", "address"],
     "sources": ["Sage", "Microsoft 365", "Salesforce", "HubSpot", "Workday"]},
    {"id": "organization", "name": "Organization", "icon": "🏢", "domain": "people", "fields": ["id", "name", "legal_name", "vat_number", "address", "country"],
     "sources": ["Sage", "Salesforce", "HubSpot", "Xero"]},
    {"id": "employee", "name": "Employee", "icon": "🪪", "domain": "people", "fields": ["id", "person_id", "employee_no", "department", "job_title", "start_date", "status"],
     "sources": ["Workday", "Microsoft 365", "HR systems"]},
    {"id": "customer", "name": "Customer", "icon": "🤝", "domain": "people", "fields": ["id", "person_id", "organization_id", "segment", "credit_limit"],
     "sources": ["Salesforce", "HubSpot", "Sage", "Xero", "POS"]},
    {"id": "supplier", "name": "Supplier", "icon": "🚚", "domain": "people", "fields": ["id", "organization_id", "category", "payment_terms", "rating"],
     "sources": ["Sage", "SAP", "Procurement systems"]},
    # ── Finance ───────────────────────────────────────────────────────
    {"id": "financial-account", "name": "Financial Account", "icon": "🏦", "domain": "finance", "fields": ["id", "code", "name", "type", "currency", "balance"],
     "sources": ["Sage", "Xero", "QuickBooks", "SAP"]},
    {"id": "invoice", "name": "Invoice", "icon": "🧾", "domain": "finance", "fields": ["id", "number", "organization_id", "customer_id", "issued_at", "due_at", "total", "currency", "status"],
     "sources": ["Sage", "Xero", "QuickBooks", "SAP"]},
    {"id": "payment", "name": "Payment", "icon": "💳", "domain": "finance", "fields": ["id", "invoice_id", "amount", "method", "paid_at", "reference"],
     "sources": ["Sage", "Xero", "QuickBooks", "POS"]},
    {"id": "transaction", "name": "Transaction", "icon": "🔁", "domain": "finance", "fields": ["id", "account_id", "amount", "direction", "occurred_at", "description"],
     "sources": ["Sage", "Xero", "QuickBooks", "SAP", "POS"]},
    # ── Projects ──────────────────────────────────────────────────────
    {"id": "project", "name": "Project", "icon": "📋", "domain": "projects", "fields": ["id", "name", "code", "customer_id", "start_date", "end_date", "budget", "status"],
     "sources": ["Indigo", "Sage", "Engineering PMIS"]},
    {"id": "task", "name": "Task", "icon": "✅", "domain": "projects", "fields": ["id", "project_id", "title", "assignee_id", "due_at", "status"],
     "sources": ["Indigo", "Microsoft 365 (Planner)", "Engineering PMIS"]},
    {"id": "milestone", "name": "Milestone", "icon": "🚩", "domain": "projects", "fields": ["id", "project_id", "name", "target_date", "achieved_at"],
     "sources": ["Indigo", "Engineering PMIS"]},
    {"id": "budget", "name": "Budget", "icon": "🎯", "domain": "projects", "fields": ["id", "project_id", "amount", "spent", "committed", "forecast", "currency"],
     "sources": ["Sage", "SAP", "Indigo"]},
    {"id": "cost", "name": "Cost", "icon": "💸", "domain": "projects", "fields": ["id", "project_id", "category", "amount", "incurred_at", "reference"],
     "sources": ["Sage", "SAP", "Indigo"]},
    # ── Documents & Communication ─────────────────────────────────────
    {"id": "document", "name": "Document", "icon": "📄", "domain": "documents", "fields": ["id", "title", "kind", "owner_id", "stored_at", "uri", "content_hash"],
     "sources": ["Microsoft 365 (SharePoint/OneDrive)", "Sage", "Indigo"]},
    {"id": "email", "name": "Email", "icon": "✉️", "domain": "documents", "fields": ["id", "thread_id", "from", "to", "subject", "sent_at", "body"],
     "sources": ["Microsoft 365 (Outlook)"]},
    {"id": "meeting", "name": "Meeting", "icon": "📅", "domain": "documents", "fields": ["id", "title", "organizer_id", "starts_at", "ends_at", "attendees"],
     "sources": ["Microsoft 365 (Calendar)", "Microsoft Teams"]},
    {"id": "message", "name": "Message", "icon": "💬", "domain": "documents", "fields": ["id", "channel", "sender_id", "sent_at", "content"],
     "sources": ["Microsoft Teams", "Slack"]},
    # ── Commerce ──────────────────────────────────────────────────────
    {"id": "asset", "name": "Asset", "icon": "🏗️", "domain": "commerce", "fields": ["id", "name", "category", "location", "value", "condition"],
     "sources": ["Sage", "SAP", "Indigo (equipment)", "CMMS"]},
    {"id": "product", "name": "Product", "icon": "📦", "domain": "commerce", "fields": ["id", "name", "sku", "unit", "cost_price", "sale_price"],
     "sources": ["POS", "Sage", "Xero", "QuickBooks"]},
    {"id": "order", "name": "Order", "icon": "🛒", "domain": "commerce", "fields": ["id", "number", "customer_id", "placed_at", "total", "status"],
     "sources": ["POS", "Salesforce", "Sage", "Xero"]},
    {"id": "inventory-item", "name": "Inventory Item", "icon": "📊", "domain": "commerce", "fields": ["id", "product_id", "warehouse", "quantity", "reorder_point"],
     "sources": ["POS", "Sage", "SAP"]},
    # ── Events, Risk & Decisions ──────────────────────────────────────
    {"id": "event", "name": "Event", "icon": "📡", "domain": "intelligence", "fields": ["id", "type", "source", "occurred_at", "payload"],
     "sources": ["All connectors", "Webhooks"]},
    {"id": "alert", "name": "Alert", "icon": "🔔", "domain": "intelligence", "fields": ["id", "severity", "title", "entity_id", "raised_at", "status"],
     "sources": ["Risk Engine", "Monitoring", "Connectors"]},
    {"id": "risk", "name": "Risk", "icon": "⚠️", "domain": "intelligence", "fields": ["id", "project_id", "category", "likelihood", "impact", "score", "mitigation"],
     "sources": ["Risk Engine", "Indigo", "Engineering PMIS"]},
    {"id": "decision", "name": "Decision", "icon": "🧭", "domain": "intelligence", "fields": ["id", "title", "made_by", "made_at", "rationale", "status"],
     "sources": ["AI ledger", "Approvals", "Workflows"]},
)

_ENTITY_MAP = {e["id"]: e for e in UNIVERSAL_ENTITIES}

# Simple canonical→source field aliases used by ``normalize_entity``.
_FIELD_ALIASES: dict[str, dict[str, tuple[str, ...]]] = {
    "invoice": {"number": ("invoice_number", "invoice_no", "number"), "total": ("total_amount", "amount", "grand_total"),
                "issued_at": ("invoice_date", "issue_date", "date"), "status": ("state", "payment_status")},
    "project": {"name": ("project_name", "name"), "code": ("project_code", "code"), "budget": ("total_budget", "budget")},
    "person": {"name": ("full_name", "name", "display_name"), "email": ("email_address", "email")},
    "order": {"number": ("order_number", "reference", "number"), "total": ("order_total", "total", "amount")},
}

# ──────────────────────────────────────────────────────────────────────
# Industry Packs — universal Core + sector packs
# ──────────────────────────────────────────────────────────────────────
INDUSTRY_PACKS: tuple[dict[str, Any], ...] = (
    {"id": "core", "name": "AEON Core", "icon": "🧬", "industry": "universal",
     "description": "The universal foundation every tenant gets: identity, permissions, audit, notifications, AI, documents, workflows.",
     "modules": list(_CORE_MODULE_IDS), "connectors": [], "currency": "EUR", "country": "",
     "profile": "general-business", "required": True},
    {"id": "engineering-construction", "name": "Engineering & Construction", "icon": "🏗️", "industry": "engineering",
     "description": "Projects, contracts, labour, equipment, materials, site management, margins, safety and procurement.",
     "modules": ["finance", "projects", "hr", "procurement", "documents", "analytics", "ai-assistant", "risk-engine"],
     "connectors": ["sage", "microsoft365", "indigo"], "currency": "EUR", "country": "MT",
     "profile": "regulated-enterprise",
     "reference_tenant": "AG Group — the first enterprise implementation of the AEON platform."},
    {"id": "restaurant", "name": "Restaurant & Hospitality", "icon": "🍽️", "industry": "restaurant",
     "description": "POS, reservations, inventory, food cost, recipes, labour, purchasing, sales, margins and staff.",
     "modules": ["finance", "hr", "inventory", "sales", "procurement", "analytics", "ai-assistant"],
     "connectors": ["xero", "microsoft365", "pos"], "currency": "EUR", "country": "",
     "profile": "general-business"},
    {"id": "professional-services", "name": "Professional Services", "icon": "🧑‍💼", "industry": "services",
     "description": "Clients, projects, timesheets, billing, expenses, employees, documents and CRM.",
     "modules": ["crm", "projects", "hr", "documents", "analytics", "ai-assistant"],
     "connectors": ["microsoft365", "xero", "salesforce"], "currency": "EUR", "country": "",
     "profile": "general-business"},
    {"id": "retail", "name": "Retail", "icon": "🛍️", "industry": "retail",
     "description": "Sales, inventory, suppliers, pricing, promotions and customer loyalty.",
     "modules": ["finance", "inventory", "sales", "crm", "procurement", "analytics", "ai-assistant"],
     "connectors": ["xero", "quickbooks", "salesforce", "pos"], "currency": "EUR", "country": "",
     "profile": "general-business"},
)

_PACK_MAP = {p["id"]: p for p in INDUSTRY_PACKS}

# ──────────────────────────────────────────────────────────────────────
# Tenant Configuration Engine
# ──────────────────────────────────────────────────────────────────────
DEFAULT_INDUSTRY = "core"
DEFAULT_CURRENCY = "EUR"
DEFAULT_COUNTRY = ""


@dataclass
class TenantConfig:
    """Per-tenant platform configuration — a company, as data, not code."""

    tenant_id: str
    company: str = ""
    industry: str = DEFAULT_INDUSTRY
    currency: str = DEFAULT_CURRENCY
    country: str = DEFAULT_COUNTRY
    modules: tuple[str, ...] = ()
    connectors: tuple[str, ...] = ()
    deployment_mode: str = "cloud"

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "company": self.company,
            "industry": self.industry,
            "currency": self.currency,
            "country": self.country,
            "modules": list(self.modules),
            "connectors": list(self.connectors),
            "deployment_mode": self.deployment_mode,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> TenantConfig:
        return cls(
            tenant_id=str(data.get("tenant_id") or ""),
            company=str(data.get("company") or ""),
            industry=str(data.get("industry") or DEFAULT_INDUSTRY),
            currency=str(data.get("currency") or DEFAULT_CURRENCY),
            country=str(data.get("country") or DEFAULT_COUNTRY),
            modules=tuple(str(m) for m in (data.get("modules") or ())),
            connectors=tuple(str(c) for c in (data.get("connectors") or ())),
            deployment_mode=str(data.get("deployment_mode") or "cloud"),
        )


def _pack_defaults(industry: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return (modules, connectors) implied by an industry pack."""
    pack = _PACK_MAP.get(str(industry or "").strip().lower())
    if not pack or pack.get("required"):
        # Universal core (or unknown pack) → core modules only, no connectors.
        return tuple(_CORE_MODULE_IDS), ()
    return tuple(pack["modules"]), tuple(pack["connectors"])


def validate_module_ids(module_ids: Sequence[str]) -> list[str]:
    """Return unknown module ids (empty list = all valid)."""
    return [m for m in module_ids if m not in _MODULE_MAP]


def validate_connector_ids(connector_ids: Sequence[str]) -> list[str]:
    """Return unknown connector ids (empty list = all valid)."""
    return [c for c in connector_ids if c not in _CONNECTOR_MAP]


class TenantConfigManager:
    """File-backed per-tenant configuration store.

    One JSON file per tenant under ``<AEON_ROOT>/tenant_config/<tenant_id>.json``,
    mirroring the marketplace store. No tenant object ever exists without its
    ``tenant_id`` scope.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.state_dir = self.root / "tenant_config"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, TenantConfig] = {}

    def _path(self, tenant_id: str) -> Path:
        safe = "".join(ch for ch in str(tenant_id or "") if ch.isalnum() or ch in "-_") or "unknown"
        return self.state_dir / f"{safe}.json"

    def _load(self, tenant_id: str) -> TenantConfig | None:
        path = self._path(tenant_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return TenantConfig.from_dict(data)
        except Exception:  # nosec B110 - corrupt config falls back to defaults
            return None

    def get(self, tenant_id: str) -> TenantConfig:
        if tenant_id in self._cache:
            return self._cache[tenant_id]
        stored = self._load(tenant_id)
        config = stored or TenantConfig(tenant_id=tenant_id)
        self._cache[tenant_id] = config
        return config

    def save(self, config: TenantConfig) -> TenantConfig:
        path = self._path(config.tenant_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(config.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        self._cache[config.tenant_id] = config
        return config

    def effective(self, tenant_id: str) -> dict[str, Any]:
        """Return the full effective platform state for a tenant.

        The stored config wins; industry-pack defaults fill anything unset, so
        a brand-new tenant is immediately functional with the universal core.
        """
        config = self.get(tenant_id)
        modules, connectors = _pack_defaults(config.industry)
        if config.modules:
            modules = config.modules
        if config.connectors:
            connectors = config.connectors
        result = dict(config.to_dict())
        result["modules"] = list(modules)
        result["connectors"] = list(connectors)
        result["pack"] = _PACK_MAP.get(config.industry, _PACK_MAP["core"])
        return result

    def set(self, tenant_id: str, *, company: str | None = None, industry: str | None = None,
            currency: str | None = None, country: str | None = None,
            modules: Sequence[str] | None = None, connectors: Sequence[str] | None = None,
            deployment_mode: str | None = None) -> dict[str, Any]:
        """Validate and persist a tenant configuration update."""
        current = self.get(tenant_id)
        if industry is not None:
            industry = str(industry or DEFAULT_INDUSTRY).strip().lower()
            if industry not in _PACK_MAP:
                raise ValueError(f"unknown industry pack: {industry}")
        if modules is not None:
            bad = validate_module_ids(modules)
            if bad:
                raise ValueError(f"unknown modules: {', '.join(bad)}")
        if connectors is not None:
            bad = validate_connector_ids(connectors)
            if bad:
                raise ValueError(f"unknown connectors: {', '.join(bad)}")
        if currency is not None and not str(currency or "").strip():
            raise ValueError("currency must not be empty")
        if deployment_mode is not None and str(deployment_mode or "") not in {"cloud", "hybrid", "on-premise", "air-gapped", "edge"}:
            raise ValueError(f"invalid deployment mode: {deployment_mode}")
        config = TenantConfig(
            tenant_id=tenant_id,
            company=str(company if company is not None else current.company),
            industry=str(industry if industry is not None else current.industry),
            currency=str(currency if currency is not None else current.currency),
            country=str(country if country is not None else current.country),
            modules=tuple(modules) if modules is not None else current.modules,
            connectors=tuple(connectors) if connectors is not None else current.connectors,
            deployment_mode=str(deployment_mode if deployment_mode is not None else current.deployment_mode),
        )
        self.save(config)
        return self.effective(tenant_id)


_manager: TenantConfigManager | None = None


def get_tenant_config_manager(root: str | Path | None = None) -> TenantConfigManager:
    """Return the process-wide tenant config manager (lazily resolved)."""
    global _manager
    if _manager is None:
        from aeon_server import AEON_ROOT

        _manager = TenantConfigManager(root or AEON_ROOT)
    return _manager


def reset_tenant_config_manager() -> None:
    """Drop the singleton (used by tests)."""
    global _manager
    _manager = None


# ──────────────────────────────────────────────────────────────────────
# Universal normalization
# ──────────────────────────────────────────────────────────────────────
def normalize_entity(entity_id: str, source_data: Mapping[str, Any], source: str) -> dict[str, Any]:
    """Map a source record into the canonical AEON entity.

    ``Sage Invoice → AEON Invoice`` and ``Xero Invoice → AEON Invoice`` land on
    the same canonical shape, so the AI never cares which system produced the
    record. Unknown source fields are preserved under ``_raw``.
    """
    entity = _ENTITY_MAP.get(str(entity_id or "").strip().lower())
    if entity is None:
        raise ValueError(f"unknown universal entity: {entity_id}")
    aliases = _FIELD_ALIASES.get(entity["id"], {})
    canonical: dict[str, Any] = {}
    for field_name in entity["fields"]:
        if field_name in source_data:
            canonical[field_name] = source_data[field_name]
            continue
        for alias in aliases.get(field_name, ()):
            if alias in source_data:
                canonical[field_name] = source_data[alias]
                break
    canonical["_entity"] = entity["id"]
    canonical["_source"] = str(source or "unknown")
    raw = {k: v for k, v in source_data.items() if k not in entity["fields"] and k not in {a for aliases2 in aliases.values() for a in aliases2}}
    if raw:
        canonical["_raw"] = raw
    return canonical


# ──────────────────────────────────────────────────────────────────────
# Connector health (simulated contract execution)
# ──────────────────────────────────────────────────────────────────────
def connector_credential_status() -> dict[str, dict[str, Any]]:
    """Report which required secrets exist in the environment (masked).

    Only booleans are exposed — secret values never leave the server.
    """
    status: dict[str, dict[str, Any]] = {}
    for connector in CONNECTOR_CATALOG:
        secrets = list(connector["required_secrets"])
        present = [name for name in secrets if os.environ.get(name)]
        status[connector["id"]] = {
            "required_secrets": secrets,
            "configured": present,
            "missing": [name for name in secrets if name not in present],
            "ready": bool(secrets) and len(present) == len(secrets),
        }
    return status


def connector_health(connector_id: str) -> dict[str, Any]:
    """Run the connector contract's ``health_check`` step.

    Built-in connectors report their contract capabilities and a simulated
    status. Real credentials are never read; production connectors would
    perform an authenticated round-trip.
    """
    connector = _CONNECTOR_MAP.get(str(connector_id or "").strip().lower())
    if connector is None:
        raise ValueError(f"unknown connector: {connector_id}")
    return {
        "ok": True,
        "connector_id": connector["id"],
        "name": connector["name"],
        "status": "operational",
        "contract": list(CONNECTOR_CONTRACT),
        "capabilities": list(connector["capabilities"]),
        "required_secrets": list(connector["required_secrets"]),
        "simulated": True,
        "message": f"{connector['name']} connector implements the universal contract and is ready to authenticate when credentials are configured.",
    }


# ──────────────────────────────────────────────────────────────────────
# Public catalogs
# ──────────────────────────────────────────────────────────────────────
def list_modules(workspace_id: str | None = None) -> list[dict[str, Any]]:
    """Return the universal module catalog with per-tenant activation state."""
    enabled = set()
    if workspace_id:
        try:
            enabled = set(get_tenant_config_manager().get(workspace_id).modules) | set(_CORE_MODULE_IDS)
        except Exception:  # nosec B110 - catalog still renders
            enabled = set(_CORE_MODULE_IDS)
    return [
        dict(m, enabled=m["id"] in enabled)
        for m in MODULE_CATALOG
    ]


def list_connectors(workspace_id: str | None = None) -> list[dict[str, Any]]:
    """Return the connector catalog with per-tenant activation state."""
    enabled = set()
    if workspace_id:
        try:
            enabled = set(get_tenant_config_manager().get(workspace_id).connectors)
        except Exception:  # nosec B110 - catalog still renders
            enabled = set()
    return [dict(c, enabled=c["id"] in enabled) for c in CONNECTOR_CATALOG]


def list_industry_packs() -> list[dict[str, Any]]:
    """Return the industry pack catalog."""
    return [dict(p) for p in INDUSTRY_PACKS]


def list_universal_entities() -> list[dict[str, Any]]:
    """Return the canonical universal data model."""
    return [dict(e) for e in UNIVERSAL_ENTITIES]


# ──────────────────────────────────────────────────────────────────────
# Tenant-aware Brain context
# ──────────────────────────────────────────────────────────────────────
def build_tenant_context_prompt(workspace_id: str) -> str:
    """Build the tenant context fragment the AEON Brain sees on every call.

    The Brain gets its context dynamically: which tenant, which industry
    pack, which modules, which connected systems, which currency. Same Brain
    for every company — only the context changes.
    """
    try:
        effective = get_tenant_config_manager().effective(workspace_id)
    except Exception:  # nosec B110 - context must never break a chat call
        return ""
    company = effective.get("company") or "an AEON tenant"
    pack = effective.get("pack") or {}
    industry = pack.get("name") or effective.get("industry") or "general"
    modules = list(effective.get("modules") or ())
    connector_ids = list(effective.get("connectors") or ())
    connector_names = [
        connector["name"] for connector in CONNECTOR_CATALOG if connector["id"] in connector_ids
    ]
    currency = effective.get("currency") or ""
    country = effective.get("country") or ""
    deployment = effective.get("deployment_mode") or "cloud"
    lines = [
        "AEON TENANT CONTEXT (authoritative for this conversation):",
        f"- Company: {company}",
        f"- Industry pack: {industry}",
        f"- Currency: {currency or 'n/a'} | Country: {country or 'n/a'} | Deployment: {deployment}",
        f"- Enabled modules: {', '.join(modules) or 'none'}",
        f"- Connected systems: {', '.join(connector_names) or 'none'}",
        "Answer strictly within this tenant's enabled modules and connected systems.",
        "If asked about a module or system this tenant does not use, say the tenant does not have it activated.",
    ]
    return "\n".join(lines)


__all__ = [
    "CONNECTOR_CATALOG",
    "CONNECTOR_CONTRACT",
    "INDUSTRY_PACKS",
    "MODULE_CATALOG",
    "TenantConfig",
    "TenantConfigManager",
    "UNIVERSAL_ENTITIES",
    "build_tenant_context_prompt",
    "connector_credential_status",
    "connector_health",
    "get_tenant_config_manager",
    "list_connectors",
    "list_industry_packs",
    "list_modules",
    "list_universal_entities",
    "normalize_entity",
    "reset_tenant_config_manager",
    "validate_connector_ids",
    "validate_module_ids",
]
