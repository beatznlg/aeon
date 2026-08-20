/**
 * Sector Data Generator
 * ======================
 * Generates time-varying mock data for all 16 sectors and their registered tools.
 * Data changes slightly on each call (poll) so dashboards appear live.
 *
 * Each generator function accepts a `seed` (derived from the sector/tool name)
 * and uses `Date.now()` to add time-based variation to values.
 */

// ════════════════════════════════════════════════════════════════
// Helpers
// ════════════════════════════════════════════════════════════════

/** Deterministic pseudo-random from a string seed + optional offset */
function pseudoRandom(seed: string, offset = 0): number {
  let hash = 0;
  const s = seed + offset;
  for (let i = 0; i < s.length; i++) {
    const char = s.charCodeAt(i);
    hash = (hash << 5) - hash + char;
    hash = hash & hash; // Convert to 32-bit int
  }
  return Math.abs(hash % 10000) / 10000;
}

/** Time-based variation that oscillates smoothly */
function timeWave(periodMs = 30000): number {
  return Math.sin(((Date.now() % periodMs) / periodMs) * Math.PI * 2);
}

/** Generate a value that oscillates around a base with some drift */
function oscillate(base: number, range: number, seed: string, toolKey: string): number {
  const t = Date.now() / 1000;
  const variation = Math.sin(t * 0.05 + pseudoRandom(seed + toolKey) * 10) * range;
  return Math.round((base + variation) * 100) / 100;
}

/** Pick a random item from array using seed */
function pickRandom<T>(arr: T[], seed: string, offset = 0): T {
  return arr[Math.floor(pseudoRandom(seed, offset) * arr.length)];
}

/** Generate a short ID */
function shortId(seed: string, i: number): string {
  const chars = "abcdef0123456789";
  let id = "";
  const s = seed + i;
  for (let j = 0; j < 8; j++) {
    id += chars[Math.floor(pseudoRandom(s, j) * chars.length)];
  }
  return id;
}

// ════════════════════════════════════════════════════════════════
// Cybersecurity Generators
// ════════════════════════════════════════════════════════════════

function genThreats(seed: string) {
  const types = [
    "malware",
    "phishing",
    "ddos",
    "ransomware",
    "insider_threat",
    "botnet",
    "social_engineering",
  ];
  const severities = ["low", "medium", "high", "critical"];
  const statuses = ["detected", "analyzing", "blocked", "quarantined", "resolved"];
  const count = 3 + Math.floor(pseudoRandom(seed, (Date.now() % 60000) / 10000) * 5);
  return Array.from({ length: count }, (_, i) => ({
    id: shortId("threat", i),
    indicator: `${pickRandom(["evilcorp", "darknet", "phishlab", "maldomain", "badhost"], seed, i)}.${pickRandom(["com", "net", "org", "xyz"], seed, i + 7)}`,
    type: pickRandom(types, seed, i + 3),
    severity: pickRandom(severities, seed, i + 5),
    status: pickRandom(statuses, seed, i + 2),
    timestamp: new Date(Date.now() - i * 180000).toISOString(),
  }));
}

function genVulnerabilities(seed: string) {
  const products = [
    "Apache HTTPD",
    "nginx",
    "OpenSSL",
    "Kubernetes",
    "Docker",
    "PostgreSQL",
    "Linux Kernel",
    "Node.js",
    "Python",
    "Redis",
  ];
  const severities = ["Low", "Medium", "High", "Critical"];
  const count = 4 + Math.floor(pseudoRandom(seed, (Date.now() % 45000) / 10000) * 6);
  return Array.from({ length: count }, (_, i) => ({
    cve: `CVE-2025-${1000 + Math.floor(pseudoRandom(seed, i) * 8000)}`,
    severity: pickRandom(severities, seed, i + 4),
    cvss: parseFloat((oscillate(6.5, 3, seed, "cvss") + pseudoRandom(seed, i) * 2).toFixed(1)),
    affected: pickRandom(products, seed, i + 2),
    patch_available: pseudoRandom(seed, i + 8) > 0.4,
  }));
}

function genCompliance(seed: string) {
  const frameworks = ["SOC 2", "ISO 27001", "HIPAA", "GDPR", "PCI DSS", "FedRAMP"];
  const maturityLevels = ["initial", "defined", "managed", "optimized"];
  const base = oscillate(72, 15, seed, "compliance");
  return {
    framework: pickRandom(frameworks, seed, 99),
    score: Math.max(30, Math.min(100, Math.round(base))),
    maturity: maturityLevels[Math.floor(Math.max(0, Math.min(3, base / 25)))],
    gaps:
      pseudoRandom(seed, 50) > 0.5
        ? [
            "Missing encryption at rest",
            "Incomplete audit trails",
            "No incident response plan",
          ].slice(0, Math.floor(pseudoRandom(seed, 55) * 3) + 1)
        : [],
  };
}

function genIpReputation(seed: string) {
  const countries = ["US", "CN", "RU", "KR", "NL", "DE", "BR", "NG"];
  const count = 2 + Math.floor(pseudoRandom(seed, 33) * 3);
  return {
    score: parseFloat(oscillate(0.35, 0.25, seed, "ip").toFixed(2)),
    known_malicious: pseudoRandom(seed, 20) > 0.6,
    source_countries: Array.from({ length: count }, (_, i) => pickRandom(countries, seed, i + 10)),
    last_seen_days: Math.floor(oscillate(14, 10, seed, "last")),
  };
}

function genSecurityNews(seed: string) {
  const headlines = [
    "Critical RCE vulnerability discovered in widely-used VPN appliance",
    "New phishing campaign targets financial institutions worldwide",
    "Zero-day exploit in popular CMS framework actively exploited",
    "Security researcher discovers backdoor in supply chain dependency",
    "Major cloud provider reports 40% increase in DDoS attacks",
    "New AI-powered defense system blocks 99.9% of advanced threats",
    "Ransomware attack on healthcare system highlights infrastructure risks",
    "Nation-state APT group targeting critical infrastructure sectors",
    "New vulnerability disclosure framework gains industry adoption",
    "Quantum-safe encryption standards proposed by security consortium",
  ];
  const count = 2 + Math.floor(pseudoRandom(seed, (Date.now() % 90000) / 15000) * 3);
  return Array.from({ length: count }, (_, i) => ({
    title: headlines[Math.floor(pseudoRandom(seed, i + 50) * headlines.length)],
    url: "https://security.example.com/news/" + shortId("news", i),
  }));
}

// ════════════════════════════════════════════════════════════════
// Health Generators
// ════════════════════════════════════════════════════════════════

