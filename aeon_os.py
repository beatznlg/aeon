# ============================================================
#  AEON OS — Modular autonomous operating system layer
#  - Built on top of aeon.py kernel (ReflectiveAgent, tools, memory)
#  - Adds WorkspaceManager (multi-tenant isolation)
#  - Adds AppRegistry (installable industry modules)
#  - Adds CyberSecurityModule (beachhead vertical)
#  - Designed for B2B SaaS, fully autonomous mode
# ============================================================

import contextlib
import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from aeon import (
    ROOT as AEON_ROOT,
)

# Import the AEON kernel we already built
from aeon import (
    ReflectiveAgent,
    _register,
    _safe_run,
)
from aeon_db import Database, get_db

# === OS root directory ====================================================
OS_ROOT = Path(os.environ.get("AEON_OS_ROOT", str(AEON_ROOT) + "/os"))
OS_ROOT.mkdir(parents=True, exist_ok=True)


# === WorkspaceManager ===================================================
class WorkspaceManager:
    """
    Multi-tenant workspace isolation for AEON OS.
    Each workspace gets its own state directory, memory, goals, and ledger.

    Phase 0 Foundation: when AEON_DATABASE_URL is configured, workspace
    metadata is also mirrored to Postgres for tenant isolation, RBAC, and
    auditability. File-system storage remains as the runtime state backend
    so existing agents keep working without a migration.
    """
    def __init__(self, root: Path = OS_ROOT, db: Database | None = None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._db = db
        self._tenant = "default"

    @property
    def db(self) -> Database | None:
        if self._db is None and os.environ.get("AEON_DATABASE_URL"):
            with contextlib.suppress(Exception):
                self._db = get_db()
        return self._db

    def _workspace_path(self, workspace_id: str) -> Path:
        safe_id = hashlib.sha256(workspace_id.encode()).hexdigest()[:16]
        return self.root / "workspaces" / safe_id

    def create(self, workspace_id: str, tenant: str = "default") -> Path:
        path = self._workspace_path(workspace_id)
        path.mkdir(parents=True, exist_ok=True)
        meta = {
            "workspace_id": workspace_id,
            "tenant": tenant,
            "created": time.time(),
        }
        (path / "meta.json").write_text(json.dumps(meta))

        # Mirror to DB if available
        if self.db:
            try:
                from aeon_db import Workspace as DBWorkspace
                with self.db.session() as s:
                    existing = s.query(DBWorkspace).filter_by(slug=workspace_id).first()
                    if not existing:
                        ws = DBWorkspace(
                            id=str(workspace_id) if len(str(workspace_id)) == 36 else None,
                            tenant_id=tenant,
                            slug=str(workspace_id),
                            name=str(workspace_id).replace("-", " ").title(),
                        )
                        s.add(ws)
                        s.commit()
            except Exception:  #nosec B110
                pass
        return path

    def exists(self, workspace_id: str) -> bool:
        return self._workspace_path(workspace_id).exists()

    def get(self, workspace_id: str) -> Path:
        if not self.exists(workspace_id):
            self.create(workspace_id)
        return self._workspace_path(workspace_id)

    def list_workspaces(self) -> list[dict[str, Any]]:
        # Prefer DB when available
        if self.db:
            try:
                from aeon_db import Workspace as DBWorkspace
                with self.db.session() as s:
                    rows = s.query(DBWorkspace).all()
                    return [
                        {
                            "workspace_id": r.id,
                            "tenant_id": r.tenant_id,
                            "slug": r.slug,
                            "name": r.name,
                            "plan": r.plan,
                            "created": r.created_at.timestamp() if r.created_at else time.time(),
                        }
                        for r in rows
                    ]
            except Exception:  #nosec B110
                pass
        ws_dir = self.root / "workspaces"
        if not ws_dir.exists():
            return []
        workspaces = []
        for d in ws_dir.iterdir():
            meta_file = d / "meta.json"
            if meta_file.exists():
                try:
                    meta = json.loads(meta_file.read_text())
                    workspaces.append(meta)
                except Exception:  #nosec B110
                    pass
        return workspaces


# === App Definition =====================================================
@dataclass
class AppDefinition:
    id: str
    name: str
    category: str
    description: str
    icon: str
    allowed_tools: list[str]
    default_goals: list[dict[str, Any]]
    color: str = "#8b5cf6"
    status: str = "active"  # active, beta, planned


# === AppRegistry ========================================================
class AppRegistry:
    """
    Registry of installable AEON OS applications / modules.
    Each app defines its tools, goals, and UI color/icon metadata.
    """
    def __init__(self):
        self.apps: dict[str, AppDefinition] = {}
        self._register_defaults()

    def register(self, app: AppDefinition):
        self.apps[app.id] = app

    def get(self, app_id: str) -> AppDefinition | None:
        return self.apps.get(app_id)

    def list_apps(self) -> list[dict[str, Any]]:
        return [asdict(a) for a in self.apps.values()]

    def _register_defaults(self):
        # Cybersecurity beachhead
        self.register(AppDefinition(
            id="cybersecurity",
            name="CyberSecurity",
            category="Security & Compliance",
            description="Autonomous threat intelligence, vulnerability tracking, IP reputation, and compliance monitoring for government and business.",
            icon="🛡️",
            color="#ef4444",
            allowed_tools=[
                "threat_lookup",
                "vuln_scan",
                "ip_reputation",
                "compliance_check",
                "security_news",
                "fetch",
                "search",
            ],
            default_goals=[
                {"title": "Monitor threat landscape and surface critical alerts", "priority": 10},
                {"title": "Track high-severity CVEs affecting client assets", "priority": 9},
                {"title": "Maintain IP reputation watchlist and flag malicious actors", "priority": 8},
                {"title": "Generate compliance posture score for frameworks", "priority": 7},
            ],
        ))

        # Existing retail, manufacturing, professional, tourism (unchanged)
        self.register(AppDefinition(
            id="retail",
            name="Retail & Wholesale",
            category="Commerce",
            description="Intelligent stock forecasting, automated supply chains, and personalized digital storefronts.",
            icon="🛒",
            color="#10b981",
            status="active",
            allowed_tools=[
                "demand_forecast",
                "inventory_optimizer",
                "supplier_risk",
                "price_elasticity",
                "storefront_personalizer",
                "fetch",
                "search",
                "math",
                "api_catalog_search",
            ],
            default_goals=[
                {"title": "Monitor inventory for stockout risks and generate reorder recommendations", "priority": 10},
                {"title": "Forecast high-velocity SKU demand across 30-90 day horizons", "priority": 9},
                {"title": "Track supplier risk and flag delivery disruptions", "priority": 8},
                {"title": "Optimize pricing and personalize storefront offers", "priority": 7},
            ],
        ))
        self.register(AppDefinition(
            id="manufacturing",
            name="Manufacturing & Engineering",
            category="Industry",
            description="Predictive maintenance, automated QC vision systems, and smart logistics.",
            icon="🏭",
            color="#f59e0b",
            status="active",
            allowed_tools=[
                "predictive_maintenance",
                "qc_vision",
                "smart_logistics",
                "fetch",
                "search",
                "math",
            ],
            default_goals=[
                {"title": "Monitor machine telemetry for failure risks and dispatch maintenance", "priority": 10},
                {"title": "Scan QC pipeline for defect spikes and production anomalies", "priority": 9},
                {"title": "Optimize logistics routes and minimize delivery delays", "priority": 8},
            ],
        ))
        self.register(AppDefinition(
            id="professional",
            name="Professional Services",
            category="Services",
            description="Automated legal document parsing, intelligent accounting workflows, and digital data management.",
            icon="📄",
            color="#3b82f6",
            status="active",
            allowed_tools=[
                "legal_doc_parser",
                "smart_accounting",
                "data_manager",
                "fetch",
                "search",
                "math",
            ],
            default_goals=[
                {"title": "Parse incoming contracts and flag high-risk clauses", "priority": 10},
                {"title": "Process invoice queue and surface accounting anomalies", "priority": 9},
                {"title": "Scan data assets for PII and compliance readiness", "priority": 8},
            ],
        ))
        self.register(AppDefinition(
            id="tourism",
            name="Tourism & Hospitality",
            category="Hospitality",
            description="AI-driven booking optimization, dynamic pricing, and automated guest concierge.",
            icon="🏨",
            color="#ec4899",
            status="active",
            allowed_tools=[
                "booking_optimizer",
                "dynamic_pricing",
                "automated_concierge",
                "fetch",
                "search",
                "math",
            ],
            default_goals=[
                {"title": "Maximize occupancy through predictive overbooking", "priority": 10},
                {"title": "Adjust room rates dynamically based on demand signals", "priority": 9},
                {"title": "Triage guest requests and automate concierge responses", "priority": 8},
            ],
        ))

        # === NEW VERTICALS ===
        # Health & Medicine
        self.register(AppDefinition(
            id="health",
            name="Health & Medicine",
            category="Healthcare",
            description="AI-powered diagnostics, patient monitoring, drug interaction checks, and telehealth triage for modern healthcare.",
            icon="🏥",
            color="#06b6d4",
            status="active",
            allowed_tools=[
                "diagnostic_analyzer",
                "health_monitor",
                "drug_interaction_check",
                "medical_literature_search",
                "telehealth_triage",
                "fetch",
                "search",
                "math",
            ],
            default_goals=[
                {"title": "Monitor patient vitals and flag abnormal trends", "priority": 10},
                {"title": "Cross-check medication regimens for adverse interactions", "priority": 9},
                {"title": "Triage incoming telehealth cases by urgency score", "priority": 8},
                {"title": "Search medical literature for treatment evidence", "priority": 7},
            ],
        ))
        # Transport & Logistics
        self.register(AppDefinition(
            id="transport",
            name="Transport & Logistics",
            category="Mobility",
            description="Traffic optimization, fleet scheduling, route planning, and congestion forecasting for smart mobility.",
            icon="🚚",
            color="#f97316",
            status="active",
            allowed_tools=[
                "traffic_optimizer",
                "fleet_scheduler",
                "route_optimizer",
                "congestion_forecast",
                "smart_logistics",
                "fetch",
                "search",
                "math",
            ],
            default_goals=[
                {"title": "Optimize fleet utilization and reduce idle time", "priority": 10},
                {"title": "Re-route deliveries around congestion hot spots", "priority": 9},
                {"title": "Forecast traffic patterns for proactive scheduling", "priority": 8},
                {"title": "Schedule preventive maintenance for fleet vehicles", "priority": 7},
            ],
        ))
        # Finance & Fintech
        self.register(AppDefinition(
            id="finance",
            name="Finance & Fintech",
            category="Financial Services",
            description="AI-driven risk analysis, payment pattern monitoring, market forecasting, fraud detection, and credit scoring.",
            icon="💰",
            color="#22c55e",
            status="active",
            allowed_tools=[
                "risk_assessment",
                "payment_analyzer",
                "market_forecast",
                "fraud_detection",
                "credit_scoring",
                "fetch",
                "search",
                "math",
            ],
            default_goals=[
                {"title": "Assess portfolio risk exposure and VaR metrics", "priority": 10},
                {"title": "Monitor transaction patterns for fraud signals", "priority": 9},
                {"title": "Forecast market trends across major indices", "priority": 8},
                {"title": "Process credit applications with AI scoring model", "priority": 7},
            ],
        ))
        # Tourism & Cultural Heritage (expanded)
        self.register(AppDefinition(
            id="cultural_heritage",
            name="Cultural Heritage",
            category="Culture & Tourism",
            description="Visitor engagement strategies, cultural heritage guides, virtual tour assistance, and exhibition planning.",
            icon="🎭",
            color="#a855f7",
            status="active",
            allowed_tools=[
                "visitor_engagement",
                "cultural_heritage_guide",
                "virtual_tour_guide",
                "exhibition_planner",
                "fetch",
                "search",
                "math",
            ],
            default_goals=[
                {"title": "Engage visitors with personalized cultural recommendations", "priority": 10},
                {"title": "Generate rich cultural heritage content for exhibits", "priority": 9},
                {"title": "Guide virtual tour participants with AI narration", "priority": 8},
                {"title": "Plan exhibition schedules and optimize visitor flow", "priority": 7},
            ],
        ))
        # Utilities & Consumer Services
        self.register(AppDefinition(
            id="utilities",
            name="Utilities & Consumer Services",
            category="Public Sector",
            description="Resource consumption optimization, public service monitoring, waste management, and energy grid oversight.",
            icon="⚡",
            color="#eab308",
            status="active",
            allowed_tools=[
                "resource_optimizer",
                "public_service_monitor",
                "waste_management",
                "energy_grid_monitor",
                "fetch",
                "search",
                "math",
            ],
            default_goals=[
                {"title": "Optimize resource allocation across public services", "priority": 10},
                {"title": "Monitor utility infrastructure for failure risks", "priority": 9},
                {"title": "Track waste management KPIs and recycling rates", "priority": 8},
                {"title": "Balance energy grid load and forecast demand peaks", "priority": 7},
            ],
        ))
        # General SME Tools
        self.register(AppDefinition(
            id="sme",
            name="SME Business Suite",
            category="General Business",
            description="Workflow automation, intelligent document processing, AI-powered customer support, and supply chain analytics for SMEs.",
            icon="🏢",
            color="#14b8a6",
            status="active",
            allowed_tools=[
                "workflow_automator",
                "document_processor",
                "customer_support_bot",
                "supply_chain_analyzer",
                "fetch",
                "search",
                "math",
            ],
            default_goals=[
                {"title": "Automate repetitive business workflows for efficiency", "priority": 10},
                {"title": "Process incoming documents and extract structured data", "priority": 9},
                {"title": "Power AI chatbot for customer self-service", "priority": 8},
                {"title": "Analyze supply chain for bottlenecks and cost savings", "priority": 7},
            ],
        ))


# === Cybersecurity Tools (registered into AEON kernel) ===================

@_register("threat_lookup")
def _tool_threat_lookup(args, root):
    """Query public threat intel for an indicator (IP, hash, domain)."""
    indicator = args.get("indicator", "").strip()
    if not indicator:
        return False, "missing indicator"
    # Use mock data + optionally Abuse.ch MalwareBazaar if API key present
    import os

    import requests
    api_key = os.environ.get("MALWAREBAZAAR_API_KEY")
    if api_key and len(indicator) in (32, 40, 64):
        try:
            r = requests.post(
                "https://mb-api.abuse.ch/api/v1/",
                data={"query": "get_info", "hash": indicator.lower()},
                headers={"Auth-Key": api_key},
                timeout=10,
            )
            if r.status_code == 200:
                return True, json.dumps(r.json(), ensure_ascii=False)[:1000]
        except Exception as e:
            return False, "malwarebazaar err: " + str(e)[:200]
    # Fallback: deterministic mock classification
    threat_type = "unknown"
    if indicator.replace(".", "").isdigit():
        threat_type = "ip_address"
    elif indicator.startswith("http"):
        threat_type = "url"
    elif len(indicator) in (32, 40, 64):
        threat_type = "hash"
    return True, json.dumps({
        "indicator": indicator,
        "type": threat_type,
        "reputation": "suspicious" if hash(indicator) % 3 == 0 else "clean",
        "sources": ["mock_threat_intel"],
        "note": "Live MalwareBazaar requires MALWAREBAZAAR_API_KEY",
    })


@_register("vuln_scan")
def _tool_vuln_scan(args, root):
    """Look up a CVE or query NIST NVD for recent vulnerabilities."""
    cve = args.get("cve", "").strip().upper()
    if cve:
        # Try live NVD API
        import requests
        try:
            r = requests.get(f"https://services.nvd.nist.gov/rest/json/cves/2.0?cveId={cve}", timeout=10)
            if r.status_code == 200:
                data = r.json()
                if data.get("vulnerabilities"):
                    return True, json.dumps(data["vulnerabilities"][0], ensure_ascii=False)[:1200]
        except Exception:  #nosec B110
            pass
        return True, json.dumps({
            "cve": cve,
            "severity": "Medium",
            "summary": f"Mock summary for {cve}: a buffer overflow in example-library allows remote code execution.",
            "note": "Live NVD data unavailable; returning mock.",
        })
    # Recent high-severity mock CVEs
    return True, json.dumps([
        {"cve": "CVE-2024-0001", "severity": "Critical", "summary": "Mock critical RCE"},
        {"cve": "CVE-2024-0002", "severity": "High", "summary": "Mock privilege escalation"},
    ])


@_register("ip_reputation")
def _tool_ip_reputation(args, root):
    """Check reputation of an IP address (mock + GreyNoise if key present)."""
    ip = args.get("ip", "").strip()
    if not ip:
        return False, "missing ip"
    import os

    import requests
    key = os.environ.get("GREYNOISE_API_KEY")
    if key:
        try:
            r = requests.get(f"https://api.greynoise.io/v3/community/{ip}",
                           headers={"key": key}, timeout=10)
            if r.status_code == 200:
                return True, json.dumps(r.json(), ensure_ascii=False)[:1000]
        except Exception:  #nosec B110
            pass
    # Mock fallback
    h = hash(ip) % 10
    return True, json.dumps({
        "ip": ip,
        "noise": h > 6,
        "classification": "malicious" if h > 7 else "benign",
        "last_seen": "2025-07-20",
        "note": "Live GreyNoise requires GREYNOISE_API_KEY",
    })


@_register("compliance_check")
def _tool_compliance_check(args, root):
    """Generate a compliance posture score for a given framework."""
    framework = args.get("framework", "NIST-CSF").upper()
    # Mock scoring based on framework name hash for determinism
    score = 70 + (hash(framework) % 25)
    gaps = [
        "Identity and Access Management policies need review",
        "Logging retention below recommended 12 months",
        "Incident response playbooks not yet automated",
    ]
    return True, json.dumps({
        "framework": framework,
        "score": score,
        "maturity": "Managed" if score >= 80 else "Developing",
        "gaps": gaps,
        "recommendations": [
            "Automate IAM policy review",
            "Extend log retention to 12 months",
            "Connect incident response runbooks",
        ],
    })


@_register("security_news")
def _tool_security_news(args, root):
    """Fetch recent security news / headlines."""
    import requests
    try:
        r = requests.get("https://www.reddit.com/r/netsec/hot.json?limit=5",
                        headers={"User-Agent": "AEON-OS/1.0"}, timeout=10)
        if r.status_code == 200:
            posts = r.json().get("data", {}).get("children", [])[:5]
            return True, json.dumps([{
                "title": p["data"]["title"],
                "url": p["data"]["url"],
            } for p in posts], ensure_ascii=False)
    except Exception:  #nosec B110
        pass
    return True, json.dumps([
        {"title": "Critical OpenSSH vulnerability disclosed", "url": "#"},
        {"title": "New ransomware group targets healthcare sector", "url": "#"},
    ])


# === Retail & Wholesale Tools ===========================================

@_register("demand_forecast")
def _tool_demand_forecast(args, root):
    """Forecast demand for a SKU. args={sku, horizon_days?}."""
    sku = str(args.get("sku", "SKU-001")).strip() or "SKU-001"
    horizon = max(7, min(int(args.get("horizon_days", 30)), 90))
    # Deterministic mock forecast based on SKU hash
    h = hash(sku) % 1000
    base = 50 + (h % 450)
    trend = 1 + (h % 30) / 100.0
    season = 1.15 if horizon >= 30 else 1.0
    projected = int(base * trend * season)
    return True, json.dumps({
        "sku": sku,
        "current_stock": int(base * 0.35),
        "current_daily_sales": round(base / 30.0, 1),
        "horizon_days": horizon,
        "projected_demand": projected,
        "trend": "upward" if trend > 1.12 else "stable" if trend > 0.95 else "downward",
        "seasonality_factor": season,
        "recommended_order_qty": max(0, projected - int(base * 0.35)),
        "confidence": 0.82 + (h % 15) / 100.0,
    }, ensure_ascii=False)


@_register("inventory_optimizer")
def _tool_inventory_optimizer(args, root):
    """Analyze inventory and flag stockouts/overstock."""
    skus = args.get("skus", ["SKU-001", "SKU-042", "SKU-099", "SKU-107"])
    if isinstance(skus, str):
        skus = [s.strip() for s in skus.split(",")]
    alerts = []
    reorder = []
    healthy = []
    for sku in skus:
        h = hash(sku) % 1000
        stock = 10 + (h % 200)
        daily = 1 + (h % 12)
        days = stock // daily
        if days < 7:
            alerts.append({"sku": sku, "status": "stockout_risk", "days_remaining": days})
            reorder.append({"sku": sku, "qty": max(daily * 14 - stock, 20), "supplier": f"Supplier-{h % 5}"})
        elif days > 60:
            healthy.append({"sku": sku, "status": "overstock", "days_supply": days})
        else:
            healthy.append({"sku": sku, "status": "healthy", "days_supply": days})
    return True, json.dumps({
        "alerts": alerts,
        "reorder_recommendations": reorder,
        "healthy": healthy,
        "summary": {
            "total_skus": len(skus),
            "stockout_risks": len(alerts),
            "overstocks": len([h for h in healthy if h["status"] == "overstock"]),
        }
    }, ensure_ascii=False)


@_register("supplier_risk")
def _tool_supplier_risk(args, root):
    """Assess supplier risk score. args={supplier}."""
    supplier = str(args.get("supplier", "Alpha Corp")).strip() or "Alpha Corp"
    h = hash(supplier) % 100
    risk_score = 15 + h  # 15-100-ish but deterministic
    delays = risk_score > 55
    return True, json.dumps({
        "supplier": supplier,
        "risk_score": risk_score,
        "classification": "High Risk" if risk_score > 70 else "Medium Risk" if risk_score > 45 else "Low Risk",
        "on_time_delivery_pct": 100 - (risk_score // 2),
        "recent_delays": delays,
        "recommended_action": "Diversify supplier" if risk_score > 70 else "Monitor closely" if risk_score > 45 else "Maintain relationship",
        "avg_lead_time_days": 3 + (h % 21),
    }, ensure_ascii=False)


@_register("price_elasticity")
def _tool_price_elasticity(args, root):
    """Estimate price elasticity of demand for a product. args={sku, price_change_pct}."""
    sku = str(args.get("sku", "SKU-001")).strip() or "SKU-001"
    price_change = float(args.get("price_change_pct", 10))
    h = hash(sku) % 100
    # Deterministic elasticity: -0.8 to -2.5
    elasticity = -0.8 - ((h % 17) / 10.0)
    projected_demand_change = round(elasticity * price_change, 1)
    return True, json.dumps({
        "sku": sku,
        "price_change_pct": price_change,
        "elasticity": elasticity,
        "projected_demand_change_pct": projected_demand_change,
        "interpretation": "elastic" if abs(elasticity) > 1 else "inelastic",
        "revenue_impact": "increase" if projected_demand_change + price_change > 0 else "decrease",
    }, ensure_ascii=False)


@_register("storefront_personalizer")
def _tool_storefront_personalizer(args, root):
    """Generate personalized product recommendations for a customer segment."""
    segment = str(args.get("segment", "budget_shopper")).strip().lower()
    h = hash(segment) % 100
    categories = {
        "budget_shopper": ["essentials_bundle", "bulk_paper_towels", "store_brand_cereal"],
        "premium_shopper": ["artisan_coffee", "organic_produce_box", "smart_home_kit"],
        "trend_shopper": ["viral_kitchen_gadget", "limited_edition_snack", "trending_beauty"],
        "loyalty_shopper": ["membership_upgrade", "exclusive_wine", "premium_pantry_box"],
    }
    picks = categories.get(segment, categories["budget_shopper"])
    return True, json.dumps({
        "segment": segment,
        "recommended_products": picks,
        "estimated_conversion_lift_pct": 5 + (h % 20),
        "personalization_strategy": f"Show {segment.replace('_', ' ')} offers first; emphasize value and urgency."
    }, ensure_ascii=False)


# === Manufacturing & Engineering Tools ==================================

@_register("predictive_maintenance")
def _tool_predictive_maintenance(args, root):
    """Predict machine failure risk from telemetry. args={machine_id}."""
    machine = str(args.get("machine_id", "CNC-04")).strip() or "CNC-04"
    h = hash(machine) % 100
    risk = 20 + (h % 70)
    temp = 60 + (h % 45)
    vibration = round(0.5 + (h % 20) / 10.0, 1)
    days = max(1, 30 - (risk // 3))
    return True, json.dumps({
        "machine_id": machine,
        "status": "critical" if risk > 75 else "warning" if risk > 50 else "healthy",
        "temp_c": temp,
        "vibration_hz": vibration,
        "failure_risk_pct": risk,
        "days_to_failure": days,
        "recommended_action": "Dispatch technician immediately" if risk > 75 else "Schedule maintenance" if risk > 50 else "Continue monitoring",
    }, ensure_ascii=False)


@_register("qc_vision")
def _tool_qc_vision(args, root):
    """Quality control vision scan for a production batch. args={batch_id}."""
    batch = str(args.get("batch_id", "B-998")).strip() or "B-998"
    h = hash(batch) % 100
    items = 1000 + (h * 15)
    defects = int(items * (0.002 + (h % 15) / 1000.0))
    rate = round(defects / items, 4)
    return True, json.dumps({
        "batch_id": batch,
        "items_scanned": items,
        "defects_found": defects,
        "defect_rate": rate,
        "status": "pass" if rate < 0.005 else "fail",
        "anomaly_type": "surface_scratch" if h % 2 == 0 else "dimensional_deviation",
        "confidence": 0.91 + (h % 8) / 100.0,
    }, ensure_ascii=False)


@_register("smart_logistics")
def _tool_smart_logistics(args, root):
    """Check logistics route status and suggest reroute. args={route_id}."""
    route = str(args.get("route_id", "R-10")).strip() or "R-10"
    h = hash(route) % 100
    delayed = h > 60
    return True, json.dumps({
        "route_id": route,
        "status": "delayed" if delayed else "on_time",
        "delay_reason": "weather" if delayed and h % 2 == 0 else "traffic" if delayed else None,
        "eta_days": 1 + (h % 5) if not delayed else 3 + (h % 4),
        "alternative_route": "Route B" if delayed else None,
        "reroute_cost_usd": 450 if delayed else 0,
        "cargo_value_usd": 50000 + (h * 1000),
    }, ensure_ascii=False)


# === Professional & Technical Services Tools ==============================

@_register("legal_doc_parser")
def _tool_legal_doc_parser(args, root):
    """Parse a legal document and extract risks and obligations. args={document_name}."""
    doc = str(args.get("document_name", "Vendor_NDA.pdf")).strip() or "Vendor_NDA.pdf"
    h = hash(doc) % 100
    risk = "low" if h < 40 else "medium" if h < 75 else "high"
    doc_type = "NDA" if "NDA" in doc else "MSA" if "MSA" in doc else "Contract"
    return True, json.dumps({
        "doc": doc,
        "type": doc_type,
        "risk_score": risk,
        "obligations": ["confidentiality", "non-compete"][:1 + (h % 2)],
        "missing_clauses": ["jurisdiction"] if h % 2 == 0 else [],
        "auto_recommended_action": "Request legal review" if risk == "high" else "Approve with standard terms",
    }, ensure_ascii=False)


@_register("smart_accounting")
def _tool_smart_accounting(args, root):
    """Audit an invoice and match to GL. args={invoice_id}."""
    inv = str(args.get("invoice_id", "INV-102")).strip() or "INV-102"
    h = hash(inv) % 100
    amount = 1000 + (h * 120)
    anomaly = h > 80
    return True, json.dumps({
        "invoice_id": inv,
        "vendor": f"Vendor-{h % 5}",
        "amount": amount,
        "anomalies_detected": anomaly,
        "auto_approved": not anomaly,
        "gl_code": "6000-Software" if h % 2 == 0 else "6100-Services",
        "payment_status": "hold_for_review" if anomaly else "scheduled",
    }, ensure_ascii=False)


@_register("data_manager")
def _tool_data_manager(args, root):
    """Scan a dataset for PII/compliance issues. args={dataset_id}."""
    dataset = str(args.get("dataset_id", "user_dump.csv")).strip() or "user_dump.csv"
    h = hash(dataset) % 100
    pii = h % 80
    return True, json.dumps({
        "dataset": dataset,
        "pii_records_found": pii,
        "redaction_status": "complete" if pii < 30 else "in_progress",
        "compliance": "GDPR-ready" if pii < 30 else "needs_review",
        "retention_days": 365 - h,
        "last_scan": "2025-07-20",
    }, ensure_ascii=False)


# === Tourism & Hospitality Tools =========================================

@_register("booking_optimizer")
def _tool_booking_optimizer(args, root):
    """Optimize overbooking and occupancy for a property. args={property_id}."""
    prop = str(args.get("property_id", "Hotel-Central")).strip() or "Hotel-Central"
    h = hash(prop) % 100
    occupancy = 70 + (h % 25)
    no_shows = 2 + (h % 6)
    overbook = max(0, min(no_shows - 1, 5))
    return True, json.dumps({
        "property": prop,
        "occupancy_pct": occupancy,
        "predictive_no_shows": no_shows,
        "optimal_overbook_qty": overbook,
        "net_expected_occupancy": min(100, occupancy + overbook),
        "recommendation": "Accept 3 more bookings" if overbook > 0 else "Hold inventory",
    }, ensure_ascii=False)


@_register("dynamic_pricing")
def _tool_dynamic_pricing(args, root):
    """Recommend dynamic room price. args={room_type, offset_days?}."""
    room = str(args.get("room_type", "King Suite")).strip() or "King Suite"
    offset = max(0, int(args.get("offset_days", 0)))
    h = hash(room + str(offset)) % 100
    base = 120 + (h % 80)
    multiplier = round(1.0 + (h % 40) / 100.0, 2)
    return True, json.dumps({
        "room": room,
        "date_offset_days": offset,
        "base_price": base,
        "demand_multiplier": multiplier,
        "recommended_price": int(base * multiplier),
        "reason": "Local Tech Conference" if h > 60 else "Weekend demand" if h > 30 else "Standard demand",
    }, ensure_ascii=False)


@_register("automated_concierge")
def _tool_automated_concierge(args, root):
    """Triage a guest request and auto-respond. args={guest_id, request_summary}."""
    guest = str(args.get("guest_id", "G-445")).strip() or "G-445"
    request = str(args.get("request_summary", "dining reservation")).strip().lower()
    h = hash(guest + request) % 100
    sentiments = {0: "positive", 1: "neutral", 2: "negative"}
    sentiment = sentiments.get(h % 3, "neutral")
    intents = ["dining", "housekeeping", "transport", "amenities"]
    intent = intents[h % len(intents)]
    responses = {
        "dining": "Booked at 7PM. Wine pairing available.",
        "housekeeping": "Scheduled for 10AM.",
        "transport": "Taxi arranged for 6:30PM.",
        "amenities": "Pool access extended to 11PM.",
    }
    return True, json.dumps({
        "guest_id": guest,
        "sentiment": sentiment,
        "intent": intent,
        "automated_response": responses.get(intent, "We will assist you shortly."),
        "upsell": "Wine pairing" if intent == "dining" else "Late checkout" if intent == "housekeeping" else None,
        "escalate": sentiment == "negative",
    }, ensure_ascii=False)


# === Health & Medicine Tools ============================================

@_register("diagnostic_analyzer")
def _tool_diagnostic_analyzer(args, root):
    """Analyze symptoms and suggest possible conditions. args={symptoms, age?}."""
    symptoms = str(args.get("symptoms", "fever, cough")).strip() or "fever, cough"
    h = hash(symptoms) % 100
    conditions = [
        {"name": "Upper Respiratory Infection", "probability": 0.35 + (h % 30) / 100.0, "severity": "mild", "action": "Rest and hydration"},
        {"name": "Allergic Rhinitis", "probability": 0.15 + (h % 20) / 100.0, "severity": "mild", "action": "Antihistamines"},
        {"name": "Influenza", "probability": 0.10 + (h % 15) / 100.0, "severity": "moderate", "action": "Antiviral if early"},
    ]
    conditions.sort(key=lambda c: c["probability"], reverse=True)
    return True, json.dumps({
        "analyzed_symptoms": symptoms,
        "possible_conditions": conditions[:3],
        "urgency": "high" if h > 80 else "moderate" if h > 50 else "low",
        "recommendation": "Consult primary care provider" if h > 60 else "Self-care with monitoring",
        "disclaimer": "This is an AI screening tool and not a medical diagnosis. Always consult a healthcare professional.",
    }, ensure_ascii=False)


@_register("health_monitor")
def _tool_health_monitor(args, root):
    """Monitor patient vital trends. args={patient_id, metric?}."""
    patient = str(args.get("patient_id", "P-1001")).strip() or "P-1001"
    metric = str(args.get("metric", "heart_rate")).strip().lower()
    h = hash(patient + metric) % 100
    baseline = {"heart_rate": 72, "blood_pressure_sys": 120, "blood_pressure_dia": 80, "oxygen_sat": 98, "temperature": 37.0}
    current_variance = (h % 20) - 10
    return True, json.dumps({
        "patient_id": patient,
        "metric": metric,
        "baseline": baseline.get(metric, "unknown"),
        "current": baseline.get(metric, 0) + current_variance,
        "trend": "rising" if current_variance > 5 else "falling" if current_variance < -5 else "stable",
        "alert": abs(current_variance) > 8,
        "last_checked": "2025-07-20T14:30:00Z",
    }, ensure_ascii=False)


@_register("drug_interaction_check")
def _tool_drug_interaction_check(args, root):
    """Check potential drug interactions. args={drugs}."""
    drugs_str = str(args.get("drugs", "aspirin, warfarin")).strip() or "aspirin, warfarin"
    drugs = [d.strip().lower() for d in drugs_str.split(",")]
    interactions = []
    known_pairs = [
        (["warfarin", "aspirin"], "Increased bleeding risk — monitor INR closely"),
        (["lisinopril", "potassium"], "Risk of hyperkalemia — check serum potassium"),
        (["metformin", "contrast_dye"], "Risk of lactic acidosis — hold metformin 48h"),
    ]
    for pair, warning in known_pairs:
        if all(d in drugs for d in pair):
            interactions.append({"drugs": pair, "severity": "moderate", "warning": warning})
    return True, json.dumps({
        "medications": drugs,
        "interactions_found": len(interactions),
        "interactions": interactions,
        "recommendation": "Review with pharmacist" if interactions else "No significant interactions predicted",
    }, ensure_ascii=False)


@_register("medical_literature_search")
def _tool_medical_literature_search(args, root):
    """Search medical literature abstracts. args={query}."""
    query = str(args.get("query", "hypertension treatment guidelines")).strip()
    h = hash(query) % 20
    return True, json.dumps({
        "query": query,
        "results": [
            {"title": "Updated Guidelines for Hypertension Management (2025)", "journal": "NEJM", "relevance": 0.95, "doi": "10.1056/NEJMoa2500001"},
            {"title": "Lifestyle Interventions vs Pharmacotherapy in Stage 1 Hypertension", "journal": "JAMA", "relevance": 0.88 - h / 100.0, "doi": "10.1001/jama.2025.0002"},
            {"title": "AI-Assisted Blood Pressure Monitoring in Primary Care", "journal": "The Lancet Digital Health", "relevance": 0.82 - h / 100.0, "doi": "10.1016/S2589-7500(25)00003-9"},
        ],
        "total_found": 2000 + h * 100,
    }, ensure_ascii=False)


@_register("telehealth_triage")
def _tool_telehealth_triage(args, root):
    """Triage a telehealth case by urgency. args={symptoms, age, vitals?}."""
    symptoms = str(args.get("symptoms", "chest pain")).strip()
    age = int(args.get("age", 45))
    h = hash(symptoms + str(age)) % 100
    urgency = "emergent" if h > 80 else "urgent" if h > 50 else "routine"
    return True, json.dumps({
        "symptoms": symptoms,
        "age": age,
        "urgency": urgency,
        "wait_time_minutes": 0 if urgency == "emergent" else 15 if urgency == "urgent" else 60,
        "recommendation": "Call 911 immediately" if urgency == "emergent" else "See provider within 24h" if urgency == "urgent" else "Schedule appointment",
        "telehealth_eligible": urgency != "emergent",
    }, ensure_ascii=False)


# === Transport & Logistics Tools =========================================

@_register("traffic_optimizer")
def _tool_traffic_optimizer(args, root):
    """Optimize traffic signal timing or flow. args={zone, congestion_level?}."""
    zone = str(args.get("zone", "downtown")).strip() or "downtown"
    congestion = int(args.get("congestion_level", 7)) % 10
    h = hash(zone) % 100
    return True, json.dumps({
        "zone": zone,
        "current_congestion": congestion,
        "recommended_timing": {"green_ratio": 1.0 - (congestion / 10.0), "cycle_seconds": 90 + (h % 30)},
        "predicted_improvement": f"{5 + (h % 15)}% reduction in avg wait time",
        "alternative_routes": [f"Route-{i}" for i in range(1, 4)],
        "incident_nearby": h > 75,
    }, ensure_ascii=False)


@_register("fleet_scheduler")
def _tool_fleet_scheduler(args, root):
    """Schedule fleet vehicle assignments. args={vehicles, shifts?}."""
    vehicles = int(args.get("vehicles", 10))
    shifts = int(args.get("shifts", 3))
    h = hash(str(vehicles) + str(shifts)) % 100
    return True, json.dumps({
        "vehicles_available": vehicles,
        "shifts": shifts,
        "vehicles_per_shift": max(1, vehicles // shifts),
        "unallocated": vehicles % shifts,
        "utilization_pct": 70 + (h % 25),
        "recommendation": "Add 2 more vehicles to peak shift" if h > 70 else "Current fleet sufficient",
        "next_maintenance_due": [f"Vehicle-{i}" for i in range(1, 4) if (h + i) % 3 == 0],
    }, ensure_ascii=False)


@_register("route_optimizer")
def _tool_route_optimizer(args, root):
    """Optimize delivery routes. args={stops, depot?}."""
    stops_str = str(args.get("stops", "A,B,C,D,E,F")).strip() or "A,B,C,D,E,F"
    stops = [s.strip() for s in stops_str.split(",")]
    depot = str(args.get("depot", "Warehouse-1")).strip() or "Warehouse-1"
    h = hash("".join(stops)) % 100
    return True, json.dumps({
        "depot": depot,
        "stops": stops,
        "optimal_route": [depot] + stops + [depot],
        "estimated_distance_km": len(stops) * 12 + (h % 20),
        "estimated_time_min": len(stops) * 25 + (h % 15),
        "fuel_cost_est": round(len(stops) * 3.5 + h * 0.2, 2),
        "efficiency_gain": f"{h % 15}% vs current route",
    }, ensure_ascii=False)


@_register("congestion_forecast")
def _tool_congestion_forecast(args, root):
    """Forecast traffic congestion. args={area, hours_ahead?}."""
    area = str(args.get("area", "city_center")).strip()
    hours = min(72, max(1, int(args.get("hours_ahead", 6))))
    h = hash(area) % 100
    return True, json.dumps({
        "area": area,
        "forecast_hours": hours,
        "peak_congestion_time": f"{7 + (h % 4)}:00 - {10 + (h % 3)}:00",
        "peak_level": min(10, 5 + (h % 6)),
        "recommendation": "Avoid peak hours; use alternate routes" if h > 60 else "Normal traffic expected",
        "hourly_forecast": [{"hour": i, "level": min(10, abs(h - i * 7) % 10)} for i in range(0, hours, 2)],
    }, ensure_ascii=False)


# === Finance & Fintech Tools =============================================

@_register("risk_assessment")
def _tool_risk_assessment(args, root):
    """Assess financial risk for a portfolio or asset. args={asset, portfolio_value?}."""
    asset = str(args.get("asset", "S&P 500")).strip()
    portfolio = float(args.get("portfolio_value", 100000))
    h = hash(asset) % 100
    var_95 = round(portfolio * (0.02 + (h % 50) / 1000.0), 2)
    return True, json.dumps({
        "asset": asset,
        "portfolio_value": portfolio,
        "var_95_1d": var_95,
        "var_95_pct": round(var_95 / portfolio * 100, 2),
        "sharpe_estimate": round(0.8 + (h % 60) / 100.0, 2),
        "beta": round(0.5 + (h % 100) / 100.0, 2),
        "risk_rating": "low" if h < 30 else "medium" if h < 65 else "high",
        "diversification_score": min(10, 3 + h // 10),
        "recommendation": "Consider hedging strategies" if h > 70 else "Portfolio is balanced",
    }, ensure_ascii=False)


@_register("payment_analyzer")
def _tool_payment_analyzer(args, root):
    """Analyze payment patterns. args={account_id, days?}."""
    account = str(args.get("account_id", "ACC-1234")).strip()
    days = min(90, max(1, int(args.get("days", 30))))
    h = hash(account) % 100
    return True, json.dumps({
        "account_id": account,
        "period_days": days,
        "total_transactions": 10 + h * 3,
        "total_volume": round(10000 + h * 500, 2),
        "avg_transaction": round(500 + h * 25, 2),
        "top_categories": ["retail", "subscription", "transfer", "utility"][:3],
        "anomaly_count": max(0, h % 5 - 2),
        "spending_trend": "increasing" if h > 60 else "stable" if h > 30 else "decreasing",
    }, ensure_ascii=False)


@_register("market_forecast")
def _tool_market_forecast(args, root):
    """Forecast market trends. args={market, horizon_days?}."""
    market = str(args.get("market", "S&P 500")).strip()
    horizon = min(365, max(1, int(args.get("horizon_days", 30))))
    h = hash(market + str(horizon)) % 100
    return True, json.dumps({
        "market": market,
        "horizon_days": horizon,
        "predicted_direction": "bullish" if h > 55 else "bearish" if h < 30 else "neutral",
        "confidence": 0.55 + (h % 30) / 100.0,
        "key_factors": ["Interest rate expectations", "Earnings season", "Geopolitical risk"],
        "price_target_pct": round((h % 40) - 15, 1),
        "volatility_forecast": "low" if h < 30 else "moderate" if h < 70 else "high",
    }, ensure_ascii=False)


@_register("fraud_detection")
def _tool_fraud_detection(args, root):
    """Detect potentially fraudulent transactions. args={transaction_id, amount, location?}."""
    tx_id = str(args.get("transaction_id", "TXN-5001")).strip()
    amount = float(args.get("amount", 1500))
    location = str(args.get("location", "unknown")).strip().lower()
    h = hash(tx_id) % 100
    fraud_score = h / 100.0
    return True, json.dumps({
        "transaction_id": tx_id,
        "amount": amount,
        "location": location,
        "fraud_score": round(fraud_score, 2),
        "risk_level": "high" if fraud_score > 0.75 else "medium" if fraud_score > 0.4 else "low",
        "flags": [] if fraud_score < 0.4 else ["unusual_location", "rapid_transaction", "high_amount"]
    } | ({"action": "Block and review"} if fraud_score > 0.75 else {"action": "Allow with monitoring"}), ensure_ascii=False)


@_register("credit_scoring")
def _tool_credit_scoring(args, root):
    """Score a credit applicant. args={applicant_id, income, debt, history_years?}."""
    app_id = str(args.get("applicant_id", "APP-200")).strip()
    income = float(args.get("income", 75000))
    debt = float(args.get("debt", 15000))
    max(1, int(args.get("history_years", 5)))
    h = hash(app_id) % 100
    dti = round(debt / max(income, 1), 3)
    score = 300 + (h % 550)  # 300-850 range
    return True, json.dumps({
        "applicant_id": app_id,
        "credit_score": score,
        "rating": "excellent" if score > 750 else "good" if score > 670 else "fair" if score > 580 else "poor",
        "debt_to_income": dti,
        "approval_probability": round((score / 850.0) * (1 - dti / 2), 2),
        "recommended_limit": max(500, int(income * 0.3 * (score / 850.0))),
        "risk_factors": ["High DTI"] if dti > 0.4 else [],
    }, ensure_ascii=False)


# === Tourism & Cultural Heritage Tools ===================================

@_register("visitor_engagement")
def _tool_visitor_engagement(args, root):
    """Generate visitor engagement recommendations. args={venue, visitor_count?}."""
    venue = str(args.get("venue", "National Museum")).strip()
    visitors = int(args.get("visitor_count", 500))
    h = hash(venue) % 100
    strategies = [
        "Interactive AR exhibits for younger audiences",
        "Audio guides in 5 languages with QR codes",
        "Gamified scavenger hunt through permanent collection",
        "Evening cultural performances and storytelling",
    ]
    return True, json.dumps({
        "venue": venue,
        "daily_visitors": visitors,
        "engagement_score": 60 + (h % 35),
        "recommended_strategies": strategies[:2 + (h % 3)],
        "projected_lift": f"{10 + (h % 20)}% increase in repeat visits",
        "peak_hours": f"{10 + (h % 4)}:00 - {14 + (h % 3)}:00",
    }, ensure_ascii=False)


@_register("cultural_heritage_guide")
def _tool_cultural_heritage_guide(args, root):
    """Generate cultural heritage information. args={site, language?}."""
    site = str(args.get("site", "Colosseum")).strip() or "Colosseum"
    lang = str(args.get("language", "english")).strip().lower() or "english"
    h = hash(site) % 100
    heritage_data = {
        "Colosseum": {"era": "Ancient Rome (70-80 AD)", "significance": "Largest amphitheater, symbol of Roman engineering", "visitors_2024": 7500000},
        "Machu Picchu": {"era": "Inca Empire (1450 AD)", "significance": "Mountain citadel, UNESCO World Heritage", "visitors_2024": 1500000},
        "Angkor Wat": {"era": "Khmer Empire (12th Century)", "significance": "Largest religious monument, Hindu-Buddhist temple complex", "visitors_2024": 2600000},
    }
    info = heritage_data.get(site, {"era": "Unknown", "significance": "Cultural heritage site awaiting classification", "visitors_2024": 0})
    return True, json.dumps({
        "site": site,
        "language": lang,
        "era": info["era"],
        "significance": info["significance"],
        "annual_visitors": info["visitors_2024"],
        "conservation_status": "good" if h < 50 else "requires attention" if h < 80 else "critical",
        "recommended_visit_duration_hours": 3 + (h % 4),
        "virtual_tour_available": True,
    }, ensure_ascii=False)


@_register("virtual_tour_guide")
def _tool_virtual_tour_guide(args, root):
    """Generate AI tour narration. args={site, interest?}."""
    site = str(args.get("site", "Louvre Museum")).strip()
    interest = str(args.get("interest", "art")).strip().lower()
    h = hash(site + interest) % 100
    narrations = {
        "art": "This masterpiece captures the Baroque fascination with light and shadow — notice how the artist uses chiaroscuro to draw your eye to the central figure.",
        "history": "This hall was originally a royal ballroom built in 1685. Over 300 years, it witnessed coronations, revolutions, and world exhibitions.",
        "architecture": "The facade combines Gothic ribbed vaults with Renaissance symmetry — a transition that defined 16th-century European architecture.",
    }
    narration = narrations.get(interest, narrations["art"])
    return True, json.dumps({
        "site": site,
        "interest": interest,
        "narration": narration,
        "next_stop": f"Gallery {3 + (h % 8)}",
        "audio_duration_seconds": 45 + (h % 30),
        "did_you_know": f"This site attracts {5000000 + h * 50000} visitors annually." if h > 50 else "The ceiling fresco took 12 years to complete.",
    }, ensure_ascii=False)


@_register("exhibition_planner")
def _tool_exhibition_planner(args, root):
    """Plan exhibition layout and schedule. args={theme, budget?}."""
    theme = str(args.get("theme", "Modern Art")).strip()
    budget = float(args.get("budget", 50000))
    h = hash(theme) % 100
    return True, json.dumps({
        "theme": theme,
        "budget": budget,
        "recommended_duration_days": 30 + (h % 60),
        "galleries_required": 2 + (h % 4),
        "estimated_visitors": int(10000 + (h % 100) * 200),
        "ticket_price": round(10 + (h % 25), 2),
        "projected_revenue": int(budget * (1.0 + (h % 50) / 100.0)),
        "sponsorship_potential": "high" if h > 60 else "moderate" if h > 30 else "low",
    }, ensure_ascii=False)


# === Utilities & Consumer Services Tools =================================

@_register("resource_optimizer")
def _tool_resource_optimizer(args, root):
    """Optimize resource allocation. args={resource, demand, supply?}."""
    resource = str(args.get("resource", "water")).strip() or "water"
    demand = float(args.get("demand", 1000))
    supply = float(args.get("supply", 850))
    h = hash(resource) % 100
    deficit = supply - demand
    return True, json.dumps({
        "resource": resource,
        "demand": demand,
        "supply": supply,
        "deficit": deficit,
        "status": "critical" if deficit < -200 else "warning" if deficit < 0 else "surplus",
        "optimization_recommendation": "Implement demand-side management" if deficit < 0 else "Increase reserve storage",
        "projected_peak_hour": f"{14 + (h % 6)}:00",
        "conservation_lift_pct": 10 + (h % 15),
    }, ensure_ascii=False)


@_register("public_service_monitor")
def _tool_public_service_monitor(args, root):
    """Monitor public service KPIs. args={service, jurisdiction?}."""
    service = str(args.get("service", "waste_collection")).strip()
    jurisdiction = str(args.get("jurisdiction", "Metro District")).strip() or "Metro District"
    h = hash(service + jurisdiction) % 100
    return True, json.dumps({
        "service": service,
        "jurisdiction": jurisdiction,
        "kpi_score": 60 + (h % 35),
        "status": "excellent" if h > 80 else "satisfactory" if h > 45 else "needs_improvement",
        "response_time_min": 15 + (h % 45),
        "citizen_satisfaction": round(0.6 + (h % 35) / 100.0, 2),
        "open_tickets": max(0, 50 - h),
        "trend": "improving" if h > 60 else "stable" if h > 30 else "declining",
    }, ensure_ascii=False)


@_register("waste_management")
def _tool_waste_management(args, root):
    """Analyze waste management operations. args={district, period?}."""
    district = str(args.get("district", "Zone A")).strip()
    period = str(args.get("period", "monthly")).strip() or "monthly"
    h = hash(district) % 100
    return True, json.dumps({
        "district": district,
        "period": period,
        "total_waste_tons": 500 + h * 20,
        "recycled_pct": 15 + (h % 40),
        "composted_pct": 5 + (h % 15),
        "landfill_pct": 100 - (15 + (h % 40)) - (5 + (h % 15)),
        "collection_efficiency": round(0.7 + (h % 25) / 100.0, 2),
        "recommendations": [
            "Expand curbside composting to Zone B",
            "Add smart bins in high-density areas",
            "Optimize collection routes with AI routing",
        ][:2 + (h % 2)],
    }, ensure_ascii=False)


@_register("energy_grid_monitor")
def _tool_energy_grid_monitor(args, root):
    """Monitor energy grid load and balance. args={region, time_of_day?}."""
    region = str(args.get("region", "North Grid")).strip()
    hour = int(args.get("time_of_day", 14)) % 24
    h = hash(region) % 100
    load = 200 + h * 5 + (hour * 10)
    capacity = 500 + (h % 200)
    return True, json.dumps({
        "region": region,
        "hour": hour,
        "current_load_mw": load,
        "capacity_mw": capacity,
        "utilization_pct": round(load / capacity * 100, 1),
        "renewable_share_pct": 15 + (h % 35),
        "status": "critical" if load / capacity > 0.9 else "warning" if load / capacity > 0.75 else "normal",
        "peak_prediction": f"{16 + (h % 4)}:00",
        "demand_response_recommended": load / capacity > 0.85,
    }, ensure_ascii=False)


# === General SME Tools ===================================================

@_register("workflow_automator")
def _tool_workflow_automator(args, root):
    """Analyze and recommend workflow automation. args={process, employees?}."""
    process = str(args.get("process", "invoice_approval")).strip() or "invoice_approval"
    employees = int(args.get("employees", 5))
    h = hash(process) % 100
    time_saved = employees * (1 + h % 8)
    return True, json.dumps({
        "process": process,
        "employees_involved": employees,
        "current_cycle_hours": 10 + (h % 40),
        "automated_cycle_hours": max(1, (10 + (h % 40)) - time_saved),
        "hours_saved_per_month": time_saved * 20,
        "cost_savings_annual": round(time_saved * 20 * 35 * 12, 2),
        "automation_readiness": round(0.4 + (h % 50) / 100.0, 2),
        "recommended_tools": ["RPA bot", "Approval dashboard", "Auto-reminder system"],
    }, ensure_ascii=False)


@_register("document_processor")
def _tool_document_processor(args, root):
    """Extract structured data from a document. args={document_type, content?}."""
    doc_type = str(args.get("document_type", "invoice")).strip().lower() or "invoice"
    h = hash(doc_type) % 100
    return True, json.dumps({
        "document_type": doc_type,
        "fields_extracted": ["vendor", "amount", "date", "invoice_number", "tax", "line_items"],
        "confidence": round(0.75 + (h % 20) / 100.0, 2),
        "pages_processed": 1 + (h % 5),
        "structured_output": {
            "vendor": f"Vendor-{h % 10}",
            "amount": 1500 + h * 30,
            "date": "2025-07-20",
            "tax": round((1500 + h * 30) * 0.08, 2),
        },
        "extraction_method": "AI OCR + NLP",
    }, ensure_ascii=False)


@_register("customer_support_bot")
def _tool_customer_support_bot(args, root):
    """Generate AI customer support response. args={query, customer_tier?}."""
    query = str(args.get("query", "Where is my order?")).strip()
    tier = str(args.get("customer_tier", "standard")).strip().lower() or "standard"
    h = hash(query + tier) % 100
    responses = {
        "order": "Your order #12345 is currently in transit. Expected delivery: July 25.",
        "refund": "A refund of $59.99 has been initiated. It will reach your account within 5-7 business days.",
        "account": "I've verified your account. Your subscription is active until Aug 15, 2025.",
        "product": "This product features a 2-year warranty, free returns within 30 days, and 24/7 technical support.",
    }
    detected_intent = "order" if "order" in query else "refund" if "refund" in query else "account" if "account" in query else "product"
    response = responses.get(detected_intent, "Thank you for contacting us. A specialist will respond within 4 hours.")
    return True, json.dumps({
        "query": query,
        "detected_intent": detected_intent,
        "sentiment": "positive" if h > 60 else "neutral" if h > 30 else "negative",
        "response": response,
        "escalated": h < 20,
        "resolution_time_min": 2 if h > 50 else 15,
        "customer_satisfaction_predicted": round(0.5 + (h % 40) / 100.0, 2),
    }, ensure_ascii=False)


@_register("supply_chain_analyzer")
def _tool_supply_chain_analyzer(args, root):
    """Analyze supply chain for bottlenecks. args={chain_id, depth?}."""
    chain = str(args.get("chain_id", "SC-001")).strip() or "SC-001"
    depth = min(5, max(1, int(args.get("depth", 3))))
    h = hash(chain) % 100
    return True, json.dumps({
        "chain_id": chain,
        "depth": depth,
        "health_score": 50 + (h % 45),
        "bottlenecks": [f"Supplier-{i}" for i in range(1, depth + 1) if (h + i) % 2 == 0],
        "lead_time_days": 5 + (h % 20),
        "cost_per_unit": round(10 + h * 0.5, 2),
        "risk_level": "high" if h > 70 else "medium" if h > 40 else "low",
        "recommended_actions": [
            "Diversify critical suppliers" if h > 60 else "Maintain current network",
            "Increase safety stock by 15%" if h > 45 else "Reduce safety stock",
            "Audit Tier 2 suppliers for compliance",
        ],
    }, ensure_ascii=False)


# === AEON OS Kernel =====================================================
class AeonOS:
    """
    Top-level AEON OS orchestrator.
    Manages workspaces, app lifecycle, and routes ticks to modules.
    """
    def __init__(self, root: Path = OS_ROOT):
        self.root = Path(root)
        self.workspace_manager = WorkspaceManager(root)
        self.app_registry = AppRegistry()
        self._agents: dict[str, ReflectiveAgent] = {}

    def _agent_for(self, workspace_id: str) -> ReflectiveAgent:
        if workspace_id not in self._agents:
            path = self.workspace_manager.get(workspace_id)
            # Ensure AEON kernel expects sub-directories exist
            (path / "substrates").mkdir(parents=True, exist_ok=True)
            (path / "goals").mkdir(parents=True, exist_ok=True)
            (path / "skills").mkdir(parents=True, exist_ok=True)
            (path / "ledger").mkdir(parents=True, exist_ok=True)
            self._agents[workspace_id] = ReflectiveAgent(path)
        return self._agents[workspace_id]

    def install_app(self, workspace_id: str, app_id: str) -> dict[str, Any]:
        app = self.app_registry.get(app_id)
        if not app:
            return {"ok": False, "error": "unknown app"}
        path = self.workspace_manager.get(workspace_id)
        installed_file = path / f"app_{app_id}.json"
        if installed_file.exists():
            return {"ok": True, "app_id": app_id, "already_installed": True}
        installed_file.write_text(json.dumps(asdict(app)))
        # Seed default goals
        agent = self._agent_for(workspace_id)
        for g in app.default_goals:
            agent.goals.add(g["title"], priority=g.get("priority", 5))
        return {"ok": True, "app_id": app_id, "installed_at": time.time()}

    def list_installed_apps(self, workspace_id: str) -> list[dict[str, Any]]:
        path = self.workspace_manager.get(workspace_id)
        apps = []
        for f in path.glob("app_*.json"):
            with contextlib.suppress(Exception):
                apps.append(json.loads(f.read_text()))
        return apps

    def tick(self, workspace_id: str, app_id: str, query: str) -> dict[str, Any]:
        app = self.app_registry.get(app_id)
        if not app:
            return {"ok": False, "error": "unknown app"}
        self.install_app(workspace_id, app_id)
        agent = self._agent_for(workspace_id)
        # Inject app context into memory
        agent.memory.remember_event("os_tick", f"[{app_id}] {query[:80]}")
        result = agent.act(query)
        return {
            "ok": True,
            "app_id": app_id,
            "workspace_id": workspace_id,
            "result": result,
        }

    def vitals(self, workspace_id: str) -> dict[str, Any]:
        agent = self._agent_for(workspace_id)
        return {
            "ok": True,
            "workspace_id": workspace_id,
            "vitals": agent.self_model.vitals(),
            "open_goals": [g["title"] for g in agent.goals.open_goals()],
            "ledger_balance": agent.ledger.balance("ETH"),
        }


# === Self-test ==========================================================
def _test():
    print("AEON OS self-tests")
    os_root = OS_ROOT / ("_test_" + str(int(time.time())))
    os_root.mkdir(parents=True, exist_ok=True)

    print("  test 1: WorkspaceManager create/list")
    wm = WorkspaceManager(os_root)
    ws = wm.create("acme-corp", tenant="acme")
    assert ws.exists()
    assert len(wm.list_workspaces()) == 1
    print("    PASS")

    print("  test 2: AppRegistry list/get")
    reg = AppRegistry()
    assert "cybersecurity" in [a["id"] for a in reg.list_apps()]
    assert reg.get("cybersecurity").name == "CyberSecurity"
    print("    PASS")

    print("  test 3: AeonOS install + tick")
    aos = AeonOS(os_root)
    res = aos.install_app("acme-corp", "cybersecurity")
    assert res["ok"]
    assert aos.list_installed_apps("acme-corp")[0]["id"] == "cybersecurity"
    print("    PASS")

    print("  test 4: Cybersecurity tools")
    assert _safe_run("threat_lookup", {"indicator": "192.168.1.1"}, str(ws))["ok"]
    assert _safe_run("vuln_scan", {"cve": "CVE-2024-0001"}, str(ws))["ok"]
    assert _safe_run("ip_reputation", {"ip": "8.8.8.8"}, str(ws))["ok"]
    assert _safe_run("compliance_check", {"framework": "nist-csf"}, str(ws))["ok"]
    assert _safe_run("security_news", {}, str(ws))["ok"]
    print("    PASS")

    print("  test 5: AeonOS tick")
    r = aos.tick("acme-corp", "cybersecurity", "Check threat intel for 10.0.0.1")
    assert r["ok"]
    assert "result" in r
    print("    PASS")

    print("  test 6: Vitals")
    v = aos.vitals("acme-corp")
    assert v["ok"] and "vitals" in v
    print("    PASS")

    print("  test 7: Retail & Wholesale tools")
    assert _safe_run("demand_forecast", {"sku": "SKU-001", "horizon_days": 30}, str(ws))["ok"]
    assert _safe_run("inventory_optimizer", {"skus": ["SKU-001", "SKU-042"]}, str(ws))["ok"]
    assert _safe_run("supplier_risk", {"supplier": "Alpha Corp"}, str(ws))["ok"]
    assert _safe_run("price_elasticity", {"sku": "SKU-001", "price_change_pct": 10}, str(ws))["ok"]
    assert _safe_run("storefront_personalizer", {"segment": "premium_shopper"}, str(ws))["ok"]
    print("    PASS")

    print("  test 8: Manufacturing & Engineering tools")
    assert _safe_run("predictive_maintenance", {"machine_id": "CNC-04"}, str(ws))["ok"]
    assert _safe_run("qc_vision", {"batch_id": "B-998"}, str(ws))["ok"]
    assert _safe_run("smart_logistics", {"route_id": "R-10"}, str(ws))["ok"]
    print("    PASS")

    print("  test 9: Professional Services tools")
    assert _safe_run("legal_doc_parser", {"document_name": "Vendor_NDA.pdf"}, str(ws))["ok"]
    assert _safe_run("smart_accounting", {"invoice_id": "INV-102"}, str(ws))["ok"]
    assert _safe_run("data_manager", {"dataset_id": "user_dump.csv"}, str(ws))["ok"]
    print("    PASS")

    print("  test 10: Tourism & Hospitality tools")
    assert _safe_run("booking_optimizer", {"property_id": "Hotel-Central"}, str(ws))["ok"]
    assert _safe_run("dynamic_pricing", {"room_type": "King Suite"}, str(ws))["ok"]
    assert _safe_run("automated_concierge", {"guest_id": "G-445", "request_summary": "dining reservation"}, str(ws))["ok"]
    print("    PASS")

    print("all AEON OS self-tests passed.")


if __name__ == "__main__":
    _test()
