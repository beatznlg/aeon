"""
AEON OS Sector Tool Endpoints
==============================
Dedicated REST endpoints for each industry vertical's specific tools.
Each sector exposes granular tool-level endpoints that the frontend
dashboards consume individually.

Now supports full CRUD (GET / POST / PATCH / DELETE) on every tool,
persisting to the database via aeon_db.py helpers with mock fallback.

Registered as a Blueprint at /sectors in aeon_server.py.
"""

from __future__ import annotations

import copy
import logging
import uuid
from typing import Any

from flask import Blueprint, jsonify, request

from aeon_auth import require_auth, require_workspace_role

try:
    from aeon_sector_data_gen import generate_sector_tool_data, refresh_all
except Exception as _gen_import_exc:  # pragma: no cover
    generate_sector_tool_data = None  # type: ignore
    refresh_all = None  # type: ignore

logger = logging.getLogger("aeon_sectors")

sectors_bp = Blueprint("sectors", __name__)

# ── Helpers ──────────────────────────────────────────────────────────────────

_WORKSPACE_CTX_ERR = {"ok": False, "error": "no workspace context"}


def _ctx() -> dict[str, Any]:
    """Return the Flask g.user context or empty dict (import-time safe)."""
    try:
        from flask import g
        return getattr(g, "user", {})
    except RuntimeError:
        return {}


def _get_workspace_id() -> str | None:
    """Return the current workspace ID from the request context."""
    ctx = _ctx()
    return ctx.get("workspace_id")


def _get_sector_tool_data(sector: str, tool: str) -> tuple[dict | list | None, bool]:
    """Try to read sector tool data from the DB. Returns (data, from_db).

    If no DB record exists, generate live data, persist it, and return it.
    This keeps the dashboards showing real, time-varying data instead of
    static mocks.
    """
    ws_id = _get_workspace_id()
    if not ws_id:
        return None, False

    try:
        from aeon_db import get_sector_data, upsert_sector_data
        data = get_sector_data(str(ws_id), sector, tool)
        if data is not None:
            return data, True

        # No persisted data yet — generate live data and store it.
        if generate_sector_tool_data is None:
            return None, False

        live_data = generate_sector_tool_data(sector, tool)
        upsert_sector_data(str(ws_id), sector, tool, live_data)
        return live_data, True
    except Exception as exc:
        logger.debug("DB lookup failed for %s/%s: %s", sector, tool, exc)
        return None, False


def _save_sector_tool_data(sector: str, tool: str, data: Any) -> bool:
    """Persist sector tool data to the database. Returns True on success."""
    ws_id = _get_workspace_id()
    if not ws_id:
        return False
    try:
        from aeon_db import upsert_sector_data
        upsert_sector_data(str(ws_id), sector, tool, data)
        return True
    except Exception as exc:
        logger.error("Failed to save sector data %s/%s: %s", sector, tool, exc)
        return False


# ═══════════════════════════════════════════════════════════════════════════════
#  Tool Metadata — describes each tool's data shape, ID field, and mock values
# ═══════════════════════════════════════════════════════════════════════════════

ToolMeta = dict  # type alias for clarity: {"data_key": str, "id_field": str | None, "mock": list | dict}

TOOL_META: dict[tuple[str, str], ToolMeta] = {}

# ── Cybersecurity ────────────────────────────────────────────────────────────

TOOL_META[("cybersecurity", "threats")] = {
    "data_key": "threats",
    "id_field": "id",
    "mock": [
        {"id": "TH-001", "indicator": "192.0.2.45", "type": "IP", "severity": "high", "status": "blocked", "first_seen": "2026-07-28T10:00:00Z", "last_seen": "2026-07-30T08:00:00Z"},
        {"id": "TH-002", "indicator": "malware.exe", "type": "Hash", "severity": "critical", "status": "quarantined", "first_seen": "2026-07-27T22:00:00Z", "last_seen": "2026-07-30T06:00:00Z"},
        {"id": "TH-003", "indicator": "phish.example.com", "type": "Domain", "severity": "medium", "status": "monitored", "first_seen": "2026-07-29T12:00:00Z", "last_seen": "2026-07-30T07:30:00Z"},
        {"id": "TH-004", "indicator": "10.0.0.99", "type": "IP", "severity": "low", "status": "investigating", "first_seen": "2026-07-30T01:00:00Z", "last_seen": "2026-07-30T08:00:00Z"},
    ],
}

TOOL_META[("cybersecurity", "vulnerabilities")] = {
    "data_key": "vulnerabilities",
    "id_field": "cve",
    "extra_response": {"scan_summary": {"total": 4, "critical": 1, "high": 1, "medium": 1, "low": 1}},
    "mock": [
        {"cve": "CVE-2024-0001", "severity": "Critical", "cvss": 9.8, "affected": "example-lib", "patch_available": True, "discovered": "2026-07-15"},
        {"cve": "CVE-2024-0002", "severity": "High", "cvss": 7.5, "affected": "auth-service", "patch_available": False, "discovered": "2026-07-20"},
        {"cve": "CVE-2024-0003", "severity": "Medium", "cvss": 5.3, "affected": "api-gateway", "patch_available": True, "discovered": "2026-07-25"},
        {"cve": "CVE-2024-0004", "severity": "Low", "cvss": 3.2, "affected": "logging-lib", "patch_available": True, "discovered": "2026-07-28"},
    ],
}

TOOL_META[("cybersecurity", "compliance")] = {
    "data_key": "compliance",
    "id_field": None,
    "mock": {
        "framework": "NIST-CSF",
        "score": 84,
        "maturity": "Managed",
        "gaps": ["IAM review", "Log retention", "Incident response automation"],
        "last_assessment": "2026-07-28",
    },
}

