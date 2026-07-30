"""
AEON OS — Sector Data Seeder
==============================
Seeds a workspace with realistic demo data for all 10 industry sectors
and their tools (40 tool endpoints total).

Usage:
    from aeon_seed_sectors import seed_all_sectors
    seed_all_sectors("workspace-uuid")

Or run as a script:
    python aeon_seed_sectors.py <workspace_id>
"""

from __future__ import annotations

import logging
import sys
from typing import Any

logger = logging.getLogger("aeon_seed_sectors")


def _sector_data() -> dict[str, dict[str, Any]]:
    """Return the canonical seed data for all 10 sectors × 4-5 tools each."""
    return {
        # ═══ Cybersecurity ═══
        "cybersecurity": {
            "threats": [
                {"id": "TH-001", "indicator": "192.0.2.45", "type": "IP", "severity": "high", "status": "blocked", "first_seen": "2026-07-28T10:00:00Z", "last_seen": "2026-07-30T08:00:00Z"},
                {"id": "TH-002", "indicator": "a1b2c3d4e5f6...", "type": "Hash", "severity": "critical", "status": "quarantined", "first_seen": "2026-07-27T22:00:00Z", "last_seen": "2026-07-30T06:00:00Z"},
                {"id": "TH-003", "indicator": "phish.example.com", "type": "Domain", "severity": "medium", "status": "monitored", "first_seen": "2026-07-29T12:00:00Z", "last_seen": "2026-07-30T07:30:00Z"},
                {"id": "TH-004", "indicator": "10.0.0.99", "type": "IP", "severity": "low", "status": "investigating", "first_seen": "2026-07-30T01:00:00Z", "last_seen": "2026-07-30T08:00:00Z"},
            ],
            "vulnerabilities": [
                {"cve": "CVE-2024-0001", "severity": "Critical", "cvss": 9.8, "affected": "example-lib", "patch_available": True, "discovered": "2026-07-15"},
                {"cve": "CVE-2024-0002", "severity": "High", "cvss": 7.5, "affected": "auth-service", "patch_available": False, "discovered": "2026-07-20"},
                {"cve": "CVE-2024-0003", "severity": "Medium", "cvss": 5.3, "affected": "api-gateway", "patch_available": True, "discovered": "2026-07-25"},
                {"cve": "CVE-2024-0004", "severity": "Low", "cvss": 3.2, "affected": "logging-lib", "patch_available": True, "discovered": "2026-07-28"},
            ],
            "compliance": {
                "framework": "NIST-CSF",
                "score": 84,
                "maturity": "Managed",
                "gaps": ["IAM review", "Log retention", "Incident response automation"],
                "last_assessment": "2026-07-28",
            },
            "ip-reputation": {
                "score": 0.18,
                "known_malicious": False,
                "source_countries": ["US", "DE", "JP"],
                "last_seen_days": 2,
            },
            "news": [
                {"title": "Critical OpenSSH vulnerability disclosed", "url": "#", "source": "CVE Database", "date": "2026-07-29"},
                {"title": "New ransomware group targets healthcare sector", "url": "#", "source": "Threat Intel", "date": "2026-07-28"},
                {"title": "Zero-day exploit detected in popular VPN client", "url": "#", "source": "Security Advisory", "date": "2026-07-27"},
            ],
        },
        # ═══ Health ═══
        "health": {
            "diagnostics": [
                {"analyzed_symptoms": "fever, cough, fatigue", "possible_conditions": [{"name": "viral infection", "probability": 0.78, "severity": "moderate", "action": "rest and monitor"}], "urgency": "moderate", "recommendation": "rest and monitor"},
                {"analyzed_symptoms": "chest pain, shortness of breath", "possible_conditions": [{"name": "cardiac concern", "probability": 0.65, "severity": "high", "action": "immediate evaluation"}], "urgency": "high", "recommendation": "immediate evaluation"},
                {"analyzed_symptoms": "headache, nausea", "possible_conditions": [{"name": "migraine", "probability": 0.72, "severity": "moderate", "action": "hydration and rest"}], "urgency": "moderate", "recommendation": "hydration and rest"},
            ],
            "vitals": [
                {"patient_id": "P-1001", "metric": "heart_rate", "baseline": 72, "current": 72, "trend": "stable", "alert": False},
                {"patient_id": "P-1001", "metric": "blood_pressure_sys", "baseline": 120, "current": 118, "trend": "stable", "alert": False},
                {"patient_id": "P-1002", "metric": "heart_rate", "baseline": 72, "current": 95, "trend": "rising", "alert": True},
                {"patient_id": "P-1002", "metric": "blood_pressure_sys", "baseline": 120, "current": 142, "trend": "rising", "alert": True},
                {"patient_id": "P-1003", "metric": "oxygen_saturation", "baseline": 98, "current": 92, "trend": "falling", "alert": True},
            ],
            "drug-interactions": [
                {"medications": ["aspirin", "warfarin"], "interactions_found": 1, "interactions": [{"drugs": ["aspirin", "warfarin"], "severity": "moderate", "warning": "increased bleeding risk"}]},
                {"medications": ["lisinopril", "potassium"], "interactions_found": 1, "interactions": [{"drugs": ["lisinopril", "potassium"], "severity": "high", "warning": "hyperkalemia risk"}]},
                {"medications": ["metformin", "losartan"], "interactions_found": 0, "interactions": []},
            ],
            "telehealth": [
                {"symptoms": "chest pain", "age": 65, "urgency": "emergent", "recommendation": "call 911"},
                {"symptoms": "fever", "age": 30, "urgency": "non-urgent", "recommendation": "schedule virtual visit"},
                {"symptoms": "skin rash", "age": 42, "urgency": "routine", "recommendation": "upload photos for dermatology review"},
                {"symptoms": "cough", "age": 55, "urgency": "non-urgent", "recommendation": "schedule virtual visit"},
            ],
        },
        # ═══ Finance ═══
        "finance": {
            "risk": {
                "asset": "S&P 500", "portfolio_value": 500000, "var_95_1d": 12500, "var_95_pct": 2.5,
                "sharpe_estimate": 1.45, "beta": 0.98, "risk_rating": "medium", "diversification_score": 7,
                "recommendation": "diversify fixed income",
            },
            "market": {
                "market": "NASDAQ", "predicted_direction": "bullish", "confidence": 0.72,
                "price_target_pct": 4.2, "volatility_forecast": "moderate",
                "key_indicators": {"rsi": 62, "macd": "bullish_cross", "moving_avg_50": 18500, "moving_avg_200": 17200},
            },
            "fraud": [
                {"transaction_id": "TXN-5001", "amount": 5000, "fraud_score": 0.85, "risk_level": "high", "action": "blocked", "timestamp": "2026-07-30T04:00:00Z"},
                {"transaction_id": "TXN-5002", "amount": 35, "fraud_score": 0.05, "risk_level": "low", "action": "approved", "timestamp": "2026-07-30T05:00:00Z"},
                {"transaction_id": "TXN-5003", "amount": 25000, "fraud_score": 0.72, "risk_level": "high", "action": "flagged", "timestamp": "2026-07-30T06:00:00Z"},
            ],
            "credit": [
                {"applicant_id": "APP-200", "credit_score": 720, "rating": "Good", "approval_probability": 0.92, "recommended_limit": 15000},
                {"applicant_id": "APP-201", "credit_score": 580, "rating": "Poor", "approval_probability": 0.18, "recommended_limit": 0},
                {"applicant_id": "APP-202", "credit_score": 810, "rating": "Excellent", "approval_probability": 0.99, "recommended_limit": 50000},
            ],
            "payments": [
                {"account_id": "ACC-1234", "total_transactions": 142, "total_volume": 48500, "anomaly_count": 1, "spending_trend": "stable"},
                {"account_id": "ACC-5678", "total_transactions": 89, "total_volume": 22300, "anomaly_count": 3, "spending_trend": "increasing"},
                {"account_id": "ACC-9012", "total_transactions": 312, "total_volume": 128000, "anomaly_count": 0, "spending_trend": "stable"},
            ],
        },
        # ═══ Retail ═══
        "retail": {
            "forecast": [
                {"sku": "SKU-001", "current_stock": 850, "projected_demand": 1240, "recommended_order_qty": 390, "confidence": 0.92},
                {"sku": "SKU-042", "current_stock": 420, "projected_demand": 680, "recommended_order_qty": 260, "confidence": 0.88},
                {"sku": "SKU-099", "current_stock": 2100, "projected_demand": 1890, "recommended_order_qty": 0, "confidence": 0.95},
                {"sku": "SKU-107", "current_stock": 120, "projected_demand": 340, "recommended_order_qty": 220, "confidence": 0.76},
                {"sku": "SKU-215", "current_stock": 560, "projected_demand": 890, "recommended_order_qty": 330, "confidence": 0.84},
            ],
            "inventory": {
                "alerts": [{"sku": "SKU-107", "status": "stockout_risk", "days_remaining": 2}],
                "reorder_recommendations": [{"sku": "SKU-107", "qty": 220, "supplier": "Alpha Corp", "est_delivery_days": 3}, {"sku": "SKU-042", "qty": 260, "supplier": "Gamma Wholesale", "est_delivery_days": 5}],
                "healthy": [{"sku": "SKU-001", "status": "healthy", "days_supply": 21}, {"sku": "SKU-099", "status": "overstock", "days_supply": 75, "suggestion": "run promotion"}, {"sku": "SKU-215", "status": "healthy", "days_supply": 18}],
                "summary": {"total_skus": 5, "stockout_risks": 1, "overstocks": 1, "healthy": 3},
            },
            "suppliers": [
                {"supplier": "Alpha Corp", "risk_score": 15, "classification": "Low Risk", "on_time_delivery_pct": 96, "contract_end": "2027-03-01"},
                {"supplier": "Beta Logistics", "risk_score": 42, "classification": "Medium Risk", "on_time_delivery_pct": 82, "contract_end": "2026-12-01"},
                {"supplier": "Gamma Wholesale", "risk_score": 8, "classification": "Low Risk", "on_time_delivery_pct": 99, "contract_end": "2028-01-01"},
                {"supplier": "Delta Distributors", "risk_score": 71, "classification": "High Risk", "on_time_delivery_pct": 61, "contract_end": "2026-09-15"},
            ],
            "pricing": {
                "sku": "SKU-001", "price_change_pct": 10, "elasticity": -0.42,
                "projected_demand_change_pct": -4.2, "optimal_price": 32.50, "current_price": 29.99,
            },
        },
        # ═══ Transport ═══
        "transport": {
            "traffic": [
                {"zone": "downtown", "current_congestion": 8.2, "predicted_improvement": "divert to ring road", "incident_nearby": True},
                {"zone": "midtown", "current_congestion": 6.5, "predicted_improvement": "monitor", "incident_nearby": False},
                {"zone": "airport_corridor", "current_congestion": 9.1, "predicted_improvement": "activate bus lane", "incident_nearby": True},
                {"zone": "suburb_east", "current_congestion": 3.8, "predicted_improvement": "normal flow", "incident_nearby": False},
                {"zone": "harbor_district", "current_congestion": 5.2, "predicted_improvement": "adjust signal timing", "incident_nearby": False},
            ],
            "fleet": [
                {"depot": "North Hub", "vehicles_available": 10, "shifts": 3, "utilization_pct": 87, "recommendation": "reduce 1 vehicle"},
                {"depot": "South Hub", "vehicles_available": 8, "shifts": 2, "utilization_pct": 72, "recommendation": "reduce 2 vehicles"},
                {"depot": "Central Hub", "vehicles_available": 15, "shifts": 3, "utilization_pct": 93, "recommendation": "optimal"},
                {"depot": "East Hub", "vehicles_available": 6, "shifts": 1, "utilization_pct": 82, "recommendation": "add 1 vehicle"},
            ],
            "routes": [
                {"stops": ["A", "B", "C", "D", "E"], "estimated_distance_km": 42, "estimated_time_min": 55, "fuel_cost_est": 18.50, "optimized": True},
                {"stops": ["F", "G", "H", "I", "J"], "estimated_distance_km": 38, "estimated_time_min": 48, "fuel_cost_est": 16.20, "optimized": True},
                {"stops": ["K", "L", "M", "N", "O"], "estimated_distance_km": 56, "estimated_time_min": 72, "fuel_cost_est": 24.80, "optimized": False},
            ],
        },
        # ═══ Manufacturing ═══
        "manufacturing": {
            "maintenance": [
                {"machine_id": "CNC-01", "status": "good", "temp_c": 42, "vibration_hz": 12.5, "failure_risk_pct": 12, "days_to_failure": 45, "last_service": "2026-06-15"},
                {"machine_id": "CNC-02", "status": "warning", "temp_c": 58, "vibration_hz": 18.2, "failure_risk_pct": 34, "days_to_failure": 12, "last_service": "2026-05-01"},
                {"machine_id": "CNC-03", "status": "good", "temp_c": 44, "vibration_hz": 11.8, "failure_risk_pct": 15, "days_to_failure": 30, "last_service": "2026-07-01"},
                {"machine_id": "CNC-04", "status": "critical", "temp_c": 78, "vibration_hz": 31.4, "failure_risk_pct": 89, "days_to_failure": 3, "last_service": "2026-03-20"},
                {"machine_id": "CNC-05", "status": "good", "temp_c": 40, "vibration_hz": 10.1, "failure_risk_pct": 8, "days_to_failure": 60, "last_service": "2026-07-10"},
            ],
            "quality": [
                {"batch_id": "B-998", "items_scanned": 500, "defects_found": 10, "defect_rate": 0.02, "status": "pass"},
                {"batch_id": "B-999", "items_scanned": 500, "defects_found": 35, "defect_rate": 0.07, "status": "fail", "root_cause": "calibration drift"},
                {"batch_id": "B-1000", "items_scanned": 500, "defects_found": 5, "defect_rate": 0.01, "status": "pass"},
            ],
            "logistics": [
                {"route_id": "R-10", "status": "on_time", "eta_days": 1, "reroute_cost_usd": 0},
                {"route_id": "R-11", "status": "delayed", "eta_days": 3, "reroute_cost_usd": 1800, "delay_reason": "weather"},
                {"route_id": "R-12", "status": "on_time", "eta_days": 2, "reroute_cost_usd": 0},
                {"route_id": "R-13", "status": "on_time", "eta_days": 4, "reroute_cost_usd": 0},
            ],
        },
        # ═══ Tourism ═══
        "tourism": {
            "bookings": [
                {"property": "Hotel-Central", "occupancy_pct": 82, "predictive_no_shows": 14, "net_expected_occupancy": 78, "revenue_ytd": 1250000},
                {"property": "Hotel-West", "occupancy_pct": 68, "predictive_no_shows": 18, "net_expected_occupancy": 64, "revenue_ytd": 890000},
                {"property": "Hotel-Airport", "occupancy_pct": 91, "predictive_no_shows": 22, "net_expected_occupancy": 89, "revenue_ytd": 2100000},
            ],
            "pricing": [
                {"room": "King Suite", "base_price": 299, "recommended_price": 320, "reason": "High demand", "demand_level": "high"},
                {"room": "Double Queen", "base_price": 259, "recommended_price": 245, "reason": "Medium demand", "demand_level": "medium"},
                {"room": "Standard", "base_price": 169, "recommended_price": 175, "reason": "Low demand, hold", "demand_level": "low"},
            ],
            "concierge": [
                {"guest_id": "G-445", "sentiment": "positive", "intent": "dining reservation", "automated_response": "Reservation confirmed at 8 PM", "upsell": "Wine pairing package"},
                {"guest_id": "G-446", "sentiment": "neutral", "intent": "housekeeping request", "automated_response": "Housekeeping dispatched", "upsell": None},
                {"guest_id": "G-447", "sentiment": "negative", "intent": "transport to airport", "automated_response": "Taxi booked for 6 AM", "upsell": None},
            ],
            "visitors": [
                {"venue": "National Museum", "daily_visitors": 1200, "engagement_score": 92, "recommended_strategies": ["extend hours weekends", "new family tour"]},
                {"venue": "Modern Art Gallery", "daily_visitors": 680, "engagement_score": 88, "recommended_strategies": ["new exhibition promo"]},
                {"venue": "History Center", "daily_visitors": 450, "engagement_score": 85, "recommended_strategies": ["school program expansion"]},
            ],
        },
        # ═══ Utilities ═══
        "utilities": {
            "resources": [
                {"resource": "water", "demand": 1000, "supply": 850, "deficit": 150, "status": "critical", "optimization_suggestion": "implement tiered pricing"},
                {"resource": "electricity", "demand": 500, "supply": 480, "deficit": 20, "status": "warning", "optimization_suggestion": "demand response program"},
                {"resource": "natural_gas", "demand": 300, "supply": 320, "deficit": 0, "status": "good"},
            ],
            "services": [
                {"service": "waste_collection", "kpi_score": 0.89, "status": "satisfactory", "citizen_satisfaction": 0.78, "trend": "stable"},
                {"service": "street_lighting", "kpi_score": 0.97, "status": "excellent", "citizen_satisfaction": 0.92, "trend": "improving"},
                {"service": "public_transport", "kpi_score": 0.82, "status": "needs improvement", "citizen_satisfaction": 0.65, "trend": "declining"},
            ],
            "waste": [
                {"district": "Zone A", "total_waste_tons": 1200, "recycled_pct": 35, "landfill_pct": 65, "collection_efficiency": 0.92},
                {"district": "Zone B", "total_waste_tons": 850, "recycled_pct": 22, "landfill_pct": 78, "collection_efficiency": 0.78},
                {"district": "Zone C", "total_waste_tons": 1600, "recycled_pct": 41, "landfill_pct": 59, "collection_efficiency": 0.95},
            ],
            "grid": [
                {"region": "North Grid", "current_load_mw": 245, "capacity_mw": 280, "utilization_pct": 87.5, "renewable_share_pct": 38, "status": "stable"},
                {"region": "South Grid", "current_load_mw": 312, "capacity_mw": 300, "utilization_pct": 104, "renewable_share_pct": 22, "status": "critical", "action": "activate backup generators"},
                {"region": "East Grid", "current_load_mw": 198, "capacity_mw": 260, "utilization_pct": 76.2, "renewable_share_pct": 45, "status": "stable"},
                {"region": "West Grid", "current_load_mw": 178, "capacity_mw": 240, "utilization_pct": 74.2, "renewable_share_pct": 52, "status": "stable"},
            ],
        },
        # ═══ Cultural Heritage ═══
        "cultural_heritage": {
            "visitors": [
                {"venue": "National Museum", "daily_visitors": 1200, "engagement_score": 92, "recommended_strategies": ["extend hours weekends", "new family tour"]},
                {"venue": "Modern Art Gallery", "daily_visitors": 680, "engagement_score": 88, "recommended_strategies": ["new exhibition promo"]},
                {"venue": "History Center", "daily_visitors": 450, "engagement_score": 85, "recommended_strategies": ["school program expansion"]},
            ],
            "sites": [
                {"site": "Colosseum", "era": "Ancient Rome", "significance": "Iconic amphitheatre", "annual_visitors": 7400000, "conservation_status": "good"},
                {"site": "Machu Picchu", "era": "Inca Empire", "significance": "Citadel in the Andes", "annual_visitors": 2500000, "conservation_status": "requires attention"},
                {"site": "Angkor Wat", "era": "Khmer Empire", "significance": "Largest religious monument", "annual_visitors": 2600000, "conservation_status": "fair"},
            ],
            "exhibitions": [
                {"theme": "Modern Art", "recommended_duration_days": 90, "estimated_visitors": 80000, "ticket_price": 25, "projected_revenue": 2000000},
                {"theme": "Ancient Egypt", "recommended_duration_days": 60, "estimated_visitors": 60000, "ticket_price": 22, "projected_revenue": 1320000},
                {"theme": "Space Exploration", "recommended_duration_days": 45, "estimated_visitors": 45000, "ticket_price": 28, "projected_revenue": 1260000},
            ],
            "tours": [
                {"site": "Louvre Museum", "interest": "art", "narration": "Explore the Mona Lisa and French masters", "audio_duration_seconds": 2100},
                {"site": "British Museum", "interest": "history", "narration": "Journey through 2 million years of history", "audio_duration_seconds": 2400},
                {"site": "Uffizi Gallery", "interest": "architecture", "narration": "Renaissance art and architecture", "audio_duration_seconds": 1680},
            ],
        },
        # ═══ SME ═══
        "sme": {
            "workflows": [
                {"process": "invoice_approval", "employees_involved": 5, "hours_saved_per_month": 120, "cost_savings_annual": 24000, "automation_rate": 0.85},
                {"process": "employee_onboarding", "employees_involved": 3, "hours_saved_per_month": 80, "cost_savings_annual": 16000, "automation_rate": 0.72},
                {"process": "report_generation", "employees_involved": 2, "hours_saved_per_month": 60, "cost_savings_annual": 12000, "automation_rate": 0.94},
                {"process": "expense_reporting", "employees_involved": 4, "hours_saved_per_month": 95, "cost_savings_annual": 19000, "automation_rate": 0.78},
            ],
            "documents": [
                {"document_type": "invoice", "confidence": 0.97, "pages_processed": 142, "fields_extracted": ["vendor", "amount", "due_date"], "status": "completed"},
                {"document_type": "contract", "confidence": 0.94, "pages_processed": 38, "fields_extracted": ["parties", "term", "liability"], "status": "completed"},
                {"document_type": "receipt", "confidence": 0.96, "pages_processed": 210, "fields_extracted": ["merchant", "total", "date"], "status": "pending"},
            ],
            "support": [
                {"query": "Where is my order?", "detected_intent": "order_status", "sentiment": "frustrated", "response": "Tracking link sent", "escalated": False},
                {"query": "I want a refund", "detected_intent": "refund", "sentiment": "angry", "response": "Refund initiated", "escalated": True},
                {"query": "My account is locked", "detected_intent": "account_access", "sentiment": "neutral", "response": "Unlocked with MFA reset", "escalated": False},
            ],
            "supply-chain": [
                {"chain_id": "SC-001", "health_score": 92, "lead_time_days": 5, "risk_level": "low", "bottlenecks": []},
                {"chain_id": "SC-002", "health_score": 68, "lead_time_days": 14, "risk_level": "medium", "bottlenecks": ["distributor delay"]},
                {"chain_id": "SC-003", "health_score": 85, "lead_time_days": 7, "risk_level": "low", "bottlenecks": []},
            ],
        },
    }