function genDiagnostics(seed: string) {
  const symptoms = [
    "Chest pain, shortness of breath",
    "Persistent headache, vision changes",
    "Abdominal pain, nausea",
    "Fever, cough, fatigue",
    "Joint pain, stiffness",
    "Dizziness, loss of balance",
    "Skin rash, itching",
    "Sore throat, difficulty swallowing",
  ];
  const urgencies = ["low", "moderate", "high"];
  const count = 3 + Math.floor(pseudoRandom(seed, (Date.now() % 50000) / 10000) * 4);
  return Array.from({ length: count }, (_, i) => ({
    analyzed_symptoms: pickRandom(symptoms, seed, i + 5),
    possible_conditions: [
      {
        name: pickRandom(["Condition A", "Condition B", "Condition C"], seed, i),
        probability: parseFloat((0.3 + pseudoRandom(seed, i + 10) * 0.6).toFixed(2)),
        severity: pickRandom(["mild", "moderate", "severe"], seed, i + 15),
        action: pickRandom(
          ["Monitor", "Prescribe medication", "Refer to specialist"],
          seed,
          i + 20
        ),
      },
    ],
    urgency: pickRandom(urgencies, seed, i + 3),
    recommendation: pickRandom(
      [
        "Rest and hydrate",
        "Schedule follow-up in 48h",
        "Immediate referral to specialist",
        "Over-the-counter medication",
      ],
      seed,
      i + 8
    ),
  }));
}

function genVitals(seed: string) {
  const metrics = [
    "Heart Rate",
    "Blood Pressure",
    "Temperature",
    "O2 Sat",
    "Respiratory Rate",
    "Blood Glucose",
  ];
  const count = 3 + Math.floor(pseudoRandom(seed, (Date.now() % 40000) / 10000) * 3);
  return Array.from({ length: count }, (_, i) => {
    const base = 50 + pseudoRandom(seed, i + 100) * 200;
    const current = oscillate(base, base * 0.1, seed, "vital" + i);
    return {
      patient_id: "PAT-" + shortId("patient", i),
      metric: pickRandom(metrics, seed, i + 3),
      baseline: Math.round(base),
      current: Math.round(current),
      trend: pickRandom(["stable", "rising", "falling", "fluctuating"], seed, i + 7),
      alert: pseudoRandom(seed, i + 50) > 0.75,
    };
  });
}

function genDrugInteractions(seed: string) {
  const meds = [
    ["Warfarin", "Aspirin"],
    ["Lisinopril", "Potassium"],
    ["Metformin", "Insulin"],
    ["Atorvastatin", "Clarithromycin"],
    ["Fluoxetine", "MAOI"],
    ["Digoxin", "Amiodarone"],
  ];
  const count = 1 + Math.floor(pseudoRandom(seed, (Date.now() % 70000) / 15000) * 2);
  return Array.from({ length: count }, (_, i) => ({
    medications: pickRandom(meds, seed, i + 5),
    interactions_found: Math.floor(pseudoRandom(seed, i + 10) * 3),
    interactions: Array.from(
      { length: Math.floor(pseudoRandom(seed, i + 15) * 2) + 1 },
      (_, j) => ({
        drugs: ["Drug A", "Drug B"],
        severity: pickRandom(["mild", "moderate", "severe"], seed, i + j + 20),
        warning: pickRandom(
          [
            "Increased bleeding risk",
            "Serum potassium elevation",
            "Hypoglycemia risk",
            "Muscle pain risk",
          ],
          seed,
          i + j + 25
        ),
      })
    ),
  }));
}

function genTelehealth(seed: string) {
  const urgencies = ["routine", "urgent", "emergent"];
  const count = 2 + Math.floor(pseudoRandom(seed, (Date.now() % 60000) / 15000) * 4);
  return Array.from({ length: count }, (_, i) => ({
    symptoms: pickRandom(
      [
        "Cough and fever",
        "Skin rash",
        "Anxiety",
        "Back pain",
        "Allergic reaction",
        "Eye irritation",
      ],
      seed,
      i + 8
    ),
    age: 25 + Math.floor(pseudoRandom(seed, i + 3) * 55),
    urgency: pickRandom(urgencies, seed, i + 5),
    recommendation: pickRandom(
      [
        "Telehealth consult scheduled",
        "Visit urgent care",
        "Prescription sent to pharmacy",
        "Monitor symptoms for 24h",
      ],
      seed,
      i + 10
    ),
  }));
}

// ════════════════════════════════════════════════════════════════
// Finance Generators
// ════════════════════════════════════════════════════════════════

function genRisk(seed: string) {
  return {
    asset: pickRandom(
      ["Tech Growth Fund", "Global Equity ETF", "Corporate Bond Portfolio", "Real Estate Trust"],
      seed,
      100
    ),
    portfolio_value: Math.round(oscillate(2500000, 500000, seed, "portfolio")),
    var_95_1d: Math.round(oscillate(45000, 15000, seed, "var")),
    var_95_pct: parseFloat(oscillate(1.8, 0.6, seed, "varpct").toFixed(2)),
    sharpe_estimate: parseFloat(oscillate(1.4, 0.5, seed, "sharpe").toFixed(2)),
    beta: parseFloat(oscillate(1.1, 0.3, seed, "beta").toFixed(2)),
    risk_rating: pickRandom(["low", "medium", "high"], seed, 55),
    diversification_score: Math.round(oscillate(6.5, 2.5, seed, "diverse")),
    recommendation: pickRandom(
      [
        "Maintain current allocation",
        "Increase bond exposure",
        "Consider hedging strategies",
        "Rebalance quarterly",
      ],
      seed,
      77
    ),
  };
}

function genMarket(seed: string) {
  return {
    market: pickRandom(["S&P 500", "NASDAQ", "FTSE 100", "Nikkei 225", "DAX"], seed, 120),
    predicted_direction: pickRandom(["bullish", "bearish", "neutral"], seed, 66),
    confidence: parseFloat(oscillate(0.65, 0.2, seed, "mktconf").toFixed(2)),
    price_target_pct: parseFloat(oscillate(3.5, 5, seed, "mktpct").toFixed(1)),
    volatility_forecast: pickRandom(["low", "moderate", "elevated", "high"], seed, 88),
  };
}

function genFraud(seed: string) {
  const count = 2 + Math.floor(pseudoRandom(seed, (Date.now() % 55000) / 10000) * 4);
  return Array.from({ length: count }, (_, i) => ({
    transaction_id: "TXN-" + shortId("fraud", i),
    amount: Math.round(oscillate(2500, 2000, seed, "amt" + i) + pseudoRandom(seed, i + 10) * 3000),
    fraud_score: parseFloat(oscillate(0.4, 0.3, seed, "fscore" + i).toFixed(2)),
    risk_level: pickRandom(["low", "medium", "high"], seed, i + 20),
    action: pickRandom(["approved", "flagged", "blocked", "pending_review"], seed, i + 30),
  }));
}

