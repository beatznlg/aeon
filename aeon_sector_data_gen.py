"""
AEON OS — Live Sector Data Generator
=====================================
Generates realistic, time-varying data for every sector/tool pair.

The generator is deterministic-ish: it uses the current UTC hour as a seed
so dashboards appear to update over time, while repeated calls within the
same hour return stable values. Calling code can override the seed to force
fresh data on every refresh.

Usage:
    from aeon_sector_data_gen import generate_sector_tool_data, refresh_sector
    data = generate_sector_tool_data("cybersecurity", "threats")
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _seed_rng(seed: int | None = None) -> random.Random:
    if seed is None:
        # Change every minute to give dashboards a live feel, but stay stable
        # across rapid refreshes within the same minute.
        now = _now()
        seed = now.year * 100000000 + now.month * 1000000 + now.day * 10000 + now.hour * 100 + now.minute
    return random.Random(seed)  # nosec B311 - deterministic demo-data seed, not security-sensitive


def _iso_now(offset_days: int = 0) -> str:
    return datetime.now(timezone.utc).isoformat().replace("+", "Z")


# ═══════════════════════════════════════════════════════════════════════════════
#  Sector-specific generators
# ═══════════════════════════════════════════════════════════════════════════════

def _gen_cybersecurity_threats(rng: random.Random) -> list[dict[str, Any]]:
    indicators = [
        ("192.0.2.45", "IP"),
        ("malware.exe", "Hash"),
        ("phish.example.com", "Domain"),
        ("10.0.0.99", "IP"),
        ("suspicious.example.net", "Domain"),
        ("trojan.bin", "Hash"),
    ]
    statuses = ["blocked", "quarantined", "monitored", "investigating"]
    severities = ["low", "medium", "high", "critical"]
    base = rng.randint(0, 1000)
    return [
        {
            "id": f"TH-{base + i:03d}",
            "indicator": indicators[rng.randint(0, len(indicators) - 1)][0],
            "type": indicators[rng.randint(0, len(indicators) - 1)][1],
            "severity": rng.choice(severities),
            "status": rng.choice(statuses),
            "first_seen": _iso_now(),
            "last_seen": _iso_now(),
        }
        for i in range(rng.randint(3, 7))
    ]


def _gen_cybersecurity_vulnerabilities(rng: random.Random) -> list[dict[str, Any]]:
    severities = ["Low", "Medium", "High", "Critical"]
    libs = ["example-lib", "auth-service", "api-gateway", "logging-lib", "payment-gateway", "user-service"]
    return [
        {
            "cve": f"CVE-2024-{rng.randint(1000, 9999):04d}",
            "severity": sev,
            "cvss": round(rng.uniform(2.0, 9.9), 1),
            "affected": rng.choice(libs),
            "patch_available": rng.choice([True, False]),
            "discovered": _iso_now()[:10],
        }
        for sev in severities
    ]


def _gen_cybersecurity_compliance(rng: random.Random) -> dict[str, Any]:
    return {
        "framework": "NIST-CSF",
        "score": rng.randint(65, 98),
        "maturity": rng.choice(["Initial", "Developing", "Defined", "Managed", "Optimized"]),
        "gaps": rng.sample(["IAM review", "Log retention", "Incident response automation", "Patch management"], rng.randint(1, 3)),
        "last_assessment": _iso_now()[:10],
    }


def _gen_cybersecurity_ip_reputation(rng: random.Random) -> dict[str, Any]:
    return {
        "score": round(rng.uniform(0.0, 0.6), 2),
        "known_malicious": rng.random() > 0.7,
        "source_countries": rng.sample(["US", "DE", "JP", "RU", "CN", "BR"], rng.randint(2, 4)),
        "last_seen_days": rng.randint(0, 7),
    }


def _gen_cybersecurity_news(rng: random.Random) -> list[dict[str, Any]]:
    headlines = [
        "Critical OpenSSH vulnerability disclosed",
        "New ransomware group targets healthcare sector",
        "Zero-day exploit detected in popular VPN client",
        "Supply-chain attack targets popular npm package",
        "Nation-state APT activity surges in Q3",
    ]
    sources = ["CVE Database", "Threat Intel", "Security Advisory", "Reuters", "BleepingComputer"]
    return [
        {
            "title": h,
            "url": "#",
            "source": rng.choice(sources),
            "date": _iso_now()[:10],
        }
        for h in rng.sample(headlines, rng.randint(2, 4))
    ]


def _gen_health_diagnostics(rng: random.Random) -> list[dict[str, Any]]:
    symptoms = ["fever, cough, fatigue", "chest pain, shortness of breath", "headache, nausea", "abdominal pain", "dizziness"]
    return [
        {
            "analyzed_symptoms": s,
            "possible_conditions": [
                {
                    "name": rng.choice(["viral infection", "cardiac concern", "migraine", "gastroenteritis"]),
                    "probability": round(rng.uniform(0.55, 0.92), 2),
                    "severity": rng.choice(["low", "moderate", "high"]),
                    "action": rng.choice(["rest and monitor", "immediate evaluation", "hydration and rest"]),
                }
            ],
            "urgency": rng.choice(["low", "moderate", "high"]),
            "recommendation": rng.choice(["rest and monitor", "immediate evaluation", "hydration and rest"]),
        }
        for s in rng.sample(symptoms, rng.randint(2, 4))
    ]


def _gen_health_vitals(rng: random.Random) -> list[dict[str, Any]]:
    metrics = [
        ("heart_rate", 72, 110),
        ("blood_pressure_sys", 120, 160),
        ("oxygen_saturation", 90, 99),
        ("respiratory_rate", 12, 28),
    ]
    patients = ["P-1001", "P-1002", "P-1003", "P-1004"]
    data = []
    for patient in patients:
        for metric, base, high in metrics:
            current = rng.randint(base - 5, high + 5)
            trend = "stable" if abs(current - base) < 8 else ("rising" if current > base else "falling")
            data.append(
                {
                    "patient_id": patient,
                    "metric": metric,
                    "baseline": base,
                    "current": current,
                    "trend": trend,
                    "alert": abs(current - base) > 15,
                }
            )
    return data


def _gen_health_drug_interactions(rng: random.Random) -> list[dict[str, Any]]:
    sets = [
        (["aspirin", "warfarin"], "increased bleeding risk"),
        (["lisinopril", "potassium"], "hyperkalemia risk"),
        (["metformin", "losartan"], None),
        (["atorvastatin", "clarithromycin"], "myopathy risk"),
    ]
    return [
        {
            "medications": meds,
            "interactions_found": 1 if warning else 0,
            "interactions": [{"drugs": meds, "severity": "moderate", "warning": warning}] if warning else [],
        }
        for meds, warning in rng.sample(sets, rng.randint(2, 4))
    ]


def _gen_health_telehealth(rng: random.Random) -> list[dict[str, Any]]:
    cases = [
        ("chest pain", 65, "emergent", "call 911"),
        ("fever", 30, "non-urgent", "schedule virtual visit"),
        ("skin rash", 42, "routine", "upload photos for dermatology review"),
        ("cough", 55, "non-urgent", "schedule virtual visit"),
        ("ankle swelling", 70, "urgent", "see provider within 24h"),
    ]
    rng.shuffle(cases)
    return [
        {"symptoms": s, "age": a, "urgency": u, "recommendation": r}
        for s, a, u, r in cases[: rng.randint(2, 4)]
    ]


def _gen_finance_risk(rng: random.Random) -> dict[str, Any]:
    return {
        "asset": "S&P 500",
        "portfolio_value": rng.randint(400000, 600000),
        "var_95_1d": rng.randint(10000, 15000),
        "var_95_pct": round(rng.uniform(2.0, 3.0), 2),
        "sharpe_estimate": round(rng.uniform(1.0, 2.0), 2),
        "beta": round(rng.uniform(0.9, 1.1), 2),
        "risk_rating": rng.choice(["low", "medium", "high"]),
        "diversification_score": rng.randint(4, 9),
        "recommendation": "diversify fixed income",
    }


def _gen_finance_market(rng: random.Random) -> dict[str, Any]:
    return {
        "market": "NASDAQ",
        "predicted_direction": rng.choice(["bullish", "bearish", "neutral"]),
        "confidence": round(rng.uniform(0.55, 0.85), 2),
        "price_target_pct": round(rng.uniform(-3.0, 6.0), 2),
        "volatility_forecast": rng.choice(["low", "moderate", "high"]),
        "key_indicators": {
            "rsi": rng.randint(40, 75),
            "macd": rng.choice(["bullish_cross", "bearish_cross", "neutral"]),
            "moving_avg_50": rng.randint(17000, 19000),
            "moving_avg_200": rng.randint(15000, 17000),
        },
    }


def _gen_finance_fraud(rng: random.Random) -> list[dict[str, Any]]:
    return [
        {
            "transaction_id": f"TXN-{rng.randint(5000, 9999)}",
            "amount": rng.randint(20, 30000),
            "fraud_score": round(rng.uniform(0.0, 0.95), 2),
            "risk_level": rng.choice(["low", "medium", "high"]),
            "action": rng.choice(["approved", "blocked", "flagged"]),
            "timestamp": _iso_now(),
        }
        for _ in range(rng.randint(3, 6))
    ]


def _gen_finance_credit(rng: random.Random) -> list[dict[str, Any]]:
    ratings = [
        ("APP-200", 720, "Good", 0.92, 15000),
        ("APP-201", 580, "Poor", 0.18, 0),
        ("APP-202", 810, "Excellent", 0.99, 50000),
        ("APP-203", 650, "Fair", 0.55, 5000),
    ]
    return [
        {
            "applicant_id": app,
            "credit_score": score + rng.randint(-20, 20),
            "rating": rating,
            "approval_probability": round(max(0.0, min(1.0, prob + rng.uniform(-0.1, 0.1))), 2),
            "recommended_limit": limit,
        }
        for app, score, rating, prob, limit in ratings
    ]


def _gen_finance_payments(rng: random.Random) -> list[dict[str, Any]]:
    return [
        {
            "account_id": acc,
            "total_transactions": rng.randint(50, 350),
            "total_volume": rng.randint(20000, 150000),
            "anomaly_count": rng.randint(0, 5),
            "spending_trend": rng.choice(["stable", "increasing", "decreasing"]),
        }
        for acc in ["ACC-1234", "ACC-5678", "ACC-9012"]
    ]


def _gen_retail_forecast(rng: random.Random) -> list[dict[str, Any]]:
    skus = [
        ("SKU-001", 850, 1240, 390),
        ("SKU-042", 420, 680, 260),
        ("SKU-099", 2100, 1890, 0),
        ("SKU-107", 120, 340, 220),
        ("SKU-215", 560, 890, 330),
    ]
    return [
        {
            "sku": sku,
            "current_stock": max(0, stock + rng.randint(-100, 100)),
            "projected_demand": max(0, demand + rng.randint(-100, 100)),
            "recommended_order_qty": max(0, order + rng.randint(-50, 50)),
            "confidence": round(rng.uniform(0.70, 0.98), 2),
        }
        for sku, stock, demand, order in skus
    ]


def _gen_retail_inventory(rng: random.Random) -> dict[str, Any]:
    return {
        "alerts": [
            {"sku": "SKU-107", "status": "stockout_risk", "days_remaining": rng.randint(1, 5)}
        ],
        "reorder_recommendations": [
            {"sku": "SKU-107", "qty": rng.randint(180, 260), "supplier": "Alpha Corp", "est_delivery_days": rng.randint(2, 5)},
            {"sku": "SKU-042", "qty": rng.randint(220, 300), "supplier": "Gamma Wholesale", "est_delivery_days": rng.randint(3, 6)},
        ],
        "healthy": [
            {"sku": "SKU-001", "status": "healthy", "days_supply": rng.randint(15, 30)},
            {"sku": "SKU-099", "status": "overstock", "days_supply": rng.randint(60, 90), "suggestion": "run promotion"},
            {"sku": "SKU-215", "status": "healthy", "days_supply": rng.randint(12, 22)},
        ],
        "summary": {
            "total_skus": 5,
            "stockout_risks": rng.randint(0, 2),
            "overstocks": rng.randint(0, 2),
            "healthy": rng.randint(2, 5),
        },
    }


def _gen_retail_suppliers(rng: random.Random) -> list[dict[str, Any]]:
    suppliers = [
        ("Alpha Corp", 15, "Low Risk", 96),
        ("Beta Logistics", 42, "Medium Risk", 82),
        ("Gamma Wholesale", 8, "Low Risk", 99),
        ("Delta Distributors", 71, "High Risk", 61),
    ]
    return [
        {
            "supplier": name,
            "risk_score": max(0, min(100, score + rng.randint(-10, 10))),
            "classification": cls,
            "on_time_delivery_pct": max(0, min(100, pct + rng.randint(-5, 5))),
            "contract_end": f"2027-{rng.randint(1, 12):02d}-01",
        }
        for name, score, cls, pct in suppliers
    ]


def _gen_retail_pricing(rng: random.Random) -> dict[str, Any]:
    return {
        "sku": "SKU-001",
        "price_change_pct": round(rng.uniform(-5, 15), 2),
        "elasticity": round(rng.uniform(-0.8, -0.1), 2),
        "projected_demand_change_pct": round(rng.uniform(-10, 5), 2),
        "optimal_price": round(rng.uniform(30, 35), 2),
        "current_price": 29.99,
    }


def _gen_transport_traffic(rng: random.Random) -> list[dict[str, Any]]:
    zones = ["downtown", "midtown", "airport_corridor", "suburb_east", "harbor_district"]
    return [
        {
            "zone": zone,
            "current_congestion": round(rng.uniform(2.0, 10.0), 1),
            "predicted_improvement": rng.choice(["divert to ring road", "monitor", "activate bus lane", "normal flow", "adjust signal timing"]),
            "incident_nearby": rng.random() > 0.6,
        }
        for zone in zones
    ]


def _gen_transport_fleet(rng: random.Random) -> list[dict[str, Any]]:
    depots = ["North Hub", "South Hub", "Central Hub", "East Hub"]
    return [
        {
            "depot": depot,
            "vehicles_available": rng.randint(5, 20),
            "shifts": rng.randint(1, 4),
            "utilization_pct": rng.randint(60, 95),
            "recommendation": rng.choice(["reduce 1 vehicle", "reduce 2 vehicles", "optimal", "add 1 vehicle"]),
        }
        for depot in depots
    ]


def _gen_transport_routes(rng: random.Random) -> list[dict[str, Any]]:
    return [
        {
            "stops": ["A", "B", "C", "D", "E"],
            "estimated_distance_km": round(rng.uniform(20, 60), 1),
            "estimated_time_min": rng.randint(30, 80),
            "fuel_cost_est": round(rng.uniform(10, 30), 2),
            "optimized": rng.random() > 0.3,
        }
        for _ in range(rng.randint(3, 5))
    ]


def _gen_manufacturing_maintenance(rng: random.Random) -> list[dict[str, Any]]:
    machines = ["CNC-01", "CNC-02", "CNC-03", "CNC-04", "CNC-05"]
    return [
        {
            "machine_id": m,
            "status": rng.choice(["good", "warning", "critical"]),
            "temp_c": rng.randint(35, 85),
            "vibration_hz": round(rng.uniform(8, 35), 1),
            "failure_risk_pct": rng.randint(5, 95),
            "days_to_failure": rng.randint(1, 90),
            "last_service": f"2026-{rng.randint(1, 7):02d}-{rng.randint(1, 28):02d}",
        }
        for m in machines
    ]


def _gen_manufacturing_quality(rng: random.Random) -> list[dict[str, Any]]:
    batches = ["B-998", "B-999", "B-1000", "B-1001"]
    return [
        {
            "batch_id": b,
            "items_scanned": rng.randint(450, 550),
            "defects_found": rng.randint(0, 40),
            "defect_rate": round(rng.uniform(0.001, 0.08), 3),
            "status": rng.choice(["pass", "fail", "warn"]),
            "root_cause": rng.choice(["calibration drift", "raw material variance", None, None]),
        }
        for b in batches
    ]


def _gen_manufacturing_logistics(rng: random.Random) -> list[dict[str, Any]]:
    routes = ["R-10", "R-11", "R-12", "R-13", "R-14"]
    return [
        {
            "route_id": r,
            "status": rng.choice(["on_time", "delayed"]),
            "eta_days": rng.randint(1, 6),
            "reroute_cost_usd": rng.choice([0, rng.randint(500, 3000)]),
            "delay_reason": rng.choice(["weather", "port congestion", None, None]),
        }
        for r in routes
    ]


def _gen_tourism_bookings(rng: random.Random) -> list[dict[str, Any]]:
    properties = ["Hotel-Central", "Hotel-West", "Hotel-Airport"]
    return [
        {
            "property": p,
            "occupancy_pct": rng.randint(55, 95),
            "predictive_no_shows": rng.randint(5, 25),
            "net_expected_occupancy": rng.randint(50, 90),
            "revenue_ytd": rng.randint(800000, 2500000),
        }
        for p in properties
    ]


def _gen_tourism_pricing(rng: random.Random) -> list[dict[str, Any]]:
    rooms = ["King Suite", "Double Queen", "Standard", "Penthouse"]
    return [
        {
            "room": room,
            "base_price": base,
            "recommended_price": base + rng.randint(-20, 60),
            "reason": rng.choice(["High demand", "Medium demand", "Low demand, hold", "Premium event weekend"]),
            "demand_level": rng.choice(["low", "medium", "high"]),
        }
        for room, base in zip(rooms, [299, 259, 169, 599], strict=False)
    ]


def _gen_tourism_concierge(rng: random.Random) -> list[dict[str, Any]]:
    return [
        {
            "guest_id": f"G-{rng.randint(400, 500)}",
            "sentiment": rng.choice(["positive", "neutral", "negative"]),
            "intent": rng.choice(["dining reservation", "housekeeping request", "transport to airport", "spa booking"]),
            "automated_response": "Confirmed",
            "upsell": rng.choice(["Wine pairing package", "Couples massage package", None, None]),
        }
        for _ in range(rng.randint(3, 5))
    ]


def _gen_tourism_visitors(rng: random.Random) -> list[dict[str, Any]]:
    venues = ["National Museum", "Modern Art Gallery", "History Center"]
    return [
        {
            "venue": v,
            "daily_visitors": rng.randint(200, 1500),
            "engagement_score": rng.randint(75, 98),
            "recommended_strategies": rng.sample(["extend hours weekends", "new family tour", "new exhibition promo", "school program expansion"], rng.randint(1, 2)),
        }
        for v in venues
    ]


def _gen_utilities_resources(rng: random.Random) -> list[dict[str, Any]]:
    resources = ["water", "electricity", "natural_gas", "renewable_energy"]
    return [
        {
            "resource": r,
            "demand": rng.randint(100, 1200),
            "supply": rng.randint(100, 1200),
            "deficit": rng.randint(-50, 200),
            "status": rng.choice(["good", "warning", "critical"]),
            "optimization_suggestion": rng.choice(["implement tiered pricing", "demand response program", "increase storage capacity", None]),
        }
        for r in resources
    ]


def _gen_utilities_services(rng: random.Random) -> list[dict[str, Any]]:
    services = ["waste_collection", "street_lighting", "public_transport", "water_supply"]
    return [
        {
            "service": s,
            "kpi_score": round(rng.uniform(0.7, 0.99), 2),
            "status": rng.choice(["excellent", "good", "satisfactory", "needs improvement"]),
            "citizen_satisfaction": round(rng.uniform(0.6, 0.95), 2),
            "trend": rng.choice(["improving", "stable", "declining"]),
        }
        for s in services
    ]


def _gen_utilities_waste(rng: random.Random) -> list[dict[str, Any]]:
    districts = ["Zone A", "Zone B", "Zone C"]
    return [
        {
            "district": d,
            "total_waste_tons": rng.randint(700, 1800),
            "recycled_pct": rng.randint(15, 50),
            "landfill_pct": rng.randint(40, 80),
            "collection_efficiency": round(rng.uniform(0.7, 0.99), 2),
        }
        for d in districts
    ]


def _gen_utilities_grid(rng: random.Random) -> list[dict[str, Any]]:
    regions = ["North Grid", "South Grid", "East Grid", "West Grid"]
    return [
        {
            "region": r,
            "current_load_mw": rng.randint(150, 350),
            "capacity_mw": rng.randint(250, 400),
            "utilization_pct": round(rng.uniform(60, 105), 1),
            "renewable_share_pct": rng.randint(15, 60),
            "status": rng.choice(["stable", "critical"]),
            "action": "activate backup generators" if rng.random() > 0.7 else None,
        }
        for r in regions
    ]


def _gen_heritage_visitors(rng: random.Random) -> list[dict[str, Any]]:
    return _gen_tourism_visitors(rng)


def _gen_heritage_sites(rng: random.Random) -> list[dict[str, Any]]:
    sites = [
        ("Colosseum", "Ancient Rome", "Iconic amphitheatre"),
        ("Machu Picchu", "Inca Empire", "Citadel in the Andes"),
        ("Angkor Wat", "Khmer Empire", "Largest religious monument"),
    ]
    return [
        {
            "site": s[0],
            "era": s[1],
            "significance": s[2],
            "annual_visitors": rng.randint(1000000, 8000000),
            "conservation_status": rng.choice(["good", "fair", "requires attention"]),
        }
        for s in sites
    ]


def _gen_heritage_exhibitions(rng: random.Random) -> list[dict[str, Any]]:
    themes = [
        ("Modern Art", 25),
        ("Ancient Egypt", 22),
        ("Space Exploration", 28),
    ]
    return [
        {
            "theme": t[0],
            "recommended_duration_days": rng.randint(30, 120),
            "estimated_visitors": rng.randint(30000, 100000),
            "ticket_price": price,
            "projected_revenue": price * rng.randint(30000, 100000),
        }
        for t, price in zip(themes, [25, 22, 28], strict=False)
    ]


def _gen_heritage_tours(rng: random.Random) -> list[dict[str, Any]]:
    tours = [
        ("Louvre Museum", "art"),
        ("British Museum", "history"),
        ("Uffizi Gallery", "architecture"),
        ("Vatican Museums", "religion"),
    ]
    return [
        {
            "site": site,
            "interest": interest,
            "narration": f"Guided {interest} tour of {site}",
            "audio_duration_seconds": rng.randint(1200, 2700),
        }
        for site, interest in tours
    ]


def _gen_sme_workflows(rng: random.Random) -> list[dict[str, Any]]:
    processes = [
        ("invoice_approval", 5, 120, 24000, 0.85),
        ("employee_onboarding", 3, 80, 16000, 0.72),
        ("report_generation", 2, 60, 12000, 0.94),
        ("expense_reporting", 4, 95, 19000, 0.78),
    ]
    return [
        {
            "process": p[0],
            "employees_involved": p[1],
            "hours_saved_per_month": p[2],
            "cost_savings_annual": p[3],
            "automation_rate": p[4],
        }
        for p in processes
    ]


def _gen_sme_documents(rng: random.Random) -> list[dict[str, Any]]:
    docs = [
        ("invoice", 0.97, 142, ["vendor", "amount", "due_date"]),
        ("contract", 0.94, 38, ["parties", "term", "liability"]),
        ("receipt", 0.96, 210, ["merchant", "total", "date"]),
        ("purchase_order", 0.91, 55, ["items", "total", "delivery_date"]),
    ]
    return [
        {
            "document_type": dtype,
            "confidence": round(conf + rng.uniform(-0.03, 0.03), 2),
            "pages_processed": pages,
            "fields_extracted": fields,
            "status": rng.choice(["completed", "pending"]),
        }
        for dtype, conf, pages, fields in docs
    ]


def _gen_sme_support(rng: random.Random) -> list[dict[str, Any]]:
    queries = [
        ("Where is my order?", "order_status", "frustrated", "Tracking link sent", False),
        ("I want a refund", "refund", "angry", "Refund initiated", True),
        ("My account is locked", "account_access", "neutral", "Unlocked with MFA reset", False),
        ("How do I change my plan?", "plan_change", "neutral", "Plan upgrade options sent", False),
    ]
    return [
        {
            "query": q[0],
            "detected_intent": q[1],
            "sentiment": q[2],
            "response": q[3],
            "escalated": q[4],
        }
        for q in queries
    ]


def _gen_sme_supply_chain(rng: random.Random) -> list[dict[str, Any]]:
    chains = ["SC-001", "SC-002", "SC-003", "SC-004"]
    return [
        {
            "chain_id": c,
            "health_score": rng.randint(40, 95),
            "lead_time_days": rng.randint(3, 25),
            "risk_level": rng.choice(["low", "medium", "high"]),
            "bottlenecks": rng.choice([[], ["distributor delay"], ["raw material shortage", "transport strike"], []]),
        }
        for c in chains
    ]


# ═══════════════════════════════════════════════════════════════════════════════
#  Telecom Generators
# ══════════════════════════════════════════════════════════════════════════════

def _gen_telecom_network(rng: random.Random) -> list[dict[str, Any]]:
    elements = [
        ("core_router_01", "core", 99.2, "US-East"),
        ("core_router_02", "core", 98.9, "US-West"),
        ("edge_switch_14", "edge", 97.5, "US-East"),
        ("edge_switch_22", "edge", 96.8, "EU-Central"),
        ("radio_tower_07", "radio", 95.4, "US-West"),
        ("fiber_ring_03", "transport", 99.6, "EU-Central"),
        ("backhaul_05", "transport", 94.7, "APAC"),
        ("small_cell_31", "radio", 93.2, "APAC"),
    ]
    return [
        {
            "id": f"tel-{idx + 1}",
            "element": element,
            "type": etype,
            "health_score": round(health + rng.uniform(-1.5, 1.5), 1),
            "uptime_pct": round(health + rng.uniform(-0.4, 0.2), 2),
            "sla_status": rng.choice(["met", "met", "met", "at_risk", "breached"]),
            "region": region,
        }
        for idx, (element, etype, health, region) in enumerate(elements)
    ]


def _gen_telecom_capacity(rng: random.Random) -> list[dict[str, Any]]:
    nodes = ["backbone_01", "backbone_02", "metro_agg_11", "metro_agg_12", "edge_pop_03", "edge_pop_09"]
    return [
        {
            "id": f"cap-{idx + 1}",
            "node": node,
            "current_utilization_pct": rng.randint(35, 95),
            "forecast_utilization_pct": rng.randint(45, 105),
            "recommended_action": rng.choice(
                ["no_action", "monitor", "add_capacity", "rebalance_traffic"]
            ),
        }
        for idx, node in enumerate(nodes)
    ]


def _gen_telecom_faults(rng: random.Random) -> list[dict[str, Any]]:
    elements = ["core_router_01", "edge_switch_14", "radio_tower_07", "backhaul_05", "small_cell_31"]
    severities = ["low", "medium", "high", "critical"]
    statuses = ["open", "triage", "fixing", "resolved"]
    return [
        {
            "id": f"fault-{idx + 1}",
            "element": elements[idx % len(elements)],
            "severity": severities[idx % len(severities)],
            "status": statuses[idx % len(statuses)],
            "opened_at": _iso_now(-idx),
            "summary": rng.choice(
                [
                    "Packet loss above 2% threshold",
                    "Latency spike on customer links",
                    "Power supply redundancy degraded",
                    "Optical signal attenuation on fiber",
                    "Handover failures on small cell",
                ]
            ),
        }
        for idx in range(rng.randint(3, 5))
    ]


# ═══════════════════════════════════════════════════════════════════════════════
#  Agriculture Generators
# ══════════════════════════════════════════════════════════════════════════════

def _gen_agriculture_yield(rng: random.Random) -> list[dict[str, Any]]:
    fields = [
        ("field_alpha", "wheat"),
        ("field_beta", "corn"),
        ("field_gamma", "soybean"),
        ("field_delta", "barley"),
        ("field_epsilon", "corn"),
    ]
    return [
        {
            "id": f"yld-{idx + 1}",
            "field": field,
            "crop": crop,
            "forecast_tons": round(rng.uniform(180, 420), 1),
            "previous_tons": round(rng.uniform(150, 380), 1),
            "confidence": round(rng.uniform(0.72, 0.96), 2),
        }
        for idx, (field, crop) in enumerate(fields)
    ]


def _gen_agriculture_irrigation(rng: random.Random) -> list[dict[str, Any]]:
    zones = [
        ("zone_north", "wheat"),
        ("zone_south", "corn"),
        ("zone_east", "soybean"),
        ("zone_west", "barley"),
    ]
    return [
        {
            "id": f"irr-{idx + 1}",
            "zone": zone,
            "crop": crop,
            "schedule": rng.choice(["daily", "every_2_days", "weekly", "sensor_triggered"]),
            "water_needed_mm": rng.randint(15, 60),
            "status": rng.choice(["optimal", "optimal", "low", "over_irrigated"]),
        }
        for idx, (zone, crop) in enumerate(zones)
    ]


def _gen_agriculture_pests(rng: random.Random) -> list[dict[str, Any]]:
    pests = [
        ("field_alpha", "wheat", "aphid"),
        ("field_beta", "corn", "corn_borer"),
        ("field_gamma", "soybean", "armyworm"),
        ("field_delta", "barley", "rust_fungus"),
    ]
    return [
        {
            "id": f"pst-{idx + 1}",
            "field": field,
            "crop": crop,
            "pest": pest,
            "risk_level": rng.choice(["low", "low", "moderate", "high"]),
            "treatment": rng.choice(
                ["none_required", "biological_control", "targeted_spray", "quarantine_zone"]
            ),
        }
        for idx, (field, crop, pest) in enumerate(pests)
    ]


# ═══════════════════════════════════════════════════════════════════════════════
#  Education Generators
# ══════════════════════════════════════════════════════════════════════════════

def _gen_education_students(rng: random.Random) -> list[dict[str, Any]]:
    names = [
        "Ava Thompson",
        "Liam Rodriguez",
        "Maya Patel",
        "Noah Kim",
        "Zoe Nguyen",
        "Ethan Brooks",
    ]
    return [
        {
            "id": f"stu-{idx + 1}",
            "student_id": f"S-2026-{1000 + idx}",
            "name": names[idx % len(names)],
            "gpa": round(rng.uniform(1.4, 4.0), 2),
            "attendance_pct": rng.randint(58, 100),
            "risk_score": round(rng.uniform(0.05, 0.95), 2),
            "risk_level": rng.choice(["low", "low", "watch", "high"]),
        }
        for idx in range(rng.randint(4, 6))
    ]


def _gen_education_plans(rng: random.Random) -> list[dict[str, Any]]:
    actions = ["tutoring", "counseling", "mentorship", "parent_meeting", "study_group"]
    return [
        {
            "id": f"plan-{idx + 1}",
            "student_id": f"S-2026-{1000 + idx}",
            "plan": rng.choice(["Academic Support", "Attendance Recovery", "Social-Emotional Support"]),
            "actions": rng.sample(actions, k=rng.randint(2, 3)),
            "status": rng.choice(["draft", "active", "active", "completed"]),
            "owner": rng.choice(["Advisor Ward", "Counselor Reed", "Dean Patel"]),
        }
        for idx in range(rng.randint(3, 5))
    ]


def _gen_education_outcomes(rng: random.Random) -> list[dict[str, Any]]:
    programs = [
        "STEM Accelerator",
        "Literacy Boost",
        "Math Recovery",
        "College Readiness",
        "Career Pathways",
    ]
    return [
        {
            "id": f"out-{idx + 1}",
            "program": program,
            "completion_rate": round(rng.uniform(0.6, 0.97), 2),
            "avg_score": round(rng.uniform(62, 94), 1),
            "trend": rng.choice(["improving", "stable", "declining"]),
        }
        for idx, program in enumerate(programs)
    ]


# ═══════════════════════════════════════════════════════════════════════════════
#  Public Safety Generators
# ══════════════════════════════════════════════════════════════════════════════

def _gen_public_safety_incidents(rng: random.Random) -> list[dict[str, Any]]:
    types = ["theft", "traffic_accident", "disturbance", "medical_emergency", "fire_report", "suspicious_activity"]
    priorities = ["low", "medium", "high", "critical"]
    statuses = ["dispatched", "on_scene", "resolving", "closed"]
    locations = ["Downtown", "Riverside", "Northgate", "Southside", "Airport District"]
    return [
        {
            "id": f"inc-{idx + 1}",
            "incident_id": f"INC-{2026000 + idx}",
            "type": types[idx % len(types)],
            "priority": priorities[idx % len(priorities)],
            "status": statuses[idx % len(statuses)],
            "location": locations[idx % len(locations)],
            "reported_at": _iso_now(-idx),
        }
        for idx in range(rng.randint(4, 6))
    ]


def _gen_public_safety_dispatch(rng: random.Random) -> list[dict[str, Any]]:
    units = [
        ("unit_101", "patrol_car"),
        ("unit_102", "patrol_car"),
        ("unit_207", "ambulance"),
        ("unit_309", "fire_engine"),
        ("unit_114", "motorcycle_unit"),
    ]
    return [
        {
            "id": f"disp-{idx + 1}",
            "unit_id": unit_id,
            "unit_type": unit_type,
            "status": rng.choice(["available", "en_route", "on_scene", "returning"]),
            "current_incident": rng.choice(["none", "INC-2026001", "INC-2026002", "INC-2026005"]),
            "eta_minutes": rng.randint(2, 25),
        }
        for idx, (unit_id, unit_type) in enumerate(units)
    ]


def _gen_public_safety_briefs(rng: random.Random) -> list[dict[str, Any]]:
    briefs = [
        ("Overnight Shift Summary", "Property crimes down 8%; one critical response in Riverside"),
        ("Weekend Operations Review", "Traffic incidents up 12% near airport; added patrol coverage"),
        ("Special Event Plan", "Concert attendance 40k — staged resource plan active"),
    ]
    return [
        {
            "id": f"brf-{idx + 1}",
            "title": title,
            "period": rng.choice(["24h", "72h", "weekly"]),
            "highlights": highlights,
            "recommendations": rng.choice(
                [
                    ["Extend night patrol coverage", "Deploy traffic units pre-rush"],
                    ["Pre-position medics at venues", "Monitor hot spots"],
                    ["Review camera coverage gaps", "Add drone support"]
                ]
            ),
        }
        for idx, (title, highlights) in enumerate(briefs)
    ]


# ═══════════════════════════════════════════════════════════════════════════════
#  Real Estate Generators
# ══════════════════════════════════════════════════════════════════════════════

def _gen_real_estate_valuations(rng: random.Random) -> list[dict[str, Any]]:
    properties = [
        ("24 Maple Avenue", "single_family"),
        ("88 Harbor Drive", "condo"),
        ("1500 Oak Street", "multi_family"),
        ("7 Birch Lane", "townhouse"),
        ("330 Commerce Blvd", "commercial"),
    ]
    return [
        {
            "id": f"val-{idx + 1}",
            "property": prop,
            "type": ptype,
            "valuation": rng.randint(285_000, 1_450_000),
            "estimate_low": rng.randint(260_000, 1_300_000),
            "estimate_high": rng.randint(310_000, 1_600_000),
            "confidence": round(rng.uniform(0.82, 0.97), 2),
            "location": rng.choice(["Midtown", "Westside", "East Village", "Lake District"]),
        }
        for idx, (prop, ptype) in enumerate(properties)
    ]


def _gen_real_estate_market(rng: random.Random) -> list[dict[str, Any]]:
    regions = ["Midtown", "Westside", "East Village", "Lake District", "Airport Corridor"]
    return [
        {
            "id": f"mkt-{idx + 1}",
            "region": region,
            "median_price": rng.randint(320_000, 980_000),
            "price_change_pct": round(rng.uniform(-4.5, 8.5), 1),
            "inventory": rng.randint(24, 210),
            "days_on_market": rng.randint(9, 65),
        }
        for idx, region in enumerate(regions)
    ]


def _gen_real_estate_comparables(rng: random.Random) -> list[dict[str, Any]]:
    properties = ["24 Maple Avenue", "88 Harbor Drive", "1500 Oak Street"]
    addresses = ["26 Maple Avenue", "30 Maple Avenue", "19 Maple Avenue", "90 Harbor Drive", "1496 Oak Street"]
    return [
        {
            "id": f"cmp-{idx + 1}",
            "property": properties[idx % len(properties)],
            "comparable_address": addresses[idx % len(addresses)],
            "price": rng.randint(275_000, 1_500_000),
            "sqft": rng.randint(1_200, 4_800),
            "delta_pct": round(rng.uniform(-8, 9), 1),
        }
        for idx in range(rng.randint(4, 6))
    ]


# ═══════════════════════════════════════════════════════════════════════════════
#  Professional Services Generators
# ══════════════════════════════════════════════════════════════════════════════

def _gen_professional_legal(rng: random.Random) -> list[dict[str, Any]]:
    docs = [
        ("Service Agreement", "contract"),
        ("NDA", "non-disclosure"),
        ("Employment Contract", "employment"),
        ("Lease Agreement", "lease"),
        ("Partnership Agreement", "partnership"),
    ]
    obligations = ["Confidentiality", "Non-compete", "IP Assignment", "Indemnification", "Termination Notice"]
    return [
        {
            "doc": doc,
            "type": dtype,
            "risk_score": rng.choice(["low", "low", "medium", "high"]),
            "obligations": rng.sample(obligations, k=rng.randint(1, 3)),
        }
        for doc, dtype in docs
    ]


def _gen_professional_accounting(rng: random.Random) -> list[dict[str, Any]]:
    vendors = ["Acme Corp", "TechSupply Inc", "DataServices LLC", "CloudHost Ltd", "ConsultPro Group"]
    return [
        {
            "invoice_id": f"INV-{idx + 1000:04d}",
            "vendor": vendor,
            "amount": rng.randint(1500, 7500),
            "anomalies_detected": rng.random() > 0.8,
            "auto_approved": rng.random() > 0.3,
        }
        for idx, vendor in enumerate(vendors)
    ]


def _gen_professional_data_mgmt(rng: random.Random) -> list[dict[str, Any]]:
    datasets = [
        "Customer DB",
        "Employee Records",
        "Transaction Logs",
        "Marketing Data",
        "Analytics Cache",
        "Support Tickets",
    ]
    return [
        {
            "dataset": dataset,
            "pii_records_found": rng.randint(500, 2600),
            "compliance": rng.choice(
                ["GDPR-ready", "HIPAA-compliant", "PCI-DSS-ready", "needs_review", "compliant"]
            ),
        }
        for dataset in datasets
    ]


# ═══════════════════════════════════════════════════════════════════════════════
#  Registry
# ══════════════════════════════════════════════════════════════════════════════

_GENERATORS: dict[tuple[str, str], Any] = {
    ("cybersecurity", "threats"): _gen_cybersecurity_threats,
    ("cybersecurity", "vulnerabilities"): _gen_cybersecurity_vulnerabilities,
    ("cybersecurity", "compliance"): _gen_cybersecurity_compliance,
    ("cybersecurity", "ip-reputation"): _gen_cybersecurity_ip_reputation,
    ("cybersecurity", "news"): _gen_cybersecurity_news,
    ("health", "diagnostics"): _gen_health_diagnostics,
    ("health", "vitals"): _gen_health_vitals,
    ("health", "drug-interactions"): _gen_health_drug_interactions,
    ("health", "telehealth"): _gen_health_telehealth,
    ("finance", "risk"): _gen_finance_risk,
    ("finance", "market"): _gen_finance_market,
    ("finance", "fraud"): _gen_finance_fraud,
    ("finance", "credit"): _gen_finance_credit,
    ("finance", "payments"): _gen_finance_payments,
    ("retail", "forecast"): _gen_retail_forecast,
    ("retail", "inventory"): _gen_retail_inventory,
    ("retail", "suppliers"): _gen_retail_suppliers,
    ("retail", "pricing"): _gen_retail_pricing,
    ("transport", "traffic"): _gen_transport_traffic,
    ("transport", "fleet"): _gen_transport_fleet,
    ("transport", "routes"): _gen_transport_routes,
    ("manufacturing", "maintenance"): _gen_manufacturing_maintenance,
    ("manufacturing", "quality"): _gen_manufacturing_quality,
    ("manufacturing", "logistics"): _gen_manufacturing_logistics,
    ("tourism", "bookings"): _gen_tourism_bookings,
    ("tourism", "pricing"): _gen_tourism_pricing,
    ("tourism", "concierge"): _gen_tourism_concierge,
    ("tourism", "visitors"): _gen_tourism_visitors,
    ("utilities", "resources"): _gen_utilities_resources,
    ("utilities", "services"): _gen_utilities_services,
    ("utilities", "waste"): _gen_utilities_waste,
    ("utilities", "grid"): _gen_utilities_grid,
    ("heritage", "visitors"): _gen_heritage_visitors,
    ("heritage", "sites"): _gen_heritage_sites,
    ("heritage", "exhibitions"): _gen_heritage_exhibitions,
    ("heritage", "tours"): _gen_heritage_tours,
    ("sme", "workflows"): _gen_sme_workflows,
    ("sme", "documents"): _gen_sme_documents,
    ("sme", "support"): _gen_sme_support,
    ("sme", "supply-chain"): _gen_sme_supply_chain,
    ("telecom", "network"): _gen_telecom_network,
    ("telecom", "capacity"): _gen_telecom_capacity,
    ("telecom", "faults"): _gen_telecom_faults,
    ("agriculture", "yield"): _gen_agriculture_yield,
    ("agriculture", "irrigation"): _gen_agriculture_irrigation,
    ("agriculture", "pests"): _gen_agriculture_pests,
    ("education", "at-risk"): _gen_education_students,
    ("education", "interventions"): _gen_education_plans,
    ("education", "outcomes"): _gen_education_outcomes,
    ("public_safety", "incidents"): _gen_public_safety_incidents,
    ("public_safety", "dispatch"): _gen_public_safety_dispatch,
    ("public_safety", "briefs"): _gen_public_safety_briefs,
    ("real_estate", "valuations"): _gen_real_estate_valuations,
    ("real_estate", "market"): _gen_real_estate_market,
    ("real_estate", "comparables"): _gen_real_estate_comparables,
    ("professional", "legal"): _gen_professional_legal,
    ("professional", "accounting"): _gen_professional_accounting,
    ("professional", "data-management"): _gen_professional_data_mgmt,
}


def generate_sector_tool_data(sector: str, tool: str, seed: int | None = None) -> dict | list:
    """Generate live data for a single sector/tool.

    Args:
        sector: The sector id, e.g. ``cybersecurity``.
        tool: The tool id, e.g. ``threats``.
        seed: Optional RNG seed. Pass ``None`` for time-based minute seeding,
            or pass a fixed value for deterministic output.

    Returns:
        JSON-serializable data matching the shape expected by the dashboards.
    """
    rng = _seed_rng(seed)
    generator = _GENERATORS.get((sector, tool))
    if generator is None:
        raise ValueError(f"No generator defined for {sector}/{tool}")
    return generator(rng)


def list_supported_tools() -> list[tuple[str, str]]:
    """Return all (sector, tool) pairs supported by the generator."""
    return list(_GENERATORS.keys())


def refresh_sector(sector: str, seed: int | None = None) -> dict[str, dict | list]:
    """Generate fresh live data for every tool in a sector."""
    return {
        tool: generate_sector_tool_data(sector, tool, seed=seed)
        for sec, tool in _GENERATORS
        if sec == sector
    }


def refresh_all(seed: int | None = None) -> dict[str, dict[str, dict | list]]:
    """Generate fresh live data for every sector/tool pair."""
    result: dict[str, dict[str, dict | list]] = {}
    for sector, tool in _GENERATORS:
        result.setdefault(sector, {})[tool] = generate_sector_tool_data(sector, tool, seed=seed)
    return result