def seed_all_sectors(workspace_id: str) -> dict[str, int]:
    """Seed all 10 sectors with demo data for a workspace.

    Returns a dict mapping sector_id -> number of tools seeded.
    Is idempotent — calling it again replaces existing data.
    """
    from aeon_db import get_db, upsert_sector_data

    data = _sector_data()
    result: dict[str, int] = {}

    for sector_id, tools in data.items():
        seeded = 0
        for tool_name, tool_data in tools.items():
            upsert_sector_data(workspace_id, sector_id, tool_name, tool_data)
            seeded += 1
        result[sector_id] = seeded
        logger.info("Seeded %s: %d tools", sector_id, seeded)

    total = sum(result.values())
    logger.info("Total: %d tools seeded across %d sectors", total, len(result))
    return result


def seed_sector(workspace_id: str, sector_id: str) -> int:
    """Seed a single sector with demo data.

    Returns the number of tools seeded (0 if sector unknown).
    """
    from aeon_db import get_db, upsert_sector_data

    data = _sector_data()
    tools = data.get(sector_id)
    if not tools:
        logger.warning("Unknown sector: %s", sector_id)
        return 0

    seeded = 0
    for tool_name, tool_data in tools.items():
        upsert_sector_data(workspace_id, sector_id, tool_name, tool_data)
        seeded += 1
    logger.info("Seeded %s: %d tools", sector_id, seeded)
    return seeded


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    if len(sys.argv) < 2:
        print("Usage: python aeon_seed_sectors.py <workspace_id>")
        sys.exit(1)

    workspace_id = sys.argv[1]
    result = seed_all_sectors(workspace_id)
    print(f"Seeded {sum(result.values())} tools across {len(result)} sectors")
    for sector, count in result.items():
        print(f"  {sector}: {count} tools")