function genCredit(seed: string) {
  const count = 2 + Math.floor(pseudoRandom(seed, (Date.now() % 65000) / 15000) * 3);
  return Array.from({ length: count }, (_, i) => ({
    applicant_id: "APP-" + shortId("credit", i),
    credit_score: Math.round(oscillate(680, 100, seed, "cs" + i)),
    rating: pickRandom(["excellent", "good", "fair", "poor"], seed, i + 15),
    approval_probability: parseFloat(oscillate(0.6, 0.25, seed, "approv" + i).toFixed(2)),
  }));
}

function genPayments(seed: string) {
  const count = 2 + Math.floor(pseudoRandom(seed, (Date.now() % 50000) / 15000) * 2);
  return Array.from({ length: count }, (_, i) => ({
    account_id: "ACC-" + shortId("pay", i),
    total_transactions: Math.floor(oscillate(150, 80, seed, "txn" + i)),
    total_volume: Math.round(oscillate(50000, 30000, seed, "vol" + i)),
    anomaly_count: Math.floor(pseudoRandom(seed, i + 20) * 4),
    spending_trend: pickRandom(["increasing", "stable", "decreasing", "seasonal"], seed, i + 30),
  }));
}

// ════════════════════════════════════════════════════════════════
// Retail / E-commerce Generators
// ════════════════════════════════════════════════════════════════

function genForecast(seed: string) {
  const count = 3 + Math.floor(pseudoRandom(seed, (Date.now() % 70000) / 15000) * 4);
  return Array.from({ length: count }, (_, i) => {
    const stock = oscillate(450, 200, seed, "stock" + i);
    const demand = oscillate(500, 250, seed, "demand" + i);
    return {
      sku: "SKU-" + shortId("sku", i),
      current_stock: Math.max(0, Math.round(stock)),
      projected_demand: Math.max(0, Math.round(demand)),
      recommended_order_qty: Math.max(
        0,
        Math.round(demand - stock + oscillate(50, 30, seed, "buffer" + i))
      ),
      confidence: parseFloat(oscillate(0.82, 0.12, seed, "conf" + i).toFixed(2)),
    };
  });
}

function genInventory(seed: string) {
  const totalSkus = Math.round(oscillate(1200, 200, seed, "totalsku"));
  const stockoutRisks = Math.floor(oscillate(45, 25, seed, "stockrisk"));
  const overstocks = Math.floor(oscillate(85, 35, seed, "overstock"));
  return {
    summary: {
      total_skus: Math.max(1, totalSkus),
      stockout_risks: Math.max(0, stockoutRisks),
      overstocks: Math.max(0, overstocks),
    },
    alerts: Array.from({ length: Math.min(3, stockoutRisks) }, (_, i) => ({
      sku: "SKU-" + shortId("alert", i),
      status: pickRandom(["critical", "warning"], seed, i + 10),
      days_remaining: Math.floor(pseudoRandom(seed, i + 20) * 14),
    })),
    reorder_recommendations: Array.from(
      { length: 2 + Math.floor(pseudoRandom(seed, 99) * 2) },
      (_, i) => ({
        sku: "SKU-" + shortId("reorder", i),
        qty: Math.floor(pseudoRandom(seed, i + 30) * 500 + 50),
        supplier: pickRandom(
          ["GlobalSupply Co", "PrimeLogistics Inc", "FastShip Corp"],
          seed,
          i + 5
        ),
      })
    ),
    healthy: Array.from({ length: Math.floor(pseudoRandom(seed, 88) * 8) }, (_, i) => ({
      sku: "SKU-" + shortId("healthy", i),
      status: "healthy",
      days_supply: 30 + Math.floor(pseudoRandom(seed, i + 40) * 60),
    })),
  };
}

function genSuppliers(seed: string) {
  const count = 2 + Math.floor(pseudoRandom(seed, (Date.now() % 60000) / 20000) * 3);
  return Array.from({ length: count }, (_, i) => ({
    supplier: pickRandom(
      [
        "GlobalSupply Co",
        "PrimeLogistics Inc",
        "FastShip Corp",
        "QualityParts Ltd",
        "ReliableSource GmbH",
      ],
      seed,
      i + 3
    ),
    risk_score: Math.round(oscillate(45, 25, seed, "supp" + i)),
    classification: pickRandom(["preferred", "standard", "at_risk"], seed, i + 8),
    on_time_delivery_pct: Math.round(oscillate(88, 12, seed, "otd" + i)),
  }));
}

function genElasticity(seed: string) {
  return {
    sku: "SKU-" + shortId("elas", 0),
    price_change_pct: parseFloat(oscillate(5, 8, seed, "pricechg").toFixed(1)),
    elasticity: parseFloat(oscillate(1.5, 1, seed, "elas").toFixed(2)),
    projected_demand_change_pct: parseFloat(oscillate(-3, 10, seed, "demchg").toFixed(1)),
  };
}

// ════════════════════════════════════════════════════════════════
// Transport Generators
// ════════════════════════════════════════════════════════════════

function genTraffic(seed: string) {
  const zones = [
    "Downtown Core",
    "East Corridor",
    "West Side Highway",
    "North Bridge",
    "South Expressway",
    "Airport Access",
    "Harbor Tunnel",
  ];
  const count = 3 + Math.floor(pseudoRandom(seed, (Date.now() % 40000) / 10000) * 3);
  return Array.from({ length: count }, (_, i) => ({
    zone: pickRandom(zones, seed, i + 2),
    current_congestion: Math.round(oscillate(4.5, 3, seed, "cong" + i)),
    predicted_improvement: pickRandom(
      ["+15% in 30min", "+8% in 1h", "stable", "-10% expected"],
      seed,
      i + 8
    ),
    incident_nearby: pseudoRandom(seed, i + 15) > 0.7,
  }));
}

function genFleet(seed: string) {
  const count = 2 + Math.floor(pseudoRandom(seed, (Date.now() % 50000) / 20000) * 2);
  return Array.from({ length: count }, (_, i) => ({
    vehicles_available: Math.floor(oscillate(45, 15, seed, "veh" + i)),
    shifts: Math.floor(oscillate(30, 10, seed, "shift" + i)),
    utilization_pct: Math.round(oscillate(72, 18, seed, "util" + i)),
    recommendation: pickRandom(
      [
        "Maintain current fleet",
        "Add 3 vehicles to meet demand",
        "Optimize shift schedules",
        "Consider route consolidation",
      ],
      seed,
      i + 12
    ),
  }));
}

