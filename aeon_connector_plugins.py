"""Marketplace manifests for AEON's first enterprise connector adapters.

The connector engine owns vendor credentials and live transport. These small,
serializable definitions keep the marketplace catalog modular while allowing
each connector to share the normal workspace-scoped install/config/run
lifecycle. The built-in marketplace runner provides safe deterministic health
and sync-preparation actions until a vendor-specific adapter is configured.
"""

from __future__ import annotations

CONNECTOR_PLUGIN_DEFINITIONS = (
    {
        "id": "sage-connector",
        "name": "Sage Connector",
        "version": "1.0.0",
        "description": "Connect Sage accounting data to AEON Finance and the universal Invoice model.",
        "author": "AEON Labs",
        "category": "integration",
        "icon": "🧮",
        "permissions": ("read", "execute", "network"),
        "entry_points": {
            "health": "Check Sage readiness.",
            "sync": "Prepare a Sage synchronization run.",
            "status": "Summarize Sage connector state.",
        },
        "config_schema": {
            "connector_id": {"type": "string", "default": "sage", "description": "Connector engine id."},
            "sync_entities": {"type": "string", "default": "invoice,transaction,payment", "description": "Comma-separated AEON entities."},
        },
        "verified": False,
        "tags": ("sage", "accounting", "erp", "connector"),
    },
    {
        "id": "microsoft365-connector",
        "name": "Microsoft 365 Connector",
        "version": "1.0.0",
        "description": "Connect Microsoft Graph services to AEON Documents, People, Meetings, and Messages.",
        "author": "AEON Labs",
        "category": "integration",
        "icon": "🟦",
        "permissions": ("read", "execute", "network"),
        "entry_points": {
            "health": "Check Microsoft Graph readiness.",
            "sync": "Prepare a Microsoft 365 synchronization run.",
            "status": "Summarize Microsoft 365 connector state.",
        },
        "config_schema": {
            "connector_id": {"type": "string", "default": "microsoft365", "description": "Connector engine id."},
            "sync_entities": {"type": "string", "default": "person,document,email,meeting,message", "description": "Comma-separated AEON entities."},
        },
        "verified": False,
        "tags": ("microsoft365", "graph", "productivity", "connector"),
    },
    {
        "id": "indigo-shireburn-connector",
        "name": "Indigo by Shireburn Connector",
        "version": "1.0.0",
        "description": "Connect Indigo project controls to AEON Projects, Tasks, Budgets, Costs, and Risks.",
        "author": "AEON Labs",
        "category": "integration",
        "icon": "🟧",
        "permissions": ("read", "execute", "network"),
        "entry_points": {
            "health": "Check Indigo by Shireburn readiness.",
            "sync": "Prepare an Indigo synchronization run.",
            "status": "Summarize Indigo connector state.",
        },
        "config_schema": {
            "connector_id": {"type": "string", "default": "indigo", "description": "Connector engine id."},
            "sync_entities": {"type": "string", "default": "project,task,milestone,budget,cost,risk", "description": "Comma-separated AEON entities."},
        },
        "verified": False,
        "tags": ("indigo", "shireburn", "projects", "construction", "connector"),
    },
    {
        "id": "open-time-clock-connector",
        "name": "Open Time Clock Connector",
        "version": "1.0.0",
        "description": "Connect attendance and time records to AEON Workforce and the universal Time Entry model.",
        "author": "AEON Labs",
        "category": "integration",
        "icon": "⏱️",
        "permissions": ("read", "execute", "network"),
        "entry_points": {
            "health": "Check Open Time Clock readiness.",
            "sync": "Prepare an attendance synchronization run.",
            "status": "Summarize time-clock connector state.",
        },
        "config_schema": {
            "connector_id": {"type": "string", "default": "open-time-clock", "description": "Connector engine id."},
            "sync_entities": {"type": "string", "default": "employee,time-entry", "description": "Comma-separated AEON entities."},
        },
        "verified": False,
        "tags": ("open-time-clock", "workforce", "attendance", "connector"),
    },
    {
        "id": "oisoft-connector",
        "name": "OiSoft Connector",
        "version": "1.0.0",
        "description": "Connect OiSoft workforce operations to AEON Workforce, Employees, and Time Entries.",
        "author": "AEON Labs",
        "category": "integration",
        "icon": "🟪",
        "permissions": ("read", "execute", "network"),
        "entry_points": {
            "health": "Check OiSoft readiness.",
            "sync": "Prepare an OiSoft synchronization run.",
            "status": "Summarize OiSoft connector state.",
        },
        "config_schema": {
            "connector_id": {"type": "string", "default": "oisoft", "description": "Connector engine id."},
            "sync_entities": {"type": "string", "default": "employee,time-entry", "description": "Comma-separated AEON entities."},
        },
        "verified": False,
        "tags": ("oisoft", "workforce", "operations", "connector"),
    },
)