TOOL_META[("cybersecurity", "ip-reputation")] = {
    "data_key": "ip_reputation",
    "id_field": None,
    "mock": {
        "score": 0.18,
        "known_malicious": False,
        "source_countries": ["US", "DE", "JP"],
        "last_seen_days": 2,
    },
}

TOOL_META[("cybersecurity", "news")] = {
    "data_key": "news",
    "id_field": "title",
    "mock": [
        {"title": "Critical OpenSSH vulnerability disclosed", "url": "#", "source": "CVE Database", "date": "2026-07-29"},
        {"title": "New ransomware group targets healthcare sector", "url": "#", "source": "Threat Intel", "date": "2026-07-28"},
        {"title": "Zero-day exploit detected in popular VPN client", "url": "#", "source": "Security Advisory", "date": "2026-07-27"},
    ],
}

# ── Health ───────────────────────────────────────────────────────────────────

TOOL_META[("health", "diagnostics")] = {
    "data_key": "diagnostics",
    "id_field": "analyzed_symptoms",
    "mock": [
        {
            "analyzed_symptoms": "fever, cough, fatigue",
            "possible_conditions": [{"name": "viral infection", "probability": 0.78, "severity": "moderate", "action": "rest and monitor"}],
            "urgency": "moderate",
            "recommendation": "rest and monitor",
        },
        {
            "analyzed_symptoms": "chest pain, shortness of breath",
            "possible_conditions": [{"name": "cardiac concern", "probability": 0.65, "severity": "high", "action": "immediate evaluation"}],
            "urgency": "high",
            "recommendation": "immediate evaluation",
        },
        {
            "analyzed_symptoms": "headache, nausea",
            "possible_conditions": [{"name": "migraine", "probability": 0.72, "severity": "moderate", "action": "hydration and rest"}],
            "urgency": "moderate",
            "recommendation": "hydration and rest",
        },
    ],
}

TOOL_META[("health", "vitals")] = {
    "data_key": "vitals",
    "id_field": "patient_id",
    "mock": [
        {"patient_id": "P-1001", "metric": "heart_rate", "baseline": 72, "current": 72, "trend": "stable", "alert": False},
        {"patient_id": "P-1001", "metric": "blood_pressure_sys", "baseline": 120, "current": 118, "trend": "stable", "alert": False},
        {"patient_id": "P-1002", "metric": "heart_rate", "baseline": 72, "current": 95, "trend": "rising", "alert": True},
        {"patient_id": "P-1002", "metric": "blood_pressure_sys", "baseline": 120, "current": 142, "trend": "rising", "alert": True},
        {"patient_id": "P-1003", "metric": "oxygen_saturation", "baseline": 98, "current": 92, "trend": "falling", "alert": True},
    ],
}

TOOL_META[("health", "drug-interactions")] = {
    "data_key": "interactions",
    "id_field": "medications",
    "extra_response": {"total_interaction_sets": 3},
    "mock": [
        {
            "medications": ["aspirin", "warfarin"],
            "interactions_found": 1,
            "interactions": [{"drugs": ["aspirin", "warfarin"], "severity": "moderate", "warning": "increased bleeding risk"}],
        },
        {
            "medications": ["lisinopril", "potassium"],
            "interactions_found": 1,
            "interactions": [{"drugs": ["lisinopril", "potassium"], "severity": "high", "warning": "hyperkalemia risk"}],
        },
        {
            "medications": ["metformin", "losartan"],
            "interactions_found": 0,
            "interactions": [],
        },
    ],
}

TOOL_META[("health", "telehealth")] = {
    "data_key": "triage",
    "id_field": "symptoms",
    "mock": [
        {"symptoms": "chest pain", "age": 65, "urgency": "emergent", "recommendation": "call 911"},
        {"symptoms": "fever", "age": 30, "urgency": "non-urgent", "recommendation": "schedule virtual visit"},
        {"symptoms": "skin rash", "age": 42, "urgency": "routine", "recommendation": "upload photos for dermatology review"},
        {"symptoms": "cough", "age": 55, "urgency": "non-urgent", "recommendation": "schedule virtual visit"},
    ],
}

# ── Finance ──────────────────────────────────────────────────────────────────

TOOL_META[("finance", "risk")] = {
    "data_key": "risk",
    "id_field": None,
    "mock": {
        "asset": "S&P 500",
        "portfolio_value": 500000,
        "var_95_1d": 12500,
        "var_95_pct": 2.5,
        "sharpe_estimate": 1.45,
        "beta": 0.98,
        "risk_rating": "medium",
        "diversification_score": 7,
        "recommendation": "diversify fixed income",
    },
}

TOOL_META[("finance", "market")] = {
    "data_key": "market",
    "id_field": None,
    "mock": {
        "market": "NASDAQ",
        "predicted_direction": "bullish",
        "confidence": 0.72,
        "price_target_pct": 4.2,
        "volatility_forecast": "moderate",
        "key_indicators": {"rsi": 62, "macd": "bullish_cross", "moving_avg_50": 18500, "moving_avg_200": 17200},
    },
}

TOOL_META[("finance", "fraud")] = {
    "data_key": "fraud_cases",
    "id_field": "transaction_id",
    "mock": [
        {"transaction_id": "TXN-5001", "amount": 5000, "fraud_score": 0.85, "risk_level": "high", "action": "blocked", "timestamp": "2026-07-30T04:00:00Z"},
        {"transaction_id": "TXN-5002", "amount": 35, "fraud_score": 0.05, "risk_level": "low", "action": "approved", "timestamp": "2026-07-30T05:00:00Z"},
        {"transaction_id": "TXN-5003", "amount": 25000, "fraud_score": 0.72, "risk_level": "high", "action": "flagged", "timestamp": "2026-07-30T06:00:00Z"},
        {"transaction_id": "TXN-5004", "amount": 150, "fraud_score": 0.12, "risk_level": "low", "action": "approved", "timestamp": "2026-07-30T07:00:00Z"},
    ],
}

