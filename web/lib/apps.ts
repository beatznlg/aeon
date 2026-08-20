/**
 * Central AEON OS app registry.
 *
 * This file is a plain TypeScript module (not a route), so it can be safely
 * imported by any API route or component without triggering Next.js Route
 * export validation errors.
 */

export interface AppGoal {
  title: string;
  priority: number;
}

export interface AeonApp {
  id: string;
  name: string;
  category: string;
  description: string;
  icon: string;
  color: string;
  status: "active" | "planned";
  allowed_tools: string[];
  default_goals: AppGoal[];
}

export const APPS: AeonApp[] = [
  {
    id: "cybersecurity",
    name: "CyberSecurity",
    category: "Security & Compliance",
    description:
      "Autonomous threat intelligence, vulnerability tracking, IP reputation, and compliance monitoring for government and business.",
    icon: "🛡️",
    color: "#ef4444",
    status: "active",
    allowed_tools: [
      "threat_lookup",
      "vuln_scan",
      "ip_reputation",
      "compliance_check",
      "security_news",
      "fetch",
      "search",
    ],
    default_goals: [
      { title: "Monitor threat landscape and surface critical alerts", priority: 10 },
      { title: "Track high-severity CVEs affecting client assets", priority: 9 },
      { title: "Maintain IP reputation watchlist and flag malicious actors", priority: 8 },
      { title: "Generate compliance posture score for frameworks", priority: 7 },
    ],
  },
  {
    id: "retail",
    name: "Retail & Wholesale",
    category: "Commerce",
    description:
      "Intelligent stock forecasting, automated supply chains, and personalized digital storefronts.",
    icon: "🛒",
    color: "#10b981",
    status: "active",
    allowed_tools: [
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
    default_goals: [
      {
        title: "Monitor inventory for stockout risks and generate reorder recommendations",
        priority: 10,
      },
      { title: "Forecast high-velocity SKU demand across 30-90 day horizons", priority: 9 },
      { title: "Track supplier risk and flag delivery disruptions", priority: 8 },
      { title: "Optimize pricing and personalize storefront offers", priority: 7 },
    ],
  },
  {
    id: "manufacturing",
    name: "Manufacturing & Engineering",
    category: "Industry",
    description: "Predictive maintenance, automated QC vision systems, and smart logistics.",
    icon: "🏭",
    color: "#f59e0b",
    status: "active",
    allowed_tools: [
      "predictive_maintenance",
      "qc_vision",
      "smart_logistics",
      "fetch",
      "search",
      "math",
    ],
    default_goals: [
      {
        title: "Monitor machine telemetry for failure risks and dispatch maintenance",
        priority: 10,
      },
      { title: "Scan QC pipeline for defect spikes and production anomalies", priority: 9 },
      { title: "Optimize logistics routes and minimize delivery delays", priority: 8 },
    ],
  },
  {
    id: "professional",
    name: "Professional Services",
    category: "Services",
    description:
      "Automated legal document parsing, intelligent accounting workflows, and digital data management.",
    icon: "📄",
    color: "#3b82f6",
    status: "active",
    allowed_tools: [
      "legal_doc_parser",
      "smart_accounting",
      "data_manager",
      "fetch",
      "search",
      "math",
    ],
    default_goals: [
      { title: "Parse incoming contracts and flag high-risk clauses", priority: 10 },
      { title: "Process invoice queue and surface accounting anomalies", priority: 9 },
      { title: "Scan data assets for PII and compliance readiness", priority: 8 },
    ],
  },
  {
    id: "tourism",
    name: "Tourism & Hospitality",
    category: "Hospitality",
    description: "AI-driven booking optimization, dynamic pricing, and automated guest concierge.",
    icon: "🏨",
    color: "#ec4899",
    status: "active",
    allowed_tools: [
      "booking_optimizer",
      "dynamic_pricing",
      "automated_concierge",
      "fetch",
      "search",
      "math",
    ],
    default_goals: [
      { title: "Maximize occupancy through predictive overbooking", priority: 10 },
      { title: "Adjust room rates dynamically based on demand signals", priority: 9 },
      { title: "Triage guest requests and automate concierge responses", priority: 8 },
    ],
  },
  {
    id: "health",
    name: "Health & Medicine",
    category: "Healthcare",
    description:
      "AI-powered diagnostics, patient monitoring, drug interaction checks, and telehealth triage for modern healthcare.",
    icon: "🏥",
    color: "#06b6d4",
    status: "active",
    allowed_tools: [
      "diagnostic_analyzer",
      "health_monitor",
      "drug_interaction_check",
      "medical_literature_search",
      "telehealth_triage",
      "fetch",
      "search",
      "math",
    ],
    default_goals: [
      { title: "Monitor patient vitals and flag abnormal trends", priority: 10 },
      { title: "Cross-check medication regimens for adverse interactions", priority: 9 },
      { title: "Triage incoming telehealth cases by urgency score", priority: 8 },
    ],
  },
  {
    id: "transport",
    name: "Transport & Logistics",
    category: "Mobility",
    description:
      "Traffic optimization, fleet scheduling, route planning, and congestion forecasting for smart mobility.",
    icon: "🚚",
    color: "#f97316",
    status: "active",
    allowed_tools: [
      "traffic_optimizer",
      "fleet_scheduler",
      "route_optimizer",
      "congestion_forecast",
      "smart_logistics",
      "fetch",
      "search",
      "math",
    ],
    default_goals: [
      { title: "Optimize fleet utilization and reduce idle time", priority: 10 },
      { title: "Re-route deliveries around congestion hot spots", priority: 9 },
      { title: "Forecast traffic patterns for proactive scheduling", priority: 8 },
    ],
  },
  {
    id: "finance",
    name: "Finance & Fintech",
    category: "Financial Services",
    description:
      "AI-driven risk analysis, payment pattern monitoring, market forecasting, fraud detection, and credit scoring.",
    icon: "💰",
    color: "#22c55e",
    status: "active",
    allowed_tools: [
      "risk_assessment",
      "payment_analyzer",
      "market_forecast",
      "fraud_detection",
      "credit_scoring",
      "fetch",
      "search",
      "math",
    ],
    default_goals: [
      { title: "Assess portfolio risk exposure and VaR metrics", priority: 10 },
      { title: "Monitor transaction patterns for fraud signals", priority: 9 },
      { title: "Forecast market trends across major indices", priority: 8 },
    ],
  },
  {
    id: "cultural_heritage",
    name: "Cultural Heritage",
    category: "Culture & Tourism",
    description:
      "Visitor engagement strategies, cultural heritage guides, virtual tour assistance, and exhibition planning.",
    icon: "🎭",
    color: "#a855f7",
    status: "active",
    allowed_tools: [
      "visitor_engagement",
      "cultural_heritage_guide",
      "virtual_tour_guide",
      "exhibition_planner",
      "fetch",
      "search",
      "math",
    ],
    default_goals: [
      { title: "Engage visitors with personalized cultural recommendations", priority: 10 },
      { title: "Generate rich cultural heritage content for exhibits", priority: 9 },
      { title: "Guide virtual tour participants with AI narration", priority: 8 },
    ],
  },
  {
    id: "utilities",
    name: "Utilities & Consumer Services",
    category: "Public Sector",
    description:
      "Resource consumption optimization, public service monitoring, waste management, and energy grid oversight.",
    icon: "⚡",
    color: "#eab308",
    status: "active",
    allowed_tools: [
      "resource_optimizer",
      "public_service_monitor",
      "waste_management",
      "energy_grid_monitor",
      "fetch",
      "search",
      "math",
    ],
    default_goals: [
      { title: "Optimize resource allocation across public services", priority: 10 },
      { title: "Monitor utility infrastructure for failure risk", priority: 9 },
      { title: "Track waste management KPIs and recycling rates", priority: 8 },
    ],
  },
  {
    id: "sme",
    name: "SME Business Suite",
    category: "General Business",
    description:
      "Workflow automation, intelligent document processing, AI-powered customer support, and supply chain analytics for SMEs.",
    icon: "🏢",
    color: "#14b8a6",
    status: "active",
    allowed_tools: [
      "workflow_automator",
      "document_processor",
      "customer_support_bot",
      "supply_chain_analyzer",
      "fetch",
      "search",
      "math",
    ],
    default_goals: [
      { title: "Automate repetitive business workflows for efficiency", priority: 10 },
      { title: "Process incoming documents and extract structured data", priority: 9 },
      { title: "Power AI chatbot for customer self-service", priority: 8 },
    ],
  },
  {
    id: "telecom",
    name: "Telecom & Connectivity",
    category: "Communications",
    description:
      "Network health scoring, capacity planning, and automated fault triage for telecom operators and ISPs.",
    icon: "📡",
    color: "#0ea5e9",
    status: "active",
    allowed_tools: ["network_health", "capacity_planner", "fault_triage", "fetch", "search", "math"],
    default_goals: [
      { title: "Monitor network element health and SLA compliance", priority: 10 },
      { title: "Forecast capacity utilization and plan upgrades", priority: 9 },
      { title: "Triage faults by severity and drive resolution", priority: 8 },
    ],
  },
  {
    id: "agriculture",
    name: "Agriculture & Farming",
    category: "AgriTech",
    description:
      "Yield forecasting, precision irrigation scheduling, and pest-risk scoring for modern farms and agribusiness.",
    icon: "🌾",
    color: "#84cc16",
    status: "active",
    allowed_tools: ["yield_forecaster", "irrigation_planner", "pest_risk_scorer", "fetch", "search", "math"],
    default_goals: [
      { title: "Forecast crop yields and flag underperforming fields", priority: 10 },
      { title: "Optimize irrigation schedules against soil moisture", priority: 9 },
      { title: "Score pest risk and recommend treatments", priority: 8 },
    ],
  },
  {
    id: "education",
    name: "Education & Learning",
    category: "EdTech",
    description:
      "At-risk student detection, intervention planning, and program outcome analytics for schools and districts.",
    icon: "🎓",
    color: "#6366f1",
    status: "active",
    allowed_tools: ["at_risk_detector", "intervention_planner", "outcome_analytics", "fetch", "search", "math"],
    default_goals: [
      { title: "Detect at-risk students from attendance and GPA signals", priority: 10 },
      { title: "Build intervention plans and track their status", priority: 9 },
      { title: "Measure program completion and learning outcomes", priority: 8 },
    ],
  },
  {
    id: "public_safety",
    name: "Public Safety & Emergency",
    category: "Government & Safety",
    description:
      "Incident priority scoring, resource dispatch optimization, and operational briefs for emergency services.",
    icon: "🚔",
    color: "#dc2626",
    status: "active",
    allowed_tools: ["incident_prioritizer", "dispatch_optimizer", "ops_briefing", "fetch", "search", "math"],
    default_goals: [
      { title: "Score incident priority to route responders first", priority: 10 },
      { title: "Optimize unit dispatch and coverage gaps", priority: 9 },
      { title: "Generate shift and event operational briefs", priority: 8 },
    ],
  },
  {
    id: "real_estate",
    name: "Real Estate & Property",
    category: "PropertyTech",
    description:
      "Property valuation scoring, market trend analytics, and comparable reports for brokers and investors.",
    icon: "🏠",
    color: "#b45309",
    status: "active",
    allowed_tools: ["valuation_scorer", "market_analytics", "comparable_reporter", "fetch", "search", "math"],
    default_goals: [
      { title: "Score property valuations with confidence ranges", priority: 10 },
      { title: "Track regional market trends and price movements", priority: 9 },
      { title: "Generate comparables reports for listings", priority: 8 },
    ],
  },
];

export function getApp(id: string): AeonApp | undefined {
  return APPS.find((a) => a.id === id);
}