function genRoutes(seed: string) {
  const count = 2 + Math.floor(pseudoRandom(seed, (Date.now() % 60000) / 20000) * 3);
  return Array.from({ length: count }, (_, i) => ({
    stops: [
      pickRandom(["Warehouse A", "Distribution Center", "Hub B"], seed, i),
      pickRandom(["Delivery Point 1", "Retail Store", "Customer Site"], seed, i + 5),
    ],
    estimated_distance_km: Math.round(oscillate(320, 150, seed, "dist" + i)),
    estimated_time_min: Math.round(oscillate(240, 90, seed, "time" + i)),
    fuel_cost_est: Math.round(oscillate(180, 80, seed, "fuel" + i)),
  }));
}

// ════════════════════════════════════════════════════════════════
// Manufacturing Generators
// ════════════════════════════════════════════════════════════════

function genMaintenance(seed: string) {
  const count = 3 + Math.floor(pseudoRandom(seed, (Date.now() % 45000) / 10000) * 3);
  return Array.from({ length: count }, (_, i) => ({
    machine_id: "MCH-" + shortId("mch", i),
    status: pickRandom(["healthy", "warning", "critical"], seed, i + 5),
    temp_c: Math.round(oscillate(65, 25, seed, "temp" + i)),
    vibration_hz: Math.round(oscillate(45, 20, seed, "vib" + i)),
    failure_risk_pct: Math.round(oscillate(30, 25, seed, "risk" + i)),
    days_to_failure: Math.max(1, Math.floor(oscillate(60, 40, seed, "dtf" + i))),
  }));
}

function genQC(seed: string) {
  const count = 2 + Math.floor(pseudoRandom(seed, (Date.now() % 50000) / 15000) * 3);
  return Array.from({ length: count }, (_, i) => ({
    batch_id: "BATCH-" + shortId("batch", i),
    items_scanned: Math.floor(oscillate(500, 200, seed, "scan" + i)),
    defects_found: Math.floor(pseudoRandom(seed, i + 10) * 15),
    defect_rate: parseFloat((pseudoRandom(seed, i + 20) * 0.04).toFixed(4)),
    status: pickRandom(["pass", "pass", "pass", "fail"], seed, i + 30),
  }));
}

function genLogistics(seed: string) {
  const count = 2 + Math.floor(pseudoRandom(seed, (Date.now() % 55000) / 18000) * 2);
  return Array.from({ length: count }, (_, i) => ({
    route_id: "RTE-" + shortId("rte", i),
    status: pickRandom(["on_time", "on_time", "delayed"], seed, i + 5),
    eta_days: Math.round(oscillate(5, 3, seed, "eta" + i)),
    reroute_cost_usd: Math.round(oscillate(1200, 800, seed, "rcost" + i)),
  }));
}

// ════════════════════════════════════════════════════════════════
// Tourism / Hospitality Generators
// ════════════════════════════════════════════════════════════════

function genBookings(seed: string) {
  const count = 3 + Math.floor(pseudoRandom(seed, (Date.now() % 60000) / 15000) * 3);
  return Array.from({ length: count }, (_, i) => ({
    property: pickRandom(
      ["Grand Hotel", "Seaside Resort", "Mountain Lodge", "City Boutique", "Lake House"],
      seed,
      i + 3
    ),
    occupancy_pct: Math.round(oscillate(72, 20, seed, "occ" + i)),
    predictive_no_shows: Math.floor(pseudoRandom(seed, i + 15) * 8),
    net_expected_occupancy: Math.round(oscillate(68, 22, seed, "netocc" + i)),
  }));
}

function genPricingTourism(seed: string) {
  const rooms = ["Standard", "Deluxe", "Suite", "Penthouse", "Family Room", "Corner Suite"];
  const count = 3 + Math.floor(pseudoRandom(seed, (Date.now() % 50000) / 15000) * 2);
  return Array.from({ length: count }, (_, i) => ({
    room: pickRandom(rooms, seed, i + 2),
    base_price: Math.round(oscillate(180, 80, seed, "bpr" + i)),
    recommended_price: Math.round(oscillate(210, 100, seed, "rpr" + i)),
    reason: pickRandom(
      [
        "Demand surge",
        "Competitor pricing",
        "Seasonal adjustment",
        "Event premium",
        "Weekend rate",
      ],
      seed,
      i + 8
    ),
  }));
}

function genConcierge(seed: string) {
  const count = 2 + Math.floor(pseudoRandom(seed, (Date.now() % 40000) / 10000) * 3);
  return Array.from({ length: count }, (_, i) => ({
    guest_id: "GST-" + shortId("gst", i),
    sentiment: pickRandom(["positive", "neutral", "negative"], seed, i + 4),
    intent: pickRandom(
      [
        "room service",
        "late checkout",
        "housekeeping",
        "dining reservation",
        "transportation",
        "events",
      ],
      seed,
      i + 7
    ),
    automated_response: pickRandom(
      ["Confirmed", "Scheduled", "Forwarded to front desk", "Processed"],
      seed,
      i + 12
    ),
    upsell:
      pseudoRandom(seed, i + 20) > 0.6
        ? pickRandom(["Spa package", "Breakfast upgrade", "Airport transfer"], seed, i + 25)
        : null,
  }));
}

function genVisitorDataTourism(seed: string) {
  const venues = [
    "Art Museum",
    "Historical Museum",
    "Science Center",
    "Botanical Garden",
    "Aquarium",
  ];
  const count = 2 + Math.floor(pseudoRandom(seed, (Date.now() % 50000) / 15000) * 2);
  return Array.from({ length: count }, (_, i) => ({
    venue: pickRandom(venues, seed, i + 3),
    daily_visitors: Math.round(oscillate(1200, 500, seed, "vis" + i)),
    engagement_score: Math.round(oscillate(68, 18, seed, "eng" + i)),
    recommended_strategies: [
      pickRandom(
        [
          "Social media campaign",
          "Student discount program",
          "Evening hours extension",
          "Group tour packages",
        ],
        seed,
        i + 10
      ),
    ],
  }));
}

// ════════════════════════════════════════════════════════════════
// Cultural Heritage Generators
// ════════════════════════════════════════════════════════════════

function genSites(seed: string) {
  const siteNames = [
    "Colosseum",
    "Machu Picchu",
    "Great Wall",
    "Taj Mahal",
    "Petra",
    "Chichen Itza",
    "Angkor Wat",
  ];
  const eras = ["Ancient Roman", "Incan", "Ming Dynasty", "Mughal", "Nabatean", "Maya", "Khmer"];
  const count = 2 + Math.floor(pseudoRandom(seed, (Date.now() % 70000) / 20000) * 3);
  return Array.from({ length: count }, (_, i) => ({
    site: pickRandom(siteNames, seed, i + 2),
    era: pickRandom(eras, seed, i + 8),
    significance: pickRandom(
      ["UNESCO World Heritage", "National Monument", "Cultural Icon"],
      seed,
      i + 15
    ),
    annual_visitors: Math.round(oscillate(800000, 400000, seed, "ann" + i)),
    conservation_status: pickRandom(["good", "requires attention", "critical"], seed, i + 20),
  }));
}

