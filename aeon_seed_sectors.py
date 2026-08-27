"""
AEON OS — Sector Data Seeder
==============================
Seeds a workspace with realistic demo data for all 16 industry sectors
and their tools (58 tool endpoints total).

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
    """Return the canonical static seed data for all 20 sectors.

    Used when the live generator is unavailable (``live=False``); the shapes
    mirror the TOOL_META mocks in aeon_sectors.py.
    """
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
        # ═══ Telecom ═══
        "telecom": {
            "network": [
                {"id": "tel-1", "element": "core_router_01", "type": "core", "health_score": 99.2, "uptime_pct": 99.2, "sla_status": "met", "region": "US-East"},
                {"id": "tel-2", "element": "edge_switch_14", "type": "edge", "health_score": 97.5, "uptime_pct": 97.5, "sla_status": "met", "region": "US-East"},
                {"id": "tel-3", "element": "radio_tower_07", "type": "radio", "health_score": 95.4, "uptime_pct": 95.4, "sla_status": "at_risk", "region": "US-West"},
                {"id": "tel-4", "element": "backhaul_05", "type": "transport", "health_score": 94.7, "uptime_pct": 94.7, "sla_status": "breached", "region": "APAC"},
            ],
            "capacity": [
                {"id": "cap-1", "node": "backbone_01", "current_utilization_pct": 82, "forecast_utilization_pct": 95, "recommended_action": "add_capacity"},
                {"id": "cap-2", "node": "backbone_02", "current_utilization_pct": 58, "forecast_utilization_pct": 66, "recommended_action": "monitor"},
                {"id": "cap-3", "node": "metro_agg_11", "current_utilization_pct": 91, "forecast_utilization_pct": 104, "recommended_action": "rebalance_traffic"},
                {"id": "cap-4", "node": "edge_pop_03", "current_utilization_pct": 44, "forecast_utilization_pct": 52, "recommended_action": "no_action"},
            ],
            "faults": [
                {"id": "fault-1", "element": "core_router_01", "severity": "high", "status": "fixing", "opened_at": "2026-08-19T08:30:00Z", "summary": "Packet loss above 2% threshold"},
                {"id": "fault-2", "element": "radio_tower_07", "severity": "medium", "status": "triage", "opened_at": "2026-08-19T09:15:00Z", "summary": "Handover failures on small cell"},
                {"id": "fault-3", "element": "backhaul_05", "severity": "critical", "status": "open", "opened_at": "2026-08-19T10:00:00Z", "summary": "Optical signal attenuation on fiber"},
            ],
        },
        # ═══ Agriculture ═══
        "agriculture": {
            "yield": [
                {"id": "yld-1", "field": "field_alpha", "crop": "wheat", "forecast_tons": 320.5, "previous_tons": 295.0, "confidence": 0.91},
                {"id": "yld-2", "field": "field_beta", "crop": "corn", "forecast_tons": 410.2, "previous_tons": 380.4, "confidence": 0.87},
                {"id": "yld-3", "field": "field_gamma", "crop": "soybean", "forecast_tons": 215.8, "previous_tons": 228.1, "confidence": 0.84},
                {"id": "yld-4", "field": "field_delta", "crop": "barley", "forecast_tons": 190.3, "previous_tons": 175.6, "confidence": 0.89},
            ],
            "irrigation": [
                {"id": "irr-1", "zone": "zone_north", "crop": "wheat", "schedule": "sensor_triggered", "water_needed_mm": 32, "status": "optimal"},
                {"id": "irr-2", "zone": "zone_south", "crop": "corn", "schedule": "every_2_days", "water_needed_mm": 48, "status": "low"},
                {"id": "irr-3", "zone": "zone_east", "crop": "soybean", "schedule": "daily", "water_needed_mm": 22, "status": "optimal"},
                {"id": "irr-4", "zone": "zone_west", "crop": "barley", "schedule": "weekly", "water_needed_mm": 18, "status": "optimal"},
            ],
            "pests": [
                {"id": "pst-1", "field": "field_alpha", "crop": "wheat", "pest": "aphid", "risk_level": "moderate", "treatment": "targeted_spray"},
                {"id": "pst-2", "field": "field_beta", "crop": "corn", "pest": "corn_borer", "risk_level": "low", "treatment": "biological_control"},
                {"id": "pst-3", "field": "field_gamma", "crop": "soybean", "pest": "armyworm", "risk_level": "high", "treatment": "quarantine_zone"},
                {"id": "pst-4", "field": "field_delta", "crop": "barley", "pest": "rust_fungus", "risk_level": "low", "treatment": "none_required"},
            ],
        },
        # ═══ Education ═══
        "education": {
            "at-risk": [
                {"id": "stu-1", "student_id": "S-2026-1001", "name": "Ava Thompson", "gpa": 2.1, "attendance_pct": 74, "risk_score": 0.82, "risk_level": "high"},
                {"id": "stu-2", "student_id": "S-2026-1002", "name": "Liam Rodriguez", "gpa": 3.4, "attendance_pct": 96, "risk_score": 0.22, "risk_level": "low"},
                {"id": "stu-3", "student_id": "S-2026-1003", "name": "Maya Patel", "gpa": 2.8, "attendance_pct": 85, "risk_score": 0.55, "risk_level": "watch"},
                {"id": "stu-4", "student_id": "S-2026-1004", "name": "Noah Kim", "gpa": 1.9, "attendance_pct": 61, "risk_score": 0.93, "risk_level": "high"},
            ],
            "interventions": [
                {"id": "plan-1", "student_id": "S-2026-1001", "plan": "Attendance Recovery", "actions": ["counseling", "parent_meeting"], "status": "active", "owner": "Advisor Ward"},
                {"id": "plan-2", "student_id": "S-2026-1004", "plan": "Academic Support", "actions": ["tutoring", "mentorship"], "status": "active", "owner": "Dean Patel"},
                {"id": "plan-3", "student_id": "S-2026-1003", "plan": "Social-Emotional Support", "actions": ["counseling"], "status": "draft", "owner": "Counselor Reed"},
            ],
            "outcomes": [
                {"id": "out-1", "program": "STEM Accelerator", "completion_rate": 0.88, "avg_score": 84.2, "trend": "improving"},
                {"id": "out-2", "program": "Literacy Boost", "completion_rate": 0.79, "avg_score": 76.5, "trend": "stable"},
                {"id": "out-3", "program": "Math Recovery", "completion_rate": 0.64, "avg_score": 68.1, "trend": "improving"},
                {"id": "out-4", "program": "College Readiness", "completion_rate": 0.92, "avg_score": 89.7, "trend": "improving"},
            ],
        },
        # ═══ Public Safety ═══
        "public_safety": {
            "incidents": [
                {"id": "inc-1", "incident_id": "INC-2026001", "type": "traffic_accident", "priority": "high", "status": "on_scene", "location": "Downtown", "reported_at": "2026-08-19T08:05:00Z"},
                {"id": "inc-2", "incident_id": "INC-2026002", "type": "medical_emergency", "priority": "critical", "status": "dispatched", "location": "Riverside", "reported_at": "2026-08-19T09:40:00Z"},
                {"id": "inc-3", "incident_id": "INC-2026003", "type": "theft", "priority": "medium", "status": "resolving", "location": "Northgate", "reported_at": "2026-08-19T10:12:00Z"},
                {"id": "inc-4", "incident_id": "INC-2026004", "type": "fire_report", "priority": "high", "status": "on_scene", "location": "Southside", "reported_at": "2026-08-19T10:55:00Z"},
            ],
            "dispatch": [
                {"id": "disp-1", "unit_id": "unit_101", "unit_type": "patrol_car", "status": "en_route", "current_incident": "INC-2026001", "eta_minutes": 4},
                {"id": "disp-2", "unit_id": "unit_207", "unit_type": "ambulance", "status": "on_scene", "current_incident": "INC-2026002", "eta_minutes": 0},
                {"id": "disp-3", "unit_id": "unit_309", "unit_type": "fire_engine", "status": "available", "current_incident": "none", "eta_minutes": 12},
                {"id": "disp-4", "unit_id": "unit_114", "unit_type": "motorcycle_unit", "status": "returning", "current_incident": "none", "eta_minutes": 8},
            ],
            "briefs": [
                {"id": "brf-1", "title": "Overnight Shift Summary", "period": "24h", "highlights": "Property crimes down 8%; one critical response in Riverside", "recommendations": ["Extend night patrol coverage", "Deploy traffic units pre-rush"]},
                {"id": "brf-2", "title": "Weekend Operations Review", "period": "72h", "highlights": "Traffic incidents up 12% near airport; added patrol coverage", "recommendations": ["Pre-position medics at venues", "Monitor hot spots"]},
                {"id": "brf-3", "title": "Special Event Plan", "period": "weekly", "highlights": "Concert attendance 40k — staged resource plan active", "recommendations": ["Review camera coverage gaps", "Add drone support"]},
            ],
        },
        # ═══ Real Estate ═══
        "real_estate": {
            "valuations": [
                {"id": "val-1", "property": "24 Maple Avenue", "type": "single_family", "valuation": 645000, "estimate_low": 612000, "estimate_high": 689000, "confidence": 0.94, "location": "Midtown"},
                {"id": "val-2", "property": "88 Harbor Drive", "type": "condo", "valuation": 412000, "estimate_low": 388000, "estimate_high": 443000, "confidence": 0.91, "location": "Westside"},
                {"id": "val-3", "property": "1500 Oak Street", "type": "multi_family", "valuation": 1180000, "estimate_low": 1105000, "estimate_high": 1275000, "confidence": 0.88, "location": "East Village"},
                {"id": "val-4", "property": "330 Commerce Blvd", "type": "commercial", "valuation": 1420000, "estimate_low": 1330000, "estimate_high": 1520000, "confidence": 0.86, "location": "Lake District"},
            ],
            "market": [
                {"id": "mkt-1", "region": "Midtown", "median_price": 645000, "price_change_pct": 4.2, "inventory": 84, "days_on_market": 24},
                {"id": "mkt-2", "region": "Westside", "median_price": 512000, "price_change_pct": 2.8, "inventory": 61, "days_on_market": 31},
                {"id": "mkt-3", "region": "East Village", "median_price": 738000, "price_change_pct": 6.5, "inventory": 47, "days_on_market": 18},
                {"id": "mkt-4", "region": "Lake District", "median_price": 895000, "price_change_pct": -1.6, "inventory": 32, "days_on_market": 48},
            ],
            "comparables": [
                {"id": "cmp-1", "property": "24 Maple Avenue", "comparable_address": "26 Maple Avenue", "price": 628000, "sqft": 2450, "delta_pct": -2.6},
                {"id": "cmp-2", "property": "24 Maple Avenue", "comparable_address": "30 Maple Avenue", "price": 671000, "sqft": 2580, "delta_pct": 4.0},
                {"id": "cmp-3", "property": "88 Harbor Drive", "comparable_address": "90 Harbor Drive", "price": 398000, "sqft": 1380, "delta_pct": -3.4},
                {"id": "cmp-4", "property": "1500 Oak Street", "comparable_address": "1496 Oak Street", "price": 1125000, "sqft": 4100, "delta_pct": -4.6},
            ],
        },
        # ═══ Professional Services ═══
        "professional": {
            "legal": [
                {"doc": "Service Agreement", "type": "contract", "risk_score": "medium", "obligations": ["Confidentiality", "Indemnification"]},
                {"doc": "NDA", "type": "non-disclosure", "risk_score": "low", "obligations": ["Confidentiality"]},
                {"doc": "Employment Contract", "type": "employment", "risk_score": "medium", "obligations": ["Non-compete", "IP Assignment"]},
                {"doc": "Lease Agreement", "type": "lease", "risk_score": "high", "obligations": ["Termination Notice", "Indemnification"]},
            ],
            "accounting": [
                {"invoice_id": "INV-1001", "vendor": "Acme Corp", "amount": 4200, "anomalies_detected": True, "auto_approved": False},
                {"invoice_id": "INV-1002", "vendor": "TechSupply Inc", "amount": 1850, "anomalies_detected": False, "auto_approved": True},
                {"invoice_id": "INV-1003", "vendor": "DataServices LLC", "amount": 6900, "anomalies_detected": False, "auto_approved": True},
                {"invoice_id": "INV-1004", "vendor": "CloudHost Ltd", "amount": 3100, "anomalies_detected": True, "auto_approved": False},
            ],
            "data-management": [
                {"dataset": "Customer DB", "pii_records_found": 1850, "compliance": "GDPR-ready"},
                {"dataset": "Employee Records", "pii_records_found": 640, "compliance": "HIPAA-compliant"},
                {"dataset": "Transaction Logs", "pii_records_found": 2300, "compliance": "needs_review"},
                {"dataset": "Marketing Data", "pii_records_found": 980, "compliance": "compliant"},
            ],
        },
        # ═══ Construction ═══
        "construction": {
            "projects": [
                {"project_id": "PRJ-7701", "name": "Harbour Point Tower", "progress_pct": 64, "budget": 18500000, "spent": 11240000, "schedule_risk": "medium"},
                {"project_id": "PRJ-7702", "name": "Northside Metro Extension", "progress_pct": 31, "budget": 42000000, "spent": 14980000, "schedule_risk": "high"},
                {"project_id": "PRJ-7703", "name": "Logistics Hub Retrofit", "progress_pct": 89, "budget": 6400000, "spent": 5610000, "schedule_risk": "low"},
            ],
            "bids": [
                {"bid_id": "BID-3301", "opportunity": "Airport Terminal Phase 2", "value": 27500000, "win_probability": 0.42, "status": "submitted"},
                {"bid_id": "BID-3302", "opportunity": "Data Center Fit-out", "value": 9800000, "win_probability": 0.67, "status": "drafting"},
                {"bid_id": "BID-3303", "opportunity": "Coastal Road Upgrade", "value": 15200000, "win_probability": 0.25, "status": "reviewing"},
            ],
        },
        # ═══ Insurance ═══
        "insurance": {
            "claims": [
                {"claim_id": "CLM-88231", "policy": "POL-55210", "type": "property_damage", "reserve": 18500, "fraud_score": 0.18, "status": "in_review"},
                {"claim_id": "CLM-88232", "policy": "POL-55344", "type": "liability", "reserve": 92000, "fraud_score": 0.61, "status": "investigation"},
                {"claim_id": "CLM-88233", "policy": "POL-55102", "type": "auto", "reserve": 4300, "fraud_score": 0.05, "status": "approved"},
            ],
            "portfolio": {
                "policies_active": 12840,
                "loss_ratio_pct": 62.4,
                "combined_ratio_pct": 96.8,
                "top_segments": [
                    {"segment": "commercial_property", "premium": 4820000, "loss_ratio": 54.1},
                    {"segment": "motor", "premium": 3610000, "loss_ratio": 71.8},
                    {"segment": "marine_cargo", "premium": 1240000, "loss_ratio": 58.3},
                ],
            },
        },
        # ═══ Legal Services ═══
        "legal": {
            "cases": [
                {"case_id": "CASE-4410", "matter": "Meridian vs. Atlas Holdings", "practice_area": "commercial", "stage": "discovery", "risk": "medium"},
                {"case_id": "CASE-4411", "matter": "In re: Nova Retail IP claim", "practice_area": "intellectual_property", "stage": "pleadings", "risk": "low"},
                {"case_id": "CASE-4412", "matter": "Estate of Callahan", "practice_area": "probate", "stage": "hearing", "risk": "low"},
            ],
            "contracts": {
                "pending_review": 7,
                "flagged_clauses": [
                    {"contract": "MSA-Delta-2026", "clause": "indemnification", "severity": "high", "note": "uncapped liability"},
                    {"contract": "NDA-Gamma", "clause": "term", "severity": "medium", "note": "auto-renews indefinitely"},
                ],
                "avg_cycle_days": 9,
            },
        },
        # ═══ Logistics ═══
        "logistics": {
            "shipments": [
                {"shipment_id": "SHP-2201", "origin": "Rotterdam", "destination": "Valletta", "carrier": "Maersk", "eta_days": 4, "status": "in_transit"},
                {"shipment_id": "SHP-2202", "origin": "Shenzhen", "destination": "Hamburg", "carrier": "DHL", "eta_days": 12, "status": "customs_hold"},
                {"shipment_id": "SHP-2203", "origin": "Chicago", "destination": "Toronto", "carrier": "FedEx", "eta_days": 2, "status": "delivered"},
                {"shipment_id": "SHP-2204", "origin": "Singapore", "destination": "Sydney", "carrier": "Kuehne+Nagel", "eta_days": 7, "status": "in_transit"},
            ],
            "fleet": {
                "vehicles_active": 42,
                "vehicles_idle": 6,
                "maintenance_due": [{"vehicle": "TRK-118", "issue": "tire_wear", "due_km": 3200}],
                "utilization_pct": 87.5,
            },
        },
    }


def seed_all_sectors(workspace_id: str, *, live: bool = True) -> dict[str, int]:
    """Seed all registered sectors with data for a workspace.

    By default, ``live=True`` generates time-varying data and persists it to
    Postgres. Pass ``live=False`` to fall back to the canonical static demo
    data (covers every sector in the tenant registry).

    Returns a dict mapping sector_id -> number of tools seeded.
    Is idempotent — calling it again replaces existing data.
    """
    from aeon_db import upsert_sector_data

    result: dict[str, int] = {}

    if live:
        from aeon_sector_data_gen import generate_sector_tool_data, list_supported_tools
        for sector_id, tool_name in list_supported_tools():
            tool_data = generate_sector_tool_data(sector_id, tool_name)
            upsert_sector_data(workspace_id, sector_id, tool_name, tool_data)
            result[sector_id] = result.get(sector_id, 0) + 1
    else:
        data = _sector_data()
        for sector_id, tools in data.items():
            for tool_name, tool_data in tools.items():
                upsert_sector_data(workspace_id, sector_id, tool_name, tool_data)
            result[sector_id] = len(tools)

    for sector_id, count in result.items():
        logger.info("Seeded %s: %d tools (live=%s)", sector_id, count, live)

    total = sum(result.values())
    logger.info("Total: %d tools seeded across %d sectors", total, len(result))
    return result


def seed_sector(workspace_id: str, sector_id: str, *, live: bool = True) -> int:
    """Seed a single sector with data.

    By default, ``live=True`` generates time-varying data. Pass ``live=False``
    to use the original static demo data.

    Returns the number of tools seeded (0 if sector unknown).
    """
    from aeon_db import upsert_sector_data

    if live:
        from aeon_sector_data_gen import generate_sector_tool_data, list_supported_tools
        tools = [tool for sec, tool in list_supported_tools() if sec == sector_id]
        if not tools:
            logger.warning("Unknown sector: %s", sector_id)
            return 0
        for tool_name in tools:
            upsert_sector_data(workspace_id, sector_id, tool_name, generate_sector_tool_data(sector_id, tool_name))
    else:
        data = _sector_data()
        tools = data.get(sector_id)
        if not tools:
            logger.warning("Unknown sector: %s", sector_id)
            return 0
        for tool_name, tool_data in tools.items():
            upsert_sector_data(workspace_id, sector_id, tool_name, tool_data)

    seeded = len(tools)
    logger.info("Seeded %s: %d tools (live=%s)", sector_id, seeded, live)
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
