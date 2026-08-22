import { ReactNode } from "react";
import AeonLogo from "./AeonLogo";
import HealthStatus from "./HealthStatus";
import SidebarLink from "./SidebarLink";
import {
  getThemeConfig,
  mergeThemeConfig,
  ThemeConfig,
  isWorkspaceAdmin,
  isModuleEnabled,
} from "@/lib/theme-config";
import { listRegisteredSectors } from "@/lib/sector-registry";

interface Health {
  ok: boolean;
  backend?: string;
}

interface AppSidebarProps {
  health?: Health | null;
  branding?: Partial<ThemeConfig>;
  userRole?: string;
}

interface SidebarLinkDef {
  href: string;
  label: string;
  icon: string;
  moduleId?: string;
}

const CORE_LINKS: SidebarLinkDef[] = [
  { href: "/", label: "Dashboard", icon: "◈", moduleId: "dashboard" },
  { href: "/showcase", label: "Showcase", icon: "✨", moduleId: "dashboard" },
  { href: "/chat", label: "Chat", icon: "💬", moduleId: "chat" },
  { href: "/os", label: "OS Modules", icon: "⊞", moduleId: "os" },
  { href: "/os/automations/metrics", label: "Automations", icon: "🤖", moduleId: "automations" },
  { href: "/swarms", label: "Swarms", icon: "🐝", moduleId: "swarms" },
  { href: "/llm", label: "LLM Brain", icon: "🧠", moduleId: "llm" },
  { href: "/os/api-keys", label: "API Keys", icon: "🔑", moduleId: "apiKeys" },
  { href: "/os/billing", label: "Billing & Plans", icon: "💳", moduleId: "billing" },
  { href: "/os/observability", label: "Observability", icon: "📊", moduleId: "observability" },
  { href: "/os/monitoring", label: "Monitoring", icon: "📈", moduleId: "monitoring" },
  { href: "/os/knowledge", label: "Knowledge", icon: "📚", moduleId: "knowledge" },
  { href: "/os/rag-chat", label: "RAG Chat", icon: "🧠", moduleId: "ragChat" },
  { href: "/os/ai-studio", label: "AI Studio", icon: "🤖", moduleId: "aiStudio" },
  { href: "/os/notifications", label: "Notifications", icon: "🔔", moduleId: "notifications" },
  { href: "/os/activity", label: "Activity", icon: "📋", moduleId: "activity" },
  { href: "/os/marketplace", label: "Marketplace", icon: "🏪", moduleId: "integrations" },
  { href: "/os/integrations/mcp", label: "MCP Servers", icon: "🔌", moduleId: "integrations" },
  { href: "/os/capabilities", label: "Capabilities", icon: "✦", moduleId: "integrations" },
  { href: "/os/operating-profiles", label: "Operating Profiles", icon: "🧭", moduleId: "operatingProfiles" },
  { href: "/admin/sectors", label: "Sector Admin", icon: "🏢", moduleId: "sectorAdmin" },
];

const MODULE_LINKS: SidebarLinkDef[] = listRegisteredSectors().map((sector) => ({
  href: `/os/${sector.id}`,
  label: sector.name,
  icon: sector.icon,
  moduleId: sector.id,
}));

const SECURITY_LINKS: SidebarLinkDef[] = [
  { href: "/anomalies", label: "Anomalies", icon: "⚠️", moduleId: "security" },
  { href: "/incidents", label: "Incidents", icon: "🚨", moduleId: "security" },
  { href: "/dr", label: "Disaster Recovery", icon: "🛡️", moduleId: "security" },
  { href: "/os/siem", label: "SIEM", icon: "🔍", moduleId: "security" },
];

const ADMIN_LINKS: SidebarLinkDef[] = [
  { href: "/admin", label: "Admin Panel", icon: "⚙️" },
  { href: "/admin/observability", label: "Observability", icon: "🔭" },
];

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="mb-5">
      <div className="px-3 pb-2 text-xs font-semibold uppercase tracking-wider text-aeon-fg-mute">
        {title}
      </div>
      {children}
    </div>
  );
}

function filterLinks(
  links: SidebarLinkDef[],
  config: Partial<ThemeConfig>,
  isAdmin: boolean
): SidebarLinkDef[] {
  return links.filter((link) => {
    if (!link.moduleId) return true;
    const enabled = isModuleEnabled(config, link.moduleId, true);
    if (enabled) return true;
    // Disabled modules are still visible to admins so they can re-enable them.
    return isAdmin;
  });
}

export default function AppSidebar({ health, branding, userRole }: AppSidebarProps) {
  const config = branding ? mergeThemeConfig(branding) : getThemeConfig();
  const admin = isWorkspaceAdmin(userRole);

  const coreLinks = filterLinks(CORE_LINKS, config, admin);
  const moduleLinks = filterLinks(MODULE_LINKS, config, admin);
  const securityLinks = filterLinks(SECURITY_LINKS, config, admin);

  return (
    <>
      <div className="sidebar-header">
        <div className="sidebar-brand">
          <AeonLogo size={36} className="aeon-logo-mark" />
          <div>
            <div className="sidebar-brand-text text-aeon-fg">{config.productName}</div>
            <div className="sidebar-brand-sub text-aeon-fg-mute">{config.tagline}</div>
          </div>
        </div>
        <HealthStatus initial={health} />
      </div>

      <nav className="sidebar-nav">
        <Section title="Core">
          {coreLinks.map((link) => (
            <SidebarLink
              key={link.href}
              href={link.href}
              icon={link.icon}
              label={link.label}
              muted={!isModuleEnabled(config, link.moduleId || "", true) && admin}
            />
          ))}
        </Section>
        <Section title="Modules">
          {moduleLinks.map((link) => (
            <SidebarLink
              key={link.href}
              href={link.href}
              icon={link.icon}
              label={link.label}
              muted={!isModuleEnabled(config, link.moduleId || "", true) && admin}
            />
          ))}
        </Section>
        <Section title="Security & Operations">
          {securityLinks.map((link) => (
            <SidebarLink
              key={link.href}
              href={link.href}
              icon={link.icon}
              label={link.label}
              muted={!isModuleEnabled(config, link.moduleId || "", true) && admin}
            />
          ))}
        </Section>
        {admin && (
          <Section title="Administration">
            {ADMIN_LINKS.map((link) => (
              <SidebarLink key={link.href} href={link.href} icon={link.icon} label={link.label} />
            ))}
          </Section>
        )}
      </nav>
    </>
  );
}