function genExhibitions(seed: string) {
  const count = 2 + Math.floor(pseudoRandom(seed, (Date.now() % 60000) / 20000) * 2);
  return Array.from({ length: count }, (_, i) => ({
    theme: pickRandom(
      [
        "Renaissance Masters",
        "Modern Art Movement",
        "Ancient Egypt",
        "Space Exploration",
        "Indigenous Cultures",
        "Photography Through Time",
      ],
      seed,
      i + 3
    ),
    recommended_duration_days: 30 + Math.floor(pseudoRandom(seed, i + 10) * 90),
    estimated_visitors: Math.round(oscillate(45000, 20000, seed, "estv" + i)),
    ticket_price: Math.round(oscillate(18, 10, seed, "tkt" + i)),
    projected_revenue: Math.round(oscillate(800000, 400000, seed, "rev" + i)),
  }));
}

function genTours(seed: string) {
  const count = 2 + Math.floor(pseudoRandom(seed, (Date.now() % 50000) / 15000) * 2);
  return Array.from({ length: count }, (_, i) => ({
    site: pickRandom(
      ["Colosseum VR", "Louvre 360", "British Museum Tour", "Luxor Temple Walk"],
      seed,
      i + 2
    ),
    interest: pickRandom(["high", "medium", "growing"], seed, i + 8),
    narration: pickRandom(
      ["Expert guided", "Self-paced audio", "Interactive storytelling"],
      seed,
      i + 12
    ),
    audio_duration_seconds: 180 + Math.floor(pseudoRandom(seed, i + 18) * 600),
  }));
}

// ════════════════════════════════════════════════════════════════
// Utilities Generators
// ════════════════════════════════════════════════════════════════

function genResources(seed: string) {
  const resources = ["Water", "Electricity", "Natural Gas", "Petroleum", "Coal", "Solar Capacity"];
  const count = 3 + Math.floor(pseudoRandom(seed, (Date.now() % 50000) / 12000) * 3);
  return Array.from({ length: count }, (_, i) => ({
    resource: pickRandom(resources, seed, i + 2),
    demand: Math.round(oscillate(850, 300, seed, "dem" + i)),
    supply: Math.round(oscillate(780, 280, seed, "sup" + i)),
    deficit: Math.round(oscillate(-70, 100, seed, "def" + i)),
    status: pickRandom(["ok", "warning", "critical"], seed, i + 8),
  }));
}

function genServices(seed: string) {
  const services = [
    "Waste Collection",
    "Public Transport",
    "Water Supply",
    "Parks & Rec",
    "Street Lighting",
    "Emergency Services",
  ];
  const count = 2 + Math.floor(pseudoRandom(seed, (Date.now() % 60000) / 15000) * 3);
  return Array.from({ length: count }, (_, i) => ({
    service: pickRandom(services, seed, i + 2),
    kpi_score: Math.round(oscillate(75, 18, seed, "kpi" + i)),
    status: pickRandom(["excellent", "satisfactory", "needs_improvement"], seed, i + 8),
    citizen_satisfaction: parseFloat(oscillate(0.7, 0.2, seed, "sat" + i).toFixed(2)),
    trend: pickRandom(["improving", "stable", "declining"], seed, i + 14),
  }));
}

function genWaste(seed: string) {
  const districts = [
    "North District",
    "South District",
    "East Ward",
    "West End",
    "Central Hub",
    "Suburban Zone",
  ];
  const count = 2 + Math.floor(pseudoRandom(seed, (Date.now() % 55000) / 15000) * 3);
  return Array.from({ length: count }, (_, i) => ({
    district: pickRandom(districts, seed, i + 2),
    total_waste_tons: Math.round(oscillate(450, 200, seed, "waste" + i)),
    recycled_pct: Math.round(oscillate(38, 15, seed, "recy" + i)),
    landfill_pct: Math.round(oscillate(52, 18, seed, "land" + i)),
    collection_efficiency: Math.round(oscillate(82, 12, seed, "collect" + i)),
  }));
}

function genGrid(seed: string) {
  const regions = [
    "North Grid",
    "South Grid",
    "East Region",
    "West Zone",
    "Central Network",
    "Island Grid",
  ];
  const count = 2 + Math.floor(pseudoRandom(seed, (Date.now() % 45000) / 12000) * 3);
  return Array.from({ length: count }, (_, i) => ({
    region: pickRandom(regions, seed, i + 2),
    current_load_mw: Math.round(oscillate(850, 300, seed, "load" + i)),
    capacity_mw: Math.round(oscillate(1200, 200, seed, "cap" + i)),
    utilization_pct: Math.round(oscillate(72, 18, seed, "utilg" + i)),
    renewable_share_pct: Math.round(oscillate(35, 15, seed, "ren" + i)),
    status: pickRandom(["ok", "warning", "critical"], seed, i + 8),
  }));
}

// ════════════════════════════════════════════════════════════════
// SME Generators
// ════════════════════════════════════════════════════════════════

function genWorkflows(seed: string) {
  const processes = [
    "Invoice Processing",
    "Employee Onboarding",
    "Expense Reporting",
    "Contract Approval",
    "Customer Onboarding",
    "Order Fulfillment",
  ];
  const count = 2 + Math.floor(pseudoRandom(seed, (Date.now() % 60000) / 15000) * 3);
  return Array.from({ length: count }, (_, i) => ({
    process: pickRandom(processes, seed, i + 3),
    employees_involved: Math.floor(oscillate(25, 15, seed, "emp" + i)),
    hours_saved_per_month: Math.round(oscillate(120, 60, seed, "hrs" + i)),
    cost_savings_annual: Math.round(oscillate(48000, 25000, seed, "cost" + i)),
  }));
}

function genDocuments(seed: string) {
  const types = ["Invoice", "Contract", "Report", "Form", "Letter", "Proposal"];
  const count = 2 + Math.floor(pseudoRandom(seed, (Date.now() % 50000) / 12000) * 3);
  return Array.from({ length: count }, (_, i) => ({
    document_type: pickRandom(types, seed, i + 2),
    confidence: parseFloat(oscillate(0.88, 0.1, seed, "docconf" + i).toFixed(2)),
    pages_processed: Math.floor(pseudoRandom(seed, i + 10) * 25 + 1),
    fields_extracted: [
      pickRandom(["amount", "date", "name", "address", "tax_id"], seed, i + 15),
      pickRandom(["total", "vendor", "invoice_no", "description"], seed, i + 20),
    ],
  }));
}

