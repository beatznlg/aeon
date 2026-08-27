/**
 * AEON OS — Industry Presets
 * ===========================
 * One-click onboarding profiles. Each preset configures the workspace for a
 * vertical: suggested branding plus the set of modules/command centers that
 * should be enabled. New accounts pick a preset during onboarding and can
 * fine-tune later from Settings → Branding.
 */

export interface IndustryPreset {
  id: string;
  name: string;
  icon: string;
  color: string;
  description: string;
  /** Suggested company name used in the demo/onboarding branding. */
  companyName: string;
  /** Suggested product name shown in the UI chrome. */
  productName: string;
  tagline: string;
  primaryColor: string;
  /** Module IDs (from theme-config) to enable for this industry. */
  moduleIds: string[];
}

/** Modules every workspace keeps on regardless of industry. */
export const CORE_MODULE_IDS = [
  "dashboard",
  "chat",
  "os",
  "automations",
  "swarms",
  "llm",
  "apiKeys",
  "billing",
  "observability",
  "monitoring",
  "knowledge",
  "ragChat",
  "aiStudio",
  "notifications",
  "activity",
  "integrations",
  "governance",
];

/** Always-on security & operations modules. */
export const SECURITY_MODULE_IDS = [
  "security",
  "anomalies",
  "incidents",
  "dr",
  "cybersecurity",
];

const preset = (
  id: string,
  name: string,
  icon: string,
  color: string,
  description: string,
  companyName: string,
  tagline: string,
  primaryColor: string,
  moduleIds: string[]
): IndustryPreset => ({
  id,
  name,
  icon,
  color,
  description,
  companyName,
  productName: `${companyName} Command`,
  tagline,
  primaryColor,
  moduleIds: Array.from(new Set([...CORE_MODULE_IDS, ...SECURITY_MODULE_IDS, ...moduleIds])),
});

export const INDUSTRY_PRESETS: IndustryPreset[] = [
  preset(
    "cybersecurity",
    "Cybersecurity & Defense",
    "🛡️",
    "#ef4444",
    "Threat intelligence, vulnerability scanning, compliance posture, and incident response for security operations centers.",
    "Sentinel Defense",
    "Mission-Critical Cyber Operations",
    "#ef4444",
    []
  ),
  preset(
    "health",
    "Healthcare",
    "🏥",
    "#06b6d4",
    "AI diagnostics, patient monitoring, drug interaction checks, and telehealth triage for modern care teams.",
    "Meridian Health",
    "Intelligent Patient Care",
    "#06b6d4",
    ["health"]
  ),
  preset(
    "finance",
    "Finance & Banking",
    "💰",
    "#f59e0b",
    "Risk analysis, market forecasting, fraud detection, credit scoring, and payment monitoring.",
    "Atlas Capital",
    "Risk-Aware Financial Intelligence",
    "#f59e0b",
    ["finance"]
  ),
  preset(
    "retail",
    "Retail & E-commerce",
    "📦",
    "#10b981",
    "Demand forecasting, inventory optimization, supplier risk, and dynamic pricing for commerce teams.",
    "Nova Retail",
    "Smarter Commerce, Less Waste",
    "#10b981",
    ["retail"]
  ),
  preset(
    "transport",
    "Transport & Logistics",
    "🚚",
    "#3b82f6",
    "Traffic management, fleet scheduling, route optimization, and supply-chain visibility.",
    "Vector Logistics",
    "On-Time, Every Time",
    "#3b82f6",
    ["transport"]
  ),
  preset(
    "manufacturing",
    "Manufacturing & Energy",
    "🏭",
    "#f97316",
    "Predictive maintenance, quality-control vision, smart logistics, and plant-floor intelligence.",
    "ForgeWorks Industries",
    "Zero-Downtime Production",
    "#f97316",
    ["manufacturing", "utilities"]
  ),
  preset(
    "tourism",
    "Tourism & Hospitality",
    "🏨",
    "#ec4899",
    "Booking optimization, dynamic pricing, and automated guest concierge for hotels and destinations.",
    "Crestline Hospitality",
    "Five-Star Guest Intelligence",
    "#ec4899",
    ["tourism"]
  ),
  preset(
    "cultural_heritage",
    "Cultural Heritage & Arts",
    "🏛️",
    "#8b5cf6",
    "Visitor engagement, exhibition planning, collections analytics, and virtual tours.",
    "Heritage Collective",
    "Bringing Culture to Life",
    "#8b5cf6",
    ["cultural_heritage"]
  ),
  preset(
    "professional",
    "Professional Services",
    "📄",
    "#6366f1",
    "Legal document parsing, smart accounting, client data management, and professional operations.",
    "Northbridge Advisory",
    "Expert Intelligence, Delivered",
    "#6366f1",
    ["professional"]
  ),
  preset(
    "utilities",
    "Utilities & Energy",
    "⚡",
    "#22c55e",
    "Grid monitoring, outage prediction, energy forecasting, and infrastructure maintenance.",
    "PeakGrid Energy",
    "Reliable Power, Intelligent Grid",
    "#22c55e",
    ["utilities"]
  ),
  preset(
    "sme",
    "SME Business Suite",
    "🏢",
    "#14b8a6",
    "An all-in-one AI suite for small and medium businesses: operations, finance, commerce, and growth.",
    "Apex Business Suite",
    "Enterprise Power for Growing Teams",
    "#14b8a6",
    ["sme", "retail", "finance", "professional"]
  ),
  preset(
    "government",
    "Government & Public Sector",
    "🏛️",
    "#0ea5e9",
    "Secure, auditable AI operations for agencies: compliance, governance, incident response, and citizen services.",
    "Civic Operations",
    "Secure, Accountable Public Service",
    "#0ea5e9",
    ["governance", "cybersecurity", "professional"]
  ),
  preset(
    "legal",
    "Legal Services",
    "⚖️",
    "#a16207",
    "Case-law research, contract review drafting, clause comparison, and discovery summarization with citation grounding.",
    "Lexbridge Counsel",
    "Grounded Legal Intelligence",
    "#a16207",
    ["professional", "governance"]
  ),
  preset(
    "insurance",
    "Insurance & Underwriting",
    "☂️",
    "#0d9488",
    "Claims triage, fraud-signal review, risk scoring, and policy Q&A with human-in-the-loop underwriting controls.",
    "Meridian Assurance",
    "Faster Claims, Safer Underwriting",
    "#0d9488",
    ["finance", "professional"]
  ),
  preset(
    "construction",
    "Construction & Engineering",
    "🏗️",
    "#d97706",
    "Schedule-risk analysis, cost-estimate drafting, RFP summarization, and bid scoring for project-driven firms.",
    "Keystone Build",
    "On-Budget, On-Schedule Intelligence",
    "#d97706",
    ["manufacturing", "professional"]
  ),
  preset(
    "real_estate",
    "Real Estate & Property",
    "🏘️",
    "#7c3aed",
    "Valuation analysis, comparables reports, market analytics, and portfolio review grounded in verified data.",
    "Cornerstone Estates",
    "Data-Driven Property Decisions",
    "#7c3aed",
    ["retail", "professional"]
  ),
];

export function getIndustryPreset(id: string): IndustryPreset | undefined {
  return INDUSTRY_PRESETS.find((p) => p.id === id);
}
