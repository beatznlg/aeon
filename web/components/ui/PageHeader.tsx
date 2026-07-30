"use client";

import { ReactNode } from "react";
import Link from "next/link";

interface PageHeaderProps {
  title: ReactNode;
  subtitle?: string;
  actions?: ReactNode;
  backHref?: string;
  backLabel?: string;
  className?: string;
}

export default function PageHeader({ title, subtitle, actions, backHref, backLabel = "← OS Launcher", className = "" }: PageHeaderProps) {
  return (
    <header className={`mb-6 flex flex-col gap-4 md:flex-row md:items-start md:justify-between ${className}`}>
      <div>
        <h1 className="text-2xl font-bold text-gradient">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-aeon-fg-mute">{subtitle}</p>}
      </div>
      <div className="flex flex-wrap items-center gap-3">
        {actions}
        {backHref && (
          <Link
            href={backHref}
            className="inline-flex items-center rounded-aeon-sm border border-aeon-border bg-aeon-bg-1 px-4 py-2 text-sm font-medium text-aeon-fg-soft transition-colors hover:border-aeon-primary/50 hover:text-aeon-fg"
          >
            {backLabel}
          </Link>
        )}
      </div>
    </header>
  );
}