function genSupport(seed: string) {
  const queries = [
    "How do I reset my password?",
    "Can I upgrade my plan?",
    "Where is my order?",
    "Report a bug in the dashboard",
    "Request a feature",
    "Billing question",
  ];
  const count = 2 + Math.floor(pseudoRandom(seed, (Date.now() % 45000) / 10000) * 3);
  return Array.from({ length: count }, (_, i) => ({
    query: pickRandom(queries, seed, i + 3),
    detected_intent: pickRandom(["account", "billing", "support", "feature_request"], seed, i + 8),
    sentiment: pickRandom(["positive", "neutral", "negative"], seed, i + 12),
    response: pickRandom(
      [
        "Password reset link sent",
        "Plan upgrade options provided",
        "Order status updated",
        "Bug report submitted",
        "Feature request logged",
        "Billing explanation sent",
      ],
      seed,
      i + 16
    ),
    escalated: pseudoRandom(seed, i + 20) > 0.7,
  }));
}

function genSupplyChain(seed: string) {
  const chains = [
    "SC-Production",
    "SC-Distribution",
    "SC-Raw Materials",
    "SC-Finished Goods",
    "SC-Parts Supply",
  ];
  const count = 2 + Math.floor(pseudoRandom(seed, (Date.now() % 55000) / 15000) * 2);
  return Array.from({ length: count }, (_, i) => ({
    chain_id: pickRandom(chains, seed, i + 2) + "-" + shortId("sc", i),
    health_score: Math.round(oscillate(72, 20, seed, "healthsc" + i)),
    lead_time_days: Math.round(oscillate(14, 8, seed, "lead" + i)),
    risk_level: pickRandom(["low", "medium", "high"], seed, i + 10),
    bottlenecks:
      pseudoRandom(seed, i + 15) > 0.5
        ? [
            pickRandom(
              ["Supplier delay", "Customs hold", "Transport shortage", "Quality check"],
              seed,
              i + 20
            ),
          ]
        : [],
  }));
}

// ════════════════════════════════════════════════════════════════
// Professional Services Generators
// ════════════════════════════════════════════════════════════════

function genLegal(seed: string) {
  const docs = [
    "Service Agreement",
    "NDA",
    "Employment Contract",
    "Lease Agreement",
    "Partnership Agreement",
    "License Agreement",
  ];
  const types = ["contract", "non-disclosure", "employment", "lease", "partnership"];
  const count = 2 + Math.floor(pseudoRandom(seed, (Date.now() % 60000) / 20000) * 3);
  return Array.from({ length: count }, (_, i) => ({
    doc: pickRandom(docs, seed, i + 2),
    type: pickRandom(types, seed, i + 8),
    risk_score: pickRandom(["low", "medium", "high"], seed, i + 12),
    obligations: Array.from({ length: 1 + Math.floor(pseudoRandom(seed, i + 18) * 2) }, (_, j) =>
      pickRandom(
        [
          "Confidentiality",
          "Non-compete",
          "IP Assignment",
          "Indemnification",
          "Termination Notice",
        ],
        seed,
        i + j + 20
      )
    ),
  }));
}

function genAccounting(seed: string) {
  const vendors = [
    "Acme Corp",
    "TechSupply Inc",
    "DataServices LLC",
    "CloudHost Ltd",
    "ConsultPro Group",
  ];
  const count = 2 + Math.floor(pseudoRandom(seed, (Date.now() % 50000) / 15000) * 3);
  return Array.from({ length: count }, (_, i) => ({
    invoice_id: "INV-" + shortId("inv", i),
    vendor: pickRandom(vendors, seed, i + 3),
    amount: Math.round(oscillate(3500, 2500, seed, "amtinv" + i)),
    anomalies_detected: pseudoRandom(seed, i + 10) > 0.8,
    auto_approved: pseudoRandom(seed, i + 15) > 0.3,
  }));
}

function genDataMgmt(seed: string) {
  const datasets = [
    "Customer DB",
    "Employee Records",
    "Transaction Logs",
    "Marketing Data",
    "Analytics Cache",
    "Support Tickets",
  ];
  const count = 2 + Math.floor(pseudoRandom(seed, (Date.now() % 55000) / 18000) * 2);
  return Array.from({ length: count }, (_, i) => ({
    dataset: pickRandom(datasets, seed, i + 2),
    pii_records_found: Math.floor(oscillate(1500, 1000, seed, "pii" + i)),
    compliance: pickRandom(
      ["GDPR-ready", "HIPAA-compliant", "PCI-DSS-ready", "needs_review", "compliant"],
      seed,
      i + 8
    ),
  }));
}

// ════════════════════════════════════════════════════════════════
// Telecom Generators
// ════════════════════════════════════════════════════════════════

function genNetworkHealth(seed: string) {
  const elements = [
    ["core_router_01", "core", "US-East"],
    ["core_router_02", "core", "US-West"],
    ["edge_switch_14", "edge", "US-East"],
    ["edge_switch_22", "edge", "EU-Central"],
    ["radio_tower_07", "radio", "US-West"],
    ["fiber_ring_03", "transport", "EU-Central"],
    ["backhaul_05", "transport", "APAC"],
    ["small_cell_31", "radio", "APAC"],
  ];
  return elements.map(([element, type, region], i) => ({
    id: "tel-" + (i + 1),
    element,
    type,
    health_score: parseFloat((oscillate(96, 3, seed, "health" + i) + pseudoRandom(seed, i)).toFixed(1)),
    uptime_pct: parseFloat(oscillate(97.5, 2, seed, "up" + i).toFixed(2)),
    sla_status: pickRandom(["met", "met", "met", "at_risk", "breached"], seed, i + 8),
    region,
  }));
}

function genCapacity(seed: string) {
  const nodes = ["backbone_01", "backbone_02", "metro_agg_11", "metro_agg_12", "edge_pop_03", "edge_pop_09"];
  return nodes.map((node, i) => ({
    id: "cap-" + (i + 1),
    node,
    current_utilization_pct: Math.round(oscillate(65, 25, seed, "cur" + i)),
    forecast_utilization_pct: Math.round(oscillate(75, 28, seed, "for" + i)),
    recommended_action: pickRandom(
      ["no_action", "monitor", "add_capacity", "rebalance_traffic"],
      seed,
      i + 6
    ),
  }));
}

function genFaults(seed: string) {
  const elements = ["core_router_01", "edge_switch_14", "radio_tower_07", "backhaul_05", "small_cell_31"];
  const summaries = [
    "Packet loss above 2% threshold",
    "Latency spike on customer links",
    "Power supply redundancy degraded",
    "Optical signal attenuation on fiber",
    "Handover failures on small cell",
  ];
  const count = 3 + Math.floor(pseudoRandom(seed, (Date.now() % 60000) / 20000) * 2);
  return Array.from({ length: count }, (_, i) => ({
    id: "fault-" + (i + 1),
    element: elements[i % elements.length],
    severity: pickRandom(["low", "medium", "high", "critical"], seed, i + 3),
    status: pickRandom(["open", "triage", "fixing", "resolved"], seed, i + 5),
    opened_at: new Date(Date.now() - i * 5400000).toISOString(),
    summary: summaries[i % summaries.length],
  }));
}

