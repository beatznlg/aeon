export interface NavItem {
  href: string;
  label: string;
  icon: string;
  section: string;
}

export const NAV_ITEMS = [
  {
    section: "Core",
    links: [
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
      { href: "/os/activity", label: "Activity", icon: "" },
      { href: "/os/automations", label: "Automations", icon: "🤖" },
      { href: "/os/approvals", label: "Approvals", icon: "✋" },
    ],
  },
  {
    section: "Modules",
    links: [
      { href: "/os/cybersecurity", label: "Security", icon: "🛡️" },
      { href: "/os/health", label: "Health", icon: "🏥" },
      { href: "/os/finance", label: "Finance", icon: "💰" },
      { href: "/os/retail", label: "Commerce", icon: "📦" },
      { href: "/os/transport", label: "Transport", icon: "🚚" },
      { href: "/os/manufacturing", label: "Manufacturing", icon: "🏭" },
      { href: "/os/tourism", label: "Tourism", icon: "🏨" },
      { href: "/os/cultural_heritage", label: "Cultural", icon: "🎭" },
      { href: "/os/professional", label: "Professional", icon: "" },
      { href: "/os/utilities", label: "Utilities", icon: "⚡" },
      { href: "/os/sme", label: "SME Suite", icon: "🏢" },
    ],
  },
];

export const ALL_NAV_LINKS: NavItem[] = NAV_ITEMS.flatMap((s) =>
  s.links.map((l) => ({ ...l, section: s.section }))
);
