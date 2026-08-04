import { listRegisteredSectors } from "@/lib/sector-registry";

export interface NavItem {
  href: string;
  label: string;
  icon: string;
  section: string;
}

const CORE_LINKS = [
  { href: "/", label: "Dashboard", icon: "◈" },
  { href: "/chat", label: "Chat", icon: "" },
  { href: "/os", label: "OS Modules", icon: "⊞" },
  { href: "/swarms", label: "Swarms", icon: "🐝" },
  { href: "/llm", label: "LLM Brain", icon: "⚡" },
  { href: "/os/api-keys", label: "API Keys", icon: "🔑" },
  { href: "/os/billing", label: "Billing & Plans", icon: "💰" },
  { href: "/os/observability", label: "Observability", icon: "📊" },
  { href: "/os/monitoring", label: "Monitoring", icon: "📈" },
  { href: "/os/knowledge", label: "Knowledge", icon: "📚" },
  { href: "/os/rag-chat", label: "RAG Chat", icon: "🧠" },
  { href: "/os/ai-studio", label: "AI Studio", icon: "🤖" },
  { href: "/os/notifications", label: "Notifications", icon: "🔔" },
  { href: "/os/marketplace", label: "Marketplace", icon: "🏪" },
  { href: "/os/activity", label: "Activity", icon: "" },
  { href: "/os/automations", label: "Automations", icon: "🤖" },
  { href: "/os/automations/executions", label: "Execution History", icon: "" },
  { href: "/os/approvals", label: "Approvals", icon: "✋" },
];

export const NAV_ITEMS = [
  {
    section: "Core",
    links: CORE_LINKS,
  },
  {
    section: "Modules",
    links: listRegisteredSectors().map((sector) => ({
      href: `/os/${sector.id}`,
      label: sector.name,
      icon: sector.icon,
    })),
  },
];

export const ALL_NAV_LINKS: NavItem[] = NAV_ITEMS.flatMap((section) =>
  section.links.map((link) => ({ ...link, section: section.section }))
);