TOOL_META[("finance", "credit")] = {
    "data_key": "applications",
    "id_field": "applicant_id",
    "mock": [
        {"applicant_id": "APP-200", "credit_score": 720, "rating": "Good", "approval_probability": 0.92, "recommended_limit": 15000},
        {"applicant_id": "APP-201", "credit_score": 580, "rating": "Poor", "approval_probability": 0.18, "recommended_limit": 0},
        {"applicant_id": "APP-202", "credit_score": 810, "rating": "Excellent", "approval_probability": 0.99, "recommended_limit": 50000},
        {"applicant_id": "APP-203", "credit_score": 650, "rating": "Fair", "approval_probability": 0.55, "recommended_limit": 5000},
    ],
}

TOOL_META[("finance", "payments")] = {
    "data_key": "accounts",
    "id_field": "account_id",
    "mock": [
        {"account_id": "ACC-1234", "total_transactions": 142, "total_volume": 48500, "anomaly_count": 1, "spending_trend": "stable"},
        {"account_id": "ACC-5678", "total_transactions": 89, "total_volume": 22300, "anomaly_count": 3, "spending_trend": "increasing"},
        {"account_id": "ACC-9012", "total_transactions": 312, "total_volume": 128000, "anomaly_count": 0, "spending_trend": "stable"},
    ],
}

# ── Retail & E-commerce ──────────────────────────────────────────────────────

TOOL_META[("retail", "forecast")] = {
    "data_key": "forecast",
    "id_field": "sku",
    "mock": [
        {"sku": "SKU-001", "current_stock": 850, "projected_demand": 1240, "recommended_order_qty": 390, "confidence": 0.92},
        {"sku": "SKU-042", "current_stock": 420, "projected_demand": 680, "recommended_order_qty": 260, "confidence": 0.88},
        {"sku": "SKU-099", "current_stock": 2100, "projected_demand": 1890, "recommended_order_qty": 0, "confidence": 0.95},
        {"sku": "SKU-107", "current_stock": 120, "projected_demand": 340, "recommended_order_qty": 220, "confidence": 0.76},
        {"sku": "SKU-215", "current_stock": 560, "projected_demand": 890, "recommended_order_qty": 330, "confidence": 0.84},
    ],
}

TOOL_META[("retail", "inventory")] = {
    "data_key": "inventory",
    "id_field": None,
    "mock": {
        "alerts": [{"sku": "SKU-107", "status": "stockout_risk", "days_remaining": 2}],
        "reorder_recommendations": [
            {"sku": "SKU-107", "qty": 220, "supplier": "Alpha Corp", "est_delivery_days": 3},
            {"sku": "SKU-042", "qty": 260, "supplier": "Gamma Wholesale", "est_delivery_days": 5},
        ],
        "healthy": [
            {"sku": "SKU-001", "status": "healthy", "days_supply": 21},
            {"sku": "SKU-099", "status": "overstock", "days_supply": 75, "suggestion": "run promotion"},
            {"sku": "SKU-215", "status": "healthy", "days_supply": 18},
        ],
        "summary": {"total_skus": 5, "stockout_risks": 1, "overstocks": 1, "healthy": 3},
    },
}

TOOL_META[("retail", "suppliers")] = {
    "data_key": "suppliers",
    "id_field": "supplier",
    "mock": [
        {"supplier": "Alpha Corp", "risk_score": 15, "classification": "Low Risk", "on_time_delivery_pct": 96, "contract_end": "2027-03-01"},
        {"supplier": "Beta Logistics", "risk_score": 42, "classification": "Medium Risk", "on_time_delivery_pct": 82, "contract_end": "2026-12-01"},
        {"supplier": "Gamma Wholesale", "risk_score": 8, "classification": "Low Risk", "on_time_delivery_pct": 99, "contract_end": "2028-01-01"},
        {"supplier": "Delta Distributors", "risk_score": 71, "classification": "High Risk", "on_time_delivery_pct": 61, "contract_end": "2026-09-15"},
    ],
}

TOOL_META[("retail", "pricing")] = {
    "data_key": "elasticity",
    "id_field": None,
    "mock": {
        "sku": "SKU-001",
        "price_change_pct": 10,
        "elasticity": -0.42,
        "projected_demand_change_pct": -4.2,
        "optimal_price": 32.50,
        "current_price": 29.99,
    },
}

# ── Transport & Logistics ────────────────────────────────────────────────────

TOOL_META[("transport", "traffic")] = {
    "data_key": "zones",
    "id_field": "zone",
    "mock": [
        {"zone": "downtown", "current_congestion": 8.2, "predicted_improvement": "divert to ring road", "incident_nearby": True},
        {"zone": "midtown", "current_congestion": 6.5, "predicted_improvement": "monitor", "incident_nearby": False},
        {"zone": "airport_corridor", "current_congestion": 9.1, "predicted_improvement": "activate bus lane", "incident_nearby": True},
        {"zone": "suburb_east", "current_congestion": 3.8, "predicted_improvement": "normal flow", "incident_nearby": False},
        {"zone": "harbor_district", "current_congestion": 5.2, "predicted_improvement": "adjust signal timing", "incident_nearby": False},
    ],
}

TOOL_META[("transport", "fleet")] = {
    "data_key": "fleet",
    "id_field": "depot",
    "mock": [
        {"depot": "North Hub", "vehicles_available": 10, "shifts": 3, "utilization_pct": 87, "recommendation": "reduce 1 vehicle"},
        {"depot": "South Hub", "vehicles_available": 8, "shifts": 2, "utilization_pct": 72, "recommendation": "reduce 2 vehicles"},
        {"depot": "Central Hub", "vehicles_available": 15, "shifts": 3, "utilization_pct": 93, "recommendation": "optimal"},
        {"depot": "East Hub", "vehicles_available": 6, "shifts": 1, "utilization_pct": 82, "recommendation": "add 1 vehicle"},
    ],
}

