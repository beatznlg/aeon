"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSidebar } from "./SidebarContext";

interface SidebarLinkProps {
  href: string;
  icon: string;
  label: string;
  muted?: boolean;
}

export default function SidebarLink({ href, icon, label, muted }: SidebarLinkProps) {
  const pathname = usePathname();
  const { close } = useSidebar();

  const isActive = href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <Link
      href={href}
      className={`sidebar-link ${isActive ? "active" : ""} ${muted ? "opacity-60" : ""}`}
      onClick={() => close()}
    >
      <span className="sidebar-link-icon">{icon}</span>
      <span className="sidebar-link-text">{label}</span>
      {muted && <span className="ml-auto text-xs text-aeon-fg-mute">off</span>}
    </Link>
  );
}