// ════════════════════════════════════════════════════════════════
// Agriculture Generators
// ════════════════════════════════════════════════════════════════

function genYieldForecast(seed: string) {
  const fields = [
    ["field_alpha", "wheat"],
    ["field_beta", "corn"],
    ["field_gamma", "soybean"],
    ["field_delta", "barley"],
    ["field_epsilon", "corn"],
  ];
  return fields.map(([field, crop], i) => ({
    id: "yld-" + (i + 1),
    field,
    crop,
    forecast_tons: parseFloat(oscillate(300, 80, seed, "yf" + i).toFixed(1)),
    previous_tons: parseFloat(oscillate(270, 70, seed, "yp" + i).toFixed(1)),
    confidence: parseFloat((0.82 + pseudoRandom(seed, i + 4) * 0.14).toFixed(2)),
  }));
}

function genIrrigation(seed: string) {
  const zones = [
    ["zone_north", "wheat"],
    ["zone_south", "corn"],
    ["zone_east", "soybean"],
    ["zone_west", "barley"],
  ];
  return zones.map(([zone, crop], i) => ({
    id: "irr-" + (i + 1),
    zone,
    crop,
    schedule: pickRandom(["daily", "every_2_days", "weekly", "sensor_triggered"], seed, i + 7),
    water_needed_mm: Math.round(oscillate(35, 20, seed, "wtr" + i)),
    status: pickRandom(["optimal", "optimal", "low", "over_irrigated"], seed, i + 12),
  }));
}

function genPestRisk(seed: string) {
  const pests = [
    ["field_alpha", "wheat", "aphid"],
    ["field_beta", "corn", "corn_borer"],
    ["field_gamma", "soybean", "armyworm"],
    ["field_delta", "barley", "rust_fungus"],
  ];
  return pests.map(([field, crop, pest], i) => ({
    id: "pst-" + (i + 1),
    field,
    crop,
    pest,
    risk_level: pickRandom(["low", "low", "moderate", "high"], seed, i + 9),
    treatment: pickRandom(
      ["none_required", "biological_control", "targeted_spray", "quarantine_zone"],
      seed,
      i + 14
    ),
  }));
}

// ════════════════════════════════════════════════════════════════
// Education Generators
// ════════════════════════════════════════════════════════════════

function genAtRiskStudents(seed: string) {
  const names = ["Ava Thompson", "Liam Rodriguez", "Maya Patel", "Noah Kim", "Zoe Nguyen", "Ethan Brooks"];
  const count = 4 + Math.floor(pseudoRandom(seed, (Date.now() % 50000) / 15000) * 2);
  return Array.from({ length: count }, (_, i) => ({
    id: "stu-" + (i + 1),
    student_id: "S-2026-" + (1000 + i),
    name: names[i % names.length],
    gpa: parseFloat((1.4 + pseudoRandom(seed, i + 3) * 2.6).toFixed(2)),
    attendance_pct: Math.round(oscillate(80, 18, seed, "att" + i)),
    risk_score: parseFloat((0.05 + pseudoRandom(seed, i + 8) * 0.9).toFixed(2)),
    risk_level: pickRandom(["low", "low", "watch", "high"], seed, i + 12),
  }));
}

function genInterventions(seed: string) {
  const actionPool = ["tutoring", "counseling", "mentorship", "parent_meeting", "study_group"];
  const count = 3 + Math.floor(pseudoRandom(seed, (Date.now() % 55000) / 18000) * 2);
  return Array.from({ length: count }, (_, i) => ({
    id: "plan-" + (i + 1),
    student_id: "S-2026-" + (1000 + i),
    plan: pickRandom(["Academic Support", "Attendance Recovery", "Social-Emotional Support"], seed, i + 4),
    actions: [
      actionPool[Math.floor(pseudoRandom(seed, i + 9) * actionPool.length)],
      actionPool[Math.floor(pseudoRandom(seed, i + 15) * actionPool.length)],
    ],
    status: pickRandom(["draft", "active", "active", "completed"], seed, i + 18),
    owner: pickRandom(["Advisor Ward", "Counselor Reed", "Dean Patel"], seed, i + 22),
  }));
}

function genProgramOutcomes(seed: string) {
  const programs = [
    "STEM Accelerator",
    "Literacy Boost",
    "Math Recovery",
    "College Readiness",
    "Career Pathways",
  ];
  return programs.map((program, i) => ({
    id: "out-" + (i + 1),
    program,
    completion_rate: parseFloat(oscillate(0.82, 0.12, seed, "cr" + i).toFixed(2)),
    avg_score: parseFloat(oscillate(78, 12, seed, "as" + i).toFixed(1)),
    trend: pickRandom(["improving", "stable", "declining"], seed, i + 10),
  }));
}

// ════════════════════════════════════════════════════════════════
// Public Safety Generators
// ════════════════════════════════════════════════════════════════

function genIncidentPriority(seed: string) {
  const types = ["theft", "traffic_accident", "disturbance", "medical_emergency", "fire_report", "suspicious_activity"];
  const locations = ["Downtown", "Riverside", "Northgate", "Southside", "Airport District"];
  const count = 4 + Math.floor(pseudoRandom(seed, (Date.now() % 45000) / 10000) * 2);
  return Array.from({ length: count }, (_, i) => ({
    id: "inc-" + (i + 1),
    incident_id: "INC-" + (2026000 + i),
    type: types[i % types.length],
    priority: pickRandom(["low", "medium", "high", "critical"], seed, i + 4),
    status: pickRandom(["dispatched", "on_scene", "resolving", "closed"], seed, i + 8),
    location: locations[i % locations.length],
    reported_at: new Date(Date.now() - i * 2700000).toISOString(),
  }));
}

function genDispatch(seed: string) {
  const units = [
    ["unit_101", "patrol_car"],
    ["unit_102", "patrol_car"],
    ["unit_207", "ambulance"],
    ["unit_309", "fire_engine"],
    ["unit_114", "motorcycle_unit"],
  ];
  return units.map(([unit_id, unit_type], i) => ({
    id: "disp-" + (i + 1),
    unit_id,
    unit_type,
    status: pickRandom(["available", "en_route", "on_scene", "returning"], seed, i + 5),
    current_incident: pickRandom(["none", "INC-2026001", "INC-2026002", "INC-2026005"], seed, i + 10),
    eta_minutes: Math.round(oscillate(12, 10, seed, "eta" + i)),
  }));
}