TOOL_META[("transport", "routes")] = {
    "data_key": "routes",
    "id_field": "stops",
    "mock": [
        {"stops": ["A", "B", "C", "D", "E"], "estimated_distance_km": 42, "estimated_time_min": 55, "fuel_cost_est": 18.50, "optimized": True},
        {"stops": ["F", "G", "H", "I", "J"], "estimated_distance_km": 38, "estimated_time_min": 48, "fuel_cost_est": 16.20, "optimized": True},
        {"stops": ["K", "L", "M", "N", "O"], "estimated_distance_km": 56, "estimated_time_min": 72, "fuel_cost_est": 24.80, "optimized": False},
        {"stops": ["P", "Q", "R", "S"], "estimated_distance_km": 28, "estimated_time_min": 35, "fuel_cost_est": 12.00, "optimized": True},
    ],
}

# ── Manufacturing ────────────────────────────────────────────────────────────

TOOL_META[("manufacturing", "maintenance")] = {
    "data_key": "machines",
    "id_field": "machine_id",
    "mock": [
        {"machine_id": "CNC-01", "status": "good", "temp_c": 42, "vibration_hz": 12.5, "failure_risk_pct": 12, "days_to_failure": 45, "last_service": "2026-06-15"},
        {"machine_id": "CNC-02", "status": "warning", "temp_c": 58, "vibration_hz": 18.2, "failure_risk_pct": 34, "days_to_failure": 12, "last_service": "2026-05-01"},
        {"machine_id": "CNC-03", "status": "good", "temp_c": 44, "vibration_hz": 11.8, "failure_risk_pct": 15, "days_to_failure": 30, "last_service": "2026-07-01"},
        {"machine_id": "CNC-04", "status": "critical", "temp_c": 78, "vibration_hz": 31.4, "failure_risk_pct": 89, "days_to_failure": 3, "last_service": "2026-03-20"},
        {"machine_id": "CNC-05", "status": "good", "temp_c": 40, "vibration_hz": 10.1, "failure_risk_pct": 8, "days_to_failure": 60, "last_service": "2026-07-10"},
    ],
}

TOOL_META[("manufacturing", "quality")] = {
    "data_key": "batches",
    "id_field": "batch_id",
    "mock": [
        {"batch_id": "B-998", "items_scanned": 500, "defects_found": 10, "defect_rate": 0.02, "status": "pass"},
        {"batch_id": "B-999", "items_scanned": 500, "defects_found": 35, "defect_rate": 0.07, "status": "fail", "root_cause": "calibration drift"},
        {"batch_id": "B-1000", "items_scanned": 500, "defects_found": 5, "defect_rate": 0.01, "status": "pass"},
        {"batch_id": "B-1001", "items_scanned": 500, "defects_found": 18, "defect_rate": 0.036, "status": "warn", "root_cause": "raw material variance"},
    ],
}

TOOL_META[("manufacturing", "logistics")] = {
    "data_key": "shipments",
    "id_field": "route_id",
    "mock": [
        {"route_id": "R-10", "status": "on_time", "eta_days": 1, "reroute_cost_usd": 0},
        {"route_id": "R-11", "status": "delayed", "eta_days": 3, "reroute_cost_usd": 1800, "delay_reason": "weather"},
        {"route_id": "R-12", "status": "on_time", "eta_days": 2, "reroute_cost_usd": 0},
        {"route_id": "R-13", "status": "on_time", "eta_days": 4, "reroute_cost_usd": 0},
        {"route_id": "R-14", "status": "delayed", "eta_days": 5, "reroute_cost_usd": 2500, "delay_reason": "port congestion"},
    ],
}

# ── Tourism & Hospitality ────────────────────────────────────────────────────

TOOL_META[("tourism", "bookings")] = {
    "data_key": "bookings",
    "id_field": "property",
    "mock": [
        {"property": "Hotel-Central", "occupancy_pct": 82, "predictive_no_shows": 14, "net_expected_occupancy": 78, "revenue_ytd": 1250000},
        {"property": "Hotel-West", "occupancy_pct": 68, "predictive_no_shows": 18, "net_expected_occupancy": 64, "revenue_ytd": 890000},
        {"property": "Hotel-Airport", "occupancy_pct": 91, "predictive_no_shows": 22, "net_expected_occupancy": 89, "revenue_ytd": 2100000},
    ],
}

TOOL_META[("tourism", "pricing")] = {
    "data_key": "pricing",
    "id_field": "room",
    "mock": [
        {"room": "King Suite", "base_price": 299, "recommended_price": 320, "reason": "High demand", "demand_level": "high"},
        {"room": "Double Queen", "base_price": 259, "recommended_price": 245, "reason": "Medium demand", "demand_level": "medium"},
        {"room": "Standard", "base_price": 169, "recommended_price": 175, "reason": "Low demand, hold", "demand_level": "low"},
        {"room": "Penthouse", "base_price": 599, "recommended_price": 650, "reason": "Premium event weekend", "demand_level": "high"},
    ],
}

TOOL_META[("tourism", "concierge")] = {
    "data_key": "requests",
    "id_field": "guest_id",
    "mock": [
        {"guest_id": "G-445", "sentiment": "positive", "intent": "dining reservation", "automated_response": "Reservation confirmed at 8 PM", "upsell": "Wine pairing package"},
        {"guest_id": "G-446", "sentiment": "neutral", "intent": "housekeeping request", "automated_response": "Housekeeping dispatched", "upsell": None},
        {"guest_id": "G-447", "sentiment": "negative", "intent": "transport to airport", "automated_response": "Taxi booked for 6 AM", "upsell": None},
        {"guest_id": "G-448", "sentiment": "positive", "intent": "spa booking", "automated_response": "Spa appointment confirmed at 3 PM", "upsell": "Couples massage package"},
    ],
}

