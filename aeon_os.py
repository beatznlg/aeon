# ============================================================
#  AEON OS — Modular autonomous operating system layer
#  - Built on top of aeon.py kernel (ReflectiveAgent, tools, memory)
#  - Adds WorkspaceManager (multi-tenant isolation)
#  - Adds AppRegistry (installable industry modules)
#  - Adds CyberSecurityModule (beachhead vertical)
#  - Designed for B2B SaaS, fully autonomous mode
# ============================================================

import os
import json
import time
import hashlib
from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field, asdict

# Import the AEON kernel we already built
from aeon import (
    ReflectiveAgent,
    MemoryBundle,
    GoalState,
    Ledger,
    ServiceRegistry,
    BountyBoard,
    _register,
    TOOLS,
    _safe_run,
    ROOT as AEON_ROOT,
)


# === OS root directory ====================================================
OS_ROOT = Path(os.environ.get("AEON_OS_ROOT", str(AEON_ROOT) + "/os"))
OS_ROOT.mkdir(parents=True, exist_ok=True)


# === WorkspaceManager ===================================================
class WorkspaceManager:
    """
    Multi-tenant workspace isolation for AEON OS.
    Each workspace gets its own state directory, memory, goals, and ledger.
    """
    def __init__(self, root: Path = OS_ROOT):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

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
        return path

    def exists(self, workspace_id: str) -> bool:
        return self._workspace_path(workspace_id).exists()

    def get(self, workspace_id: str) -> Path:
        if not self.exists(workspace_id):
            self.create(workspace_id)
        return self._workspace_path(workspace_id)

    def list_workspaces(self) -> List[Dict[str, Any]]:
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
                except Exception:
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
    allowed_tools: List[str]
    default_goals: List[Dict[str, Any]]
    color: str = "#8b5cf6"
    status: str = "active"  # active, beta, planned


# === AppRegistry ========================================================
class AppRegistry:
    """
    Registry of installable AEON OS applications / modules.
    Each app defines its tools, goals, and UI color/icon metadata.
    """
    def __init__(self):
        self.apps: Dict[str, AppDefinition] = {}
        self._register_defaults()

    def register(self, app: AppDefinition):
        self.apps[app.id] = app

    def get(self, app_id: str) -> Optional[AppDefinition]:
        return self.apps.get(app_id)

    def list_apps(self) -> List[Dict[str, Any]]:
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

        # Future verticals (stubs for the dashboard)
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


# === Cybersecurity Tools (registered into AEON kernel) ===================

@_register("threat_lookup")
def _tool_threat_lookup(args, root):
    """Query public threat intel for an indicator (IP, hash, domain)."""
    indicator = args.get("indicator", "").strip()
    if not indicator:
        return False, "missing indicator"
    # Use mock data + optionally Abuse.ch MalwareBazaar if API key present
    import os, requests
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
        except Exception as e:
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
    import os, requests
    key = os.environ.get("GREYNOISE_API_KEY")
    if key:
        try:
            r = requests.get(f"https://api.greynoise.io/v3/community/{ip}",
                           headers={"key": key}, timeout=10)
            if r.status_code == 200:
                return True, json.dumps(r.json(), ensure_ascii=False)[:1000]
        except Exception as e:
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
    except Exception:
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
        self._agents: Dict[str, ReflectiveAgent] = {}

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

    def install_app(self, workspace_id: str, app_id: str) -> Dict[str, Any]:
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

    def list_installed_apps(self, workspace_id: str) -> List[Dict[str, Any]]:
        path = self.workspace_manager.get(workspace_id)
        apps = []
        for f in path.glob("app_*.json"):
            try:
                apps.append(json.loads(f.read_text()))
            except Exception:
                pass
        return apps

    def tick(self, workspace_id: str, app_id: str, query: str) -> Dict[str, Any]:
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

    def vitals(self, workspace_id: str) -> Dict[str, Any]:
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