function genOpsBriefs(seed: string) {
  const briefs = [
    ["Overnight Shift Summary", "Property crimes down 8%; one critical response in Riverside"],
    ["Weekend Operations Review", "Traffic incidents up 12% near airport; added patrol coverage"],
    ["Special Event Plan", "Concert attendance 40k — staged resource plan active"],
  ];
  const recommendationSets = [
    ["Extend night patrol coverage", "Deploy traffic units pre-rush"],
    ["Pre-position medics at venues", "Monitor hot spots"],
    ["Review camera coverage gaps", "Add drone support"],
  ];
  return briefs.map(([title, highlights], i) => ({
    id: "brf-" + (i + 1),
    title,
    period: pickRandom(["24h", "72h", "weekly"], seed, i + 3),
    highlights,
    recommendations: recommendationSets[i % recommendationSets.length],
  }));
}

// ════════════════════════════════════════════════════════════════
// Real Estate Generators
// ════════════════════════════════════════════════════════════════

function genValuations(seed: string) {
  const properties = [
    ["24 Maple Avenue", "single_family"],
    ["88 Harbor Drive", "condo"],
    ["1500 Oak Street", "multi_family"],
    ["7 Birch Lane", "townhouse"],
    ["330 Commerce Blvd", "commercial"],
  ];
  const locations = ["Midtown", "Westside", "East Village", "Lake District"];
  return properties.map(([property, type], i) => {
    const base = 300000 + pseudoRandom(seed, i + 5) * 1100000;
    return {
      id: "val-" + (i + 1),
      property,
      type,
      valuation: Math.round(oscillate(base, base * 0.06, seed, "val" + i)),
      estimate_low: Math.round(base * 0.93),
      estimate_high: Math.round(base * 1.07),
      confidence: parseFloat((0.84 + pseudoRandom(seed, i + 12) * 0.13).toFixed(2)),
      location: locations[i % locations.length],
    };
  });
}

function genMarketTrends(seed: string) {
  const regions = ["Midtown", "Westside", "East Village", "Lake District", "Airport Corridor"];
  return regions.map((region, i) => ({
    id: "mkt-" + (i + 1),
    region,
    median_price: Math.round(oscillate(600000, 250000, seed, "med" + i)),
    price_change_pct: parseFloat(oscillate(2, 5, seed, "pc" + i).toFixed(1)),
    inventory: Math.round(oscillate(90, 60, seed, "inv" + i)),
    days_on_market: Math.round(oscillate(35, 22, seed, "dom" + i)),
  }));
}

function genComparables(seed: string) {
  const properties = ["24 Maple Avenue", "88 Harbor Drive", "1500 Oak Street"];
  const addresses = ["26 Maple Avenue", "30 Maple Avenue", "19 Maple Avenue", "90 Harbor Drive", "1496 Oak Street"];
  const count = 4 + Math.floor(pseudoRandom(seed, (Date.now() % 60000) / 15000) * 2);
  return Array.from({ length: count }, (_, i) => ({
    id: "cmp-" + (i + 1),
    property: properties[i % properties.length],
    comparable_address: addresses[i % addresses.length],
    price: Math.round(300000 + pseudoRandom(seed, i + 8) * 1150000),
    sqft: Math.round(1400 + pseudoRandom(seed, i + 16) * 3200),
    delta_pct: parseFloat((pseudoRandom(seed, i + 20) * 17 - 8).toFixed(1)),
  }));
}

// ════════════════════════════════════════════════════════════════
// Master generator — returns data for any sector/tool combo
// ════════════════════════════════════════════════════════════════

export type SectorToolGenerator = (seed: string) => unknown;

const SECTOR_TOOL_GENERATORS: Record<string, Record<string, SectorToolGenerator>> = {
  cybersecurity: {
    threats: genThreats,
    vulnerabilities: genVulnerabilities,
    compliance: genCompliance,
    "ip-reputation": genIpReputation,
    news: genSecurityNews,
  },
  health: {
    diagnostics: genDiagnostics,
    vitals: genVitals,
    "drug-interactions": genDrugInteractions,
    telehealth: genTelehealth,
  },
  finance: {
    risk: genRisk,
    market: genMarket,
    fraud: genFraud,
    credit: genCredit,
    payments: genPayments,
  },
  retail: {
    forecast: genForecast,
    inventory: genInventory,
    suppliers: genSuppliers,
    pricing: genElasticity,
  },
  transport: {
    traffic: genTraffic,
    fleet: genFleet,
    routes: genRoutes,
  },
  manufacturing: {
    maintenance: genMaintenance,
    quality: genQC,
    logistics: genLogistics,
  },
  tourism: {
    bookings: genBookings,
    pricing: genPricingTourism,
    concierge: genConcierge,
    visitors: genVisitorDataTourism,
  },
  utilities: {
    resources: genResources,
    services: genServices,
    waste: genWaste,
    grid: genGrid,
  },
  cultural_heritage: {
    visitors: genVisitorDataTourism,
    sites: genSites,
    exhibitions: genExhibitions,
    tours: genTours,
  },
  sme: {
    workflows: genWorkflows,
    documents: genDocuments,
    support: genSupport,
    "supply-chain": genSupplyChain,
  },
  professional: {
    legal: genLegal,
    accounting: genAccounting,
    "data-management": genDataMgmt,
  },
  telecom: {
    network: genNetworkHealth,
    capacity: genCapacity,
    faults: genFaults,
  },
  agriculture: {
    yield: genYieldForecast,
    irrigation: genIrrigation,
    pests: genPestRisk,
  },
  education: {
    "at-risk": genAtRiskStudents,
    interventions: genInterventions,
    outcomes: genProgramOutcomes,
  },
  public_safety: {
    incidents: genIncidentPriority,
    dispatch: genDispatch,
    briefs: genOpsBriefs,
  },
  real_estate: {
    valuations: genValuations,
    market: genMarketTrends,
    comparables: genComparables,
  },
};

export interface GenerateOptions {
  sector: string;
  tool: string;
}

/**
 * Generate time-varying mock data for a sector tool endpoint.
 * Data changes on each call based on Date.now(), making charts appear live.
 */
export function generateSectorData({ sector, tool }: GenerateOptions): unknown {
  const sectorGens = SECTOR_TOOL_GENERATORS[sector];
  if (!sectorGens) return { ok: false, error: `Unknown sector: ${sector}` };

  const gen = sectorGens[tool];
  if (!gen) return { ok: false, error: `Unknown tool: ${tool} for sector ${sector}` };

  const seed = `${sector}:${tool}`;
  return gen(seed);
}

/**
 * List all available (sector, tool) pairs.
 */
export function listSectorTools(): { sector: string; tool: string }[] {
  const pairs: { sector: string; tool: string }[] = [];
  for (const [sector, tools] of Object.entries(SECTOR_TOOL_GENERATORS)) {
    for (const tool of Object.keys(tools)) {
      pairs.push({ sector, tool });
    }
  }
  return pairs;
}