TOOL_META[("tourism", "visitors")] = {
    "data_key": "venues",
    "id_field": "venue",
    "mock": [
        {"venue": "National Museum", "daily_visitors": 1200, "engagement_score": 92, "recommended_strategies": ["extend hours weekends", "new family tour"]},
        {"venue": "Modern Art Gallery", "daily_visitors": 680, "engagement_score": 88, "recommended_strategies": ["new exhibition promo"]},
        {"venue": "History Center", "daily_visitors": 450, "engagement_score": 85, "recommended_strategies": ["school program expansion"]},
    ],
}

# ── Utilities & Public Sector ────────────────────────────────────────────────

TOOL_META[("utilities", "resources")] = {
    "data_key": "resources",
    "id_field": "resource",
    "mock": [
        {"resource": "water", "demand": 1000, "supply": 850, "deficit": 150, "status": "critical", "optimization_suggestion": "implement tiered pricing"},
        {"resource": "electricity", "demand": 500, "supply": 480, "deficit": 20, "status": "warning", "optimization_suggestion": "demand response program"},
        {"resource": "natural_gas", "demand": 300, "supply": 320, "deficit": 0, "status": "good"},
        {"resource": "renewable_energy", "demand": 200, "supply": 250, "deficit": 0, "status": "good", "optimization_suggestion": "increase storage capacity"},
    ],
}

TOOL_META[("utilities", "services")] = {
    "data_key": "services",
    "id_field": "service",
    "mock": [
        {"service": "waste_collection", "kpi_score": 0.89, "status": "satisfactory", "citizen_satisfaction": 0.78, "trend": "stable"},
        {"service": "street_lighting", "kpi_score": 0.97, "status": "excellent", "citizen_satisfaction": 0.92, "trend": "improving"},
        {"service": "public_transport", "kpi_score": 0.82, "status": "needs improvement", "citizen_satisfaction": 0.65, "trend": "declining"},
        {"service": "water_supply", "kpi_score": 0.91, "status": "good", "citizen_satisfaction": 0.85, "trend": "stable"},
    ],
}

TOOL_META[("utilities", "waste")] = {
    "data_key": "districts",
    "id_field": "district",
    "mock": [
        {"district": "Zone A", "total_waste_tons": 1200, "recycled_pct": 35, "landfill_pct": 65, "collection_efficiency": 0.92},
        {"district": "Zone B", "total_waste_tons": 850, "recycled_pct": 22, "landfill_pct": 78, "collection_efficiency": 0.78},
        {"district": "Zone C", "total_waste_tons": 1600, "recycled_pct": 41, "landfill_pct": 59, "collection_efficiency": 0.95},
    ],
}

TOOL_META[("utilities", "grid")] = {
    "data_key": "regions",
    "id_field": "region",
    "mock": [
        {"region": "North Grid", "current_load_mw": 245, "capacity_mw": 280, "utilization_pct": 87.5, "renewable_share_pct": 38, "status": "stable"},
        {"region": "South Grid", "current_load_mw": 312, "capacity_mw": 300, "utilization_pct": 104, "renewable_share_pct": 22, "status": "critical", "action": "activate backup generators"},
        {"region": "East Grid", "current_load_mw": 198, "capacity_mw": 260, "utilization_pct": 76.2, "renewable_share_pct": 45, "status": "stable"},
        {"region": "West Grid", "current_load_mw": 178, "capacity_mw": 240, "utilization_pct": 74.2, "renewable_share_pct": 52, "status": "stable"},
    ],
}

# ── Cultural Heritage ────────────────────────────────────────────────────────

TOOL_META[("heritage", "visitors")] = {
    "data_key": "venues",
    "id_field": "venue",
    "mock": [
        {"venue": "National Museum", "daily_visitors": 1200, "engagement_score": 92, "recommended_strategies": ["extend hours weekends", "new family tour"]},
        {"venue": "Modern Art Gallery", "daily_visitors": 680, "engagement_score": 88, "recommended_strategies": ["new exhibition promo"]},
        {"venue": "History Center", "daily_visitors": 450, "engagement_score": 85, "recommended_strategies": ["school program expansion"]},
    ],
}

TOOL_META[("heritage", "sites")] = {
    "data_key": "sites",
    "id_field": "site",
    "mock": [
        {"site": "Colosseum", "era": "Ancient Rome", "significance": "Iconic amphitheatre", "annual_visitors": 7400000, "conservation_status": "good"},
        {"site": "Machu Picchu", "era": "Inca Empire", "significance": "Citadel in the Andes", "annual_visitors": 2500000, "conservation_status": "requires attention"},
        {"site": "Angkor Wat", "era": "Khmer Empire", "significance": "Largest religious monument", "annual_visitors": 2600000, "conservation_status": "fair"},
    ],
}

TOOL_META[("heritage", "exhibitions")] = {
    "data_key": "exhibitions",
    "id_field": "theme",
    "mock": [
        {"theme": "Modern Art", "recommended_duration_days": 90, "estimated_visitors": 80000, "ticket_price": 25, "projected_revenue": 2000000},
        {"theme": "Ancient Egypt", "recommended_duration_days": 60, "estimated_visitors": 60000, "ticket_price": 22, "projected_revenue": 1320000},
        {"theme": "Space Exploration", "recommended_duration_days": 45, "estimated_visitors": 45000, "ticket_price": 28, "projected_revenue": 1260000},
    ],
}

TOOL_META[("heritage", "tours")] = {
    "data_key": "tours",
    "id_field": "site",
    "mock": [
        {"site": "Louvre Museum", "interest": "art", "narration": "Explore the Mona Lisa and French masters", "audio_duration_seconds": 2100},
        {"site": "British Museum", "interest": "history", "narration": "Journey through 2 million years of history", "audio_duration_seconds": 2400},
        {"site": "Uffizi Gallery", "interest": "architecture", "narration": "Renaissance art and architecture", "audio_duration_seconds": 1680},
        {"site": "Vatican Museums", "interest": "religion", "narration": "Masterpieces of religious art", "audio_duration_seconds": 1800},
    ],
}

