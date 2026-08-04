/**
 * AEON OS sector registry.
 *
 * Keep sector identity, presentation metadata, endpoint mapping, and response
 * mapping together so a new company or vertical can extend the UI without
 * editing multiple dashboard components.
 */

export interface SectorToolDefinition {
  path: string;
  label: string;
  icon: string;
  responseKey: string;
  targetKey: string;
  entireResponse?: boolean;
}

export interface SectorDefinition {
  id: string;
  name: string;
  icon: string;
  color: string;
  description: string;
  tools: SectorToolDefinition[];
}

export const SECTOR_DEFINITIONS: SectorDefinition[] = [
  {
    id: "cybersecurity",
    name: "Cybersecurity",
    icon: "🛡️",
    color: "#ef4444",
    description: "Threat intelligence, vulnerability scanning, compliance & IP reputation",
    tools: [
      {
        path: "threats",
        label: "Threat Intelligence",
        icon: "⚠️",
        responseKey: "threats",
        targetKey: "threats",
      },
      {
        path: "vulnerabilities",
        label: "Vulnerability Scan",
        icon: "🔓",
        responseKey: "vulnerabilities",
        targetKey: "vulnerabilities",
      },
      {
        path: "compliance",
        label: "Compliance Posture",
        icon: "✓",
        responseKey: "compliance",
        targetKey: "compliance",
      },
      {
        path: "ip-reputation",
        label: "IP Reputation",
        icon: "🌐",
        responseKey: "ip_reputation",
        targetKey: "ip_reputation",
      },
      {
        path: "news",
        label: "Security News",
        icon: "📰",
        responseKey: "news",
        targetKey: "security_news",
      },
    ],
  },
  {
    id: "health",
    name: "Healthcare",
    icon: "🏥",
    color: "#22c55e",
    description: "AI diagnostics, patient vitals, drug interactions & telehealth",
    tools: [
      {
        path: "diagnostics",
        label: "Diagnostic Analysis",
        icon: "🔬",
        responseKey: "diagnostics",
        targetKey: "diagnostics",
      },
      {
        path: "vitals",
        label: "Patient Vitals",
        icon: "📈",
        responseKey: "vitals",
        targetKey: "patient_vitals",
      },
      {
        path: "drug-interactions",
        label: "Drug Interactions",
        icon: "💊",
        responseKey: "interactions",
        targetKey: "drug_interactions",
      },
      {
        path: "telehealth",
        label: "Telehealth Triage",
        icon: "📹",
        responseKey: "triage",
        targetKey: "telehealth",
      },
    ],
  },
  {
    id: "finance",
    name: "Finance",
    icon: "💰",
    color: "#f59e0b",
    description: "Risk analysis, market forecasting, fraud detection & credit scoring",
    tools: [
      {
        path: "risk",
        label: "Risk Assessment",
        icon: "📊",
        responseKey: "risk",
        targetKey: "risk_data",
      },
      {
        path: "market",
        label: "Market Forecast",
        icon: "📈",
        responseKey: "market",
        targetKey: "market_data",
      },
      {
        path: "fraud",
        label: "Fraud Detection",
        icon: "🔍",
        responseKey: "fraud_cases",
        targetKey: "fraud_cases",
      },
      {
        path: "credit",
        label: "Credit Scoring",
        icon: "💳",
        responseKey: "applications",
        targetKey: "credit_applications",
      },
      {
        path: "payments",
        label: "Payment Analysis",
        icon: "💸",
        responseKey: "accounts",
        targetKey: "payment_analysis",
      },
    ],
  },
  {
    id: "retail",
    name: "Retail & E-commerce",
    icon: "📦",
    color: "#a855f7",
    description: "Demand forecasting, inventory optimization & supplier risk",
    tools: [
      {
        path: "forecast",
        label: "Demand Forecast",
        icon: "📊",
        responseKey: "forecast",
        targetKey: "forecast",
      },
      {
        path: "inventory",
        label: "Inventory Status",
        icon: "📋",
        responseKey: "inventory",
        targetKey: "inventory",
      },
      {
        path: "suppliers",
        label: "Supplier Risk",
        icon: "🚚",
        responseKey: "suppliers",
        targetKey: "supplier_risks",
      },
      {
        path: "pricing",
        label: "Price Elasticity",
        icon: "🏷️",
        responseKey: "elasticity",
        targetKey: "price_elasticity",
      },
    ],
  },
  {
    id: "transport",
    name: "Transport & Logistics",
    icon: "🚚",
    color: "#3b82f6",
    description: "Traffic management, fleet scheduling & route optimization",
    tools: [
      {
        path: "traffic",
        label: "Traffic Zones",
        icon: "🚦",
        responseKey: "zones",
        targetKey: "traffic",
      },
      {
        path: "fleet",
        label: "Fleet Scheduling",
        icon: "🚛",
        responseKey: "fleet",
        targetKey: "fleet",
      },
      {
        path: "routes",
        label: "Route Planning",
        icon: "🗺️",
        responseKey: "routes",
        targetKey: "route_plan",
      },
    ],
  },
  {
    id: "manufacturing",
    name: "Manufacturing",
    icon: "🏭",
    color: "#f97316",
    description: "Predictive maintenance, quality control & smart logistics",
    tools: [
      {
        path: "maintenance",
        label: "Machine Health",
        icon: "⚙️",
        responseKey: "machines",
        targetKey: "maintenance",
      },
      {
        path: "quality",
        label: "Quality Control",
        icon: "✓",
        responseKey: "batches",
        targetKey: "qc",
      },
      {
        path: "logistics",
        label: "Smart Logistics",
        icon: "🚚",
        responseKey: "shipments",
        targetKey: "logistics",
      },
    ],
  },
  {
    id: "tourism",
    name: "Tourism & Hospitality",
    icon: "🏨",
    color: "#ec4899",
    description: "Booking optimization, dynamic pricing & automated concierge",
    tools: [
      {
        path: "bookings",
        label: "Booking Optimization",
        icon: "📅",
        responseKey: "bookings",
        targetKey: "bookings",
      },
      {
        path: "pricing",
        label: "Dynamic Pricing",
        icon: "💰",
        responseKey: "pricing",
        targetKey: "pricing",
      },
      {
        path: "concierge",
        label: "Concierge Triage",
        icon: "🤵",
        responseKey: "requests",
        targetKey: "concierge",
      },
      {
        path: "visitors",
        label: "Visitor Analytics",
        icon: "👥",
        responseKey: "venues",
        targetKey: "visitor_data",
      },
    ],
  },
  {
    id: "utilities",
    name: "Utilities & Public Sector",
    icon: "⚡",
    color: "#06b6d4",
    description: "Resource optimization, public services, waste & energy grid",
    tools: [
      {
        path: "resources",
        label: "Resource Optimization",
        icon: "💧",
        responseKey: "resources",
        targetKey: "resource_data",
      },
      {
        path: "services",
        label: "Public Services KPI",
        icon: "🏛️",
        responseKey: "services",
        targetKey: "public_services",
      },
      {
        path: "waste",
        label: "Waste Management",
        icon: "♻️",
        responseKey: "districts",
        targetKey: "waste_data",
      },
      {
        path: "grid",
        label: "Energy Grid",
        icon: "🔌",
        responseKey: "regions",
        targetKey: "energy_grid",
      },
    ],
  },
  {
    id: "cultural_heritage",
    name: "Cultural Heritage",
    icon: "🎭",
    color: "#14b8a6",
    description: "Visitor engagement, heritage sites, exhibitions & virtual tours",
    tools: [
      {
        path: "visitors",
        label: "Visitor Engagement",
        icon: "👥",
        responseKey: "venues",
        targetKey: "visitor_data",
      },
      {
        path: "sites",
        label: "Heritage Sites",
        icon: "🏛️",
        responseKey: "sites",
        targetKey: "heritage_sites",
      },
      {
        path: "exhibitions",
        label: "Exhibition Planning",
        icon: "🖼️",
        responseKey: "exhibitions",
        targetKey: "exhibitions",
      },
      {
        path: "tours",
        label: "Virtual Tours",
        icon: "🎧",
        responseKey: "tours",
        targetKey: "virtual_tours",
      },
    ],
  },
  {
    id: "professional",
    name: "Professional Services",
    icon: "📋",
    color: "#8b5cf6",
    description: "Legal review, accounting audit & data governance for professional teams",
    tools: [
      {
        path: "legal",
        label: "Legal Document Review",
        icon: "⚖️",
        responseKey: "data",
        targetKey: "legal_documents",
        entireResponse: true,
      },
      {
        path: "accounting",
        label: "Accounting Audit",
        icon: "🧾",
        responseKey: "data",
        targetKey: "accounting_audit",
        entireResponse: true,
      },
      {
        path: "data-management",
        label: "Data Compliance",
        icon: "🗂️",
        responseKey: "data",
        targetKey: "data_management",
        entireResponse: true,
      },
    ],
  },
  {
    id: "sme",
    name: "SME Business Suite",
    icon: "🏢",
    color: "#6366f1",
    description: "Workflow automation, document processing, AI support & supply chain",
    tools: [
      {
        path: "workflows",
        label: "Workflow Automation",
        icon: "🤖",
        responseKey: "workflows",
        targetKey: "workflow_data",
      },
      {
        path: "documents",
        label: "Document Processing",
        icon: "📄",
        responseKey: "documents",
        targetKey: "document_queue",
      },
      {
        path: "support",
        label: "AI Support Desk",
        icon: "🎧",
        responseKey: "tickets",
        targetKey: "support_tickets",
      },
      {
        path: "supply-chain",
        label: "Supply Chain",
        icon: "🔗",
        responseKey: "chains",
        targetKey: "supply_chain",
      },
    ],
  },
];

export function getSectorDefinition(sectorId: string): SectorDefinition | undefined {
  return SECTOR_DEFINITIONS.find((sector) => sector.id === sectorId);
}

export function getSectorTools(sectorId: string): SectorToolDefinition[] {
  return getSectorDefinition(sectorId)?.tools ?? [];
}

export function listRegisteredSectors(): SectorDefinition[] {
  return SECTOR_DEFINITIONS;
}