# ── SME Business Suite ───────────────────────────────────────────────────────

TOOL_META[("sme", "workflows")] = {
    "data_key": "workflows",
    "id_field": "process",
    "mock": [
        {"process": "invoice_approval", "employees_involved": 5, "hours_saved_per_month": 120, "cost_savings_annual": 24000, "automation_rate": 0.85},
        {"process": "employee_onboarding", "employees_involved": 3, "hours_saved_per_month": 80, "cost_savings_annual": 16000, "automation_rate": 0.72},
        {"process": "report_generation", "employees_involved": 2, "hours_saved_per_month": 60, "cost_savings_annual": 12000, "automation_rate": 0.94},
        {"process": "expense_reporting", "employees_involved": 4, "hours_saved_per_month": 95, "cost_savings_annual": 19000, "automation_rate": 0.78},
    ],
}

TOOL_META[("sme", "documents")] = {
    "data_key": "documents",
    "id_field": "document_type",
    "mock": [
        {"document_type": "invoice", "confidence": 0.97, "pages_processed": 142, "fields_extracted": ["vendor", "amount", "due_date"], "status": "completed"},
        {"document_type": "contract", "confidence": 0.94, "pages_processed": 38, "fields_extracted": ["parties", "term", "liability"], "status": "completed"},
        {"document_type": "receipt", "confidence": 0.96, "pages_processed": 210, "fields_extracted": ["merchant", "total", "date"], "status": "pending"},
        {"document_type": "purchase_order", "confidence": 0.91, "pages_processed": 55, "fields_extracted": ["items", "total", "delivery_date"], "status": "completed"},
    ],
}

TOOL_META[("sme", "support")] = {
    "data_key": "tickets",
    "id_field": "query",
    "mock": [
        {"query": "Where is my order?", "detected_intent": "order_status", "sentiment": "frustrated", "response": "Tracking link sent", "escalated": False},
        {"query": "I want a refund", "detected_intent": "refund", "sentiment": "angry", "response": "Refund initiated", "escalated": True},
        {"query": "My account is locked", "detected_intent": "account_access", "sentiment": "neutral", "response": "Unlocked with MFA reset", "escalated": False},
        {"query": "How do I change my plan?", "detected_intent": "plan_change", "sentiment": "neutral", "response": "Plan upgrade options sent", "escalated": False},
    ],
}

TOOL_META[("sme", "supply-chain")] = {
    "data_key": "chains",
    "id_field": "chain_id",
    "mock": [
        {"chain_id": "SC-001", "health_score": 92, "lead_time_days": 5, "risk_level": "low", "bottlenecks": []},
        {"chain_id": "SC-002", "health_score": 68, "lead_time_days": 14, "risk_level": "medium", "bottlenecks": ["distributor delay"]},
        {"chain_id": "SC-003", "health_score": 85, "lead_time_days": 7, "risk_level": "low", "bottlenecks": []},
        {"chain_id": "SC-004", "health_score": 45, "lead_time_days": 21, "risk_level": "high", "bottlenecks": ["raw material shortage", "transport strike"]},
    ],
}


# ═══════════════════════════════════════════════════════════════════════════════
#  CRUD operations — shared helpers called by the dynamically registered routes
# ═══════════════════════════════════════════════════════════════════════════════

def _do_get_tool(sector: str, tool: str, meta: ToolMeta):
    """Handle GET for a sector tool."""
    data_key = meta["data_key"]
    extra = meta.get("extra_response", {})

    data, from_db = _get_sector_tool_data(sector, tool)
    if from_db:
        return jsonify({"ok": True, data_key: data, "source": "db", **extra})
    return jsonify({"ok": True, data_key: meta["mock"], "source": "mock", **extra})


def _do_create_tool_item(sector: str, tool: str, meta: ToolMeta):
    """Handle POST: create a new item (array tool) or replace object (object tool)."""
    ws_id = _get_workspace_id()
    if not ws_id:
        return jsonify({"ok": False, "error": "no workspace context"}), 400

    body = request.get_json(silent=True)
    if body is None:
        return jsonify({"ok": False, "error": "invalid JSON body"}), 400

    id_field = meta.get("id_field")
    data_key = meta["data_key"]

    # Load existing data from DB, or start with empty/mock
    existing, from_db = _get_sector_tool_data(sector, tool)
    if not from_db:
        existing = copy.deepcopy(meta["mock"])

    if isinstance(existing, list):
        # Array tool — append the new item
        if id_field and id_field not in body:
            body[id_field] = f"{sector}-{tool}-{uuid.uuid4().hex[:8].upper()}"
        existing.append(body)
        _save_sector_tool_data(sector, tool, existing)
        return jsonify({"ok": True, data_key: existing, "created": body, "source": "db"}), 201
    else:
        # Object tool — replace the entire object
        _save_sector_tool_data(sector, tool, body)
        return jsonify({"ok": True, data_key: body, "source": "db"}), 201


def _do_update_tool_item(sector: str, tool: str, meta: ToolMeta):
    """Handle PATCH: update an existing item by id_field (array) or merge fields (object)."""
    ws_id = _get_workspace_id()
    if not ws_id:
        return jsonify({"ok": False, "error": "no workspace context"}), 400

    body = request.get_json(silent=True)
    if body is None:
        return jsonify({"ok": False, "error": "invalid JSON body"}), 400

    id_field = meta.get("id_field")
    data_key = meta["data_key"]

    existing, from_db = _get_sector_tool_data(sector, tool)
    if not from_db:
        existing = copy.deepcopy(meta["mock"])

    if isinstance(existing, list):
        if not id_field or id_field not in body:
            return jsonify({"ok": False, "error": f"Missing identifier field '{id_field}' in request body"}), 400
        item_id = body[id_field]
        updated = False
        for i, item in enumerate(existing):
            if item.get(id_field) == item_id:
                existing[i] = {**item, **body}
                updated = True
                break
        if not updated:
            return jsonify({"ok": False, "error": f"Item with {id_field}='{item_id}' not found"}), 404
        _save_sector_tool_data(sector, tool, existing)
        return jsonify({"ok": True, data_key: existing, "updated": existing, "source": "db"})
    else:
        # Object tool — merge fields
        merged = {**existing, **body} if isinstance(existing, dict) else body
        _save_sector_tool_data(sector, tool, merged)
        return jsonify({"ok": True, data_key: merged, "source": "db"})


def _do_delete_tool_item(sector: str, tool: str, meta: ToolMeta):
    """Handle DELETE: remove an item by id_field (array) or reset to default mock (object)."""
    ws_id = _get_workspace_id()
    if not ws_id:
        return jsonify({"ok": False, "error": "no workspace context"}), 400

    body = request.get_json(silent=True) or {}
    id_field = meta.get("id_field")
    data_key = meta["data_key"]

    existing, from_db = _get_sector_tool_data(sector, tool)
    if not from_db:
        existing = copy.deepcopy(meta["mock"])

    if isinstance(existing, list):
        if not id_field or id_field not in body:
            return jsonify({"ok": False, "error": f"Missing identifier field '{id_field}' in request body"}), 400
        item_id = body[id_field]
        before_len = len(existing)
        existing = [item for item in existing if item.get(id_field) != item_id]
        if len(existing) == before_len:
            return jsonify({"ok": False, "error": f"Item with {id_field}='{item_id}' not found"}), 404
        _save_sector_tool_data(sector, tool, existing)
        return jsonify({"ok": True, "deleted": True, "remaining": len(existing), data_key: existing})
    else:
        # Object tool — reset to default mock
        reset = copy.deepcopy(meta["mock"])
        _save_sector_tool_data(sector, tool, reset)
        return jsonify({"ok": True, "reset": True, data_key: reset})


# ═══════════════════════════════════════════════════════════════════════════════
#  Dynamic route registration — creates GET / POST / PATCH / DELETE per tool
# ═══════════════════════════════════════════════════════════════════════════════

def _register_tool_crud(sector: str, tool: str, meta: ToolMeta):
    """Register all 4 HTTP verbs for a single sector tool endpoint with auth decorators."""
    route = f"/{sector}/{tool}"

    # ── GET (VIEWER role) ──
    @require_auth
    @require_workspace_role("VIEWER")
    def _get_view():
        return _do_get_tool(sector, tool, meta)

    sectors_bp.add_url_rule(
        route,
        endpoint=f"{sector}_{tool}_get",
        view_func=_get_view,
        methods=["GET"],
    )

    # ── POST (ADMIN role) ──
    @require_auth
    @require_workspace_role("ADMIN")
    def _post_view():
        return _do_create_tool_item(sector, tool, meta)

    sectors_bp.add_url_rule(
        route,
        endpoint=f"{sector}_{tool}_post",
        view_func=_post_view,
        methods=["POST"],
    )

    # ── PATCH (ADMIN role) ──
    @require_auth
    @require_workspace_role("ADMIN")
    def _patch_view():
        return _do_update_tool_item(sector, tool, meta)

    sectors_bp.add_url_rule(
        route,
        endpoint=f"{sector}_{tool}_patch",
        view_func=_patch_view,
        methods=["PATCH"],
    )

    # ── DELETE (ADMIN role) ──
    @require_auth
    @require_workspace_role("ADMIN")
    def _delete_view():
        return _do_delete_tool_item(sector, tool, meta)

    sectors_bp.add_url_rule(
        route,
        endpoint=f"{sector}_{tool}_delete",
        view_func=_delete_view,
        methods=["DELETE"],
    )


# Register all 40 tools dynamically
for (sector, tool), meta in TOOL_META.items():
    _register_tool_crud(sector, tool, meta)


# ═══════════════════════════════════════════════════════════════════════════════
#  Generic sector data endpoint & seed endpoint
#  (These handle raw data CRUD at the storage level, complementing the
#   item-level CRUD above.)
# ═══════════════════════════════════════════════════════════════════════════════

# ── Generic data get ─────────────────────────────────────────────────────────
@sectors_bp.route("/data/<sector>/<tool>", methods=["GET"])
@require_auth
@require_workspace_role("VIEWER")
def sector_data_get(sector: str, tool: str):
    """Return sector tool data from the database (if seeded) or mock.

    The response uses the tool's ``data_key`` as the top-level key so the
    frontend can consume it directly (e.g. ``{ok: true, threats: [...]}``).
    """
    data, from_db = _get_sector_tool_data(sector, tool)
    meta = TOOL_META.get((sector, tool))
    data_key = meta["data_key"] if meta else tool
    source = "db" if from_db else "mock"

    if from_db:
        return jsonify({"ok": True, data_key: data, "source": source, "data_key": data_key})

    # Fall back to mock data from TOOL_META
    if meta:
        return jsonify({
            "ok": True,
            data_key: meta["mock"],
            "source": source,
            "data_key": data_key,
        })

    return jsonify({"ok": False, "error": f"No data found for {sector}/{tool}"}), 404


# ── Generic data upsert ──────────────────────────────────────────────────────
@sectors_bp.route("/data/<sector>/<tool>", methods=["POST", "PUT"])
@require_auth
@require_workspace_role("ADMIN")
def sector_data_upsert(sector: str, tool: str):
    """Upsert sector tool data from the request body."""
    ws_id = _get_workspace_id()
    if not ws_id:
        return jsonify({"ok": False, "error": "no workspace context"}), 400

    body = request.get_json(silent=True)
    if body is None:
        return jsonify({"ok": False, "error": "invalid JSON body"}), 400

    try:
        from aeon_db import upsert_sector_data
        record = upsert_sector_data(str(ws_id), sector, tool, body)
        return jsonify({"ok": True, "id": record.id, "version": record.version, "source": "db"}), 201
    except Exception as exc:
        logger.error("Failed to upsert sector data: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 500


# ── Generic data delete ──────────────────────────────────────────────────────
@sectors_bp.route("/data/<sector>/<tool>", methods=["DELETE"])
@require_auth
@require_workspace_role("ADMIN")
def sector_data_delete(sector: str, tool: str):
    """Delete sector tool data from the database."""
    ws_id = _get_workspace_id()
    if not ws_id:
        return jsonify({"ok": False, "error": "no workspace context"}), 400

    try:
        from aeon_db import delete_sector_data
        deleted = delete_sector_data(str(ws_id), sector, tool)
        return jsonify({"ok": True, "deleted": deleted})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


# ── Unified sector dashboard ─────────────────────────────────────────────────
@sectors_bp.route("/data/<sector>/dashboard", methods=["GET"])
@require_auth
@require_workspace_role("VIEWER")
def sector_dashboard_get(sector: str):
    """Aggregate every tool for a sector into a single dashboard payload.

    Returns a dictionary keyed by each tool's ``data_key``.  This lets the
    Next.js unified dashboard endpoint render the initial dashboard state
    without making N individual tool requests.
    """
    tools = [key for key in TOOL_META if key[0] == sector]
    result: dict[str, Any] = {"ok": True, "source": "db"}
    all_sources: set[str] = set()

    for tool_key in tools:
        tool = tool_key[1]
        meta = TOOL_META[tool_key]
        data_key = meta["data_key"]
        data, from_db = _get_sector_tool_data(sector, tool)
        if from_db:
            all_sources.add("db")
        else:
            data = meta["mock"]
            all_sources.add("mock")
        result[data_key] = data

    # If no tools exist for this sector, return a 404.
    if not tools:
        return jsonify({"ok": False, "error": f"Unknown sector: {sector}"}), 404

    # Determine overall source label.
    if all_sources == {"db"}:
        result["source"] = "db"
    elif all_sources == {"mock"}:
        result["source"] = "mock"
    else:
        result["source"] = "mixed"

    return jsonify(result)


# ── Seed all sectors ─────────────────────────────────────────────────────────
@sectors_bp.route("/seed", methods=["POST"])
@require_auth
@require_workspace_role("ADMIN")
def sector_seed_all():
    """Seed all 10 sectors with demo data for the current workspace."""
    ws_id = _get_workspace_id()
    if not ws_id:
        return jsonify({"ok": False, "error": "no workspace context"}), 400

    try:
        from aeon_seed_sectors import seed_all_sectors
        result = seed_all_sectors(str(ws_id))
        total = sum(result.values())
        return jsonify({
            "ok": True,
            "workspace_id": ws_id,
            "sectors_seeded": len(result),
            "tools_seeded": total,
            "detail": result,
        })
    except Exception as exc:
        logger.exception("Sector seed failed")
        return jsonify({"ok": False, "error": str(exc)}), 500


# ── Refresh a single tool ────────────────────────────────────────────────────
@sectors_bp.route("/data/<sector>/<tool>/refresh", methods=["POST"])
@require_auth
@require_workspace_role("ADMIN")
def sector_tool_refresh(sector: str, tool: str):
    """Regenerate live data for a single sector/tool and persist it."""
    ws_id = _get_workspace_id()
    if not ws_id:
        return jsonify(_WORKSPACE_CTX_ERR), 400

    if generate_sector_tool_data is None:
        return jsonify({"ok": False, "error": "live generator unavailable"}), 503

    try:
        from aeon_db import upsert_sector_data
        live_data = generate_sector_tool_data(sector, tool)
        upsert_sector_data(str(ws_id), sector, tool, live_data)
        return jsonify({"ok": True, "sector": sector, "tool": tool, "source": "db"})
    except Exception as exc:
        logger.exception("Failed to refresh %s/%s", sector, tool)
        return jsonify({"ok": False, "error": str(exc)}), 500


# ── Refresh all tools / a single sector ──────────────────────────────────────
@sectors_bp.route("/refresh", methods=["POST"])
@require_auth
@require_workspace_role("ADMIN")
def sector_refresh_all():
    """Regenerate live data for the whole workspace.

    Accepts an optional JSON body ``{"sector": "..."}`` to limit refresh to
    one sector. Persists every generated dataset to Postgres.
    """
    ws_id = _get_workspace_id()
    if not ws_id:
        return jsonify(_WORKSPACE_CTX_ERR), 400

    if generate_sector_tool_data is None or refresh_all is None:
        return jsonify({"ok": False, "error": "live generator unavailable"}), 503

    body = request.get_json(silent=True) or {}
    target_sector = body.get("sector")

    try:
        from aeon_db import upsert_sector_data

        # Refresh a single sector, or every sector represented in TOOL_META.
        sectors_to_refresh = [target_sector] if target_sector else sorted({key[0] for key in TOOL_META})

        refreshed: dict[str, int] = {}
        for sector in sectors_to_refresh:
            tools = [tool for sec, tool in TOOL_META if sec == sector]
            count = 0
            for tool in tools:
                live_data = generate_sector_tool_data(sector, tool)
                upsert_sector_data(str(ws_id), sector, tool, live_data)
                count += 1
            refreshed[sector] = count

        return jsonify({"ok": True, "workspace_id": ws_id, "refreshed": refreshed})
    except Exception as exc:
        logger.exception("Failed to refresh sectors")
        return jsonify({"ok": False, "error": str(exc)}), 500
