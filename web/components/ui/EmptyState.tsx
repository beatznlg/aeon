"use client";

import { ReactNode } from "react";

interface EmptyStateProps {
  title?: string;
  description?: string;
  icon?: ReactNode;
  children?: ReactNode;
  className?: string;
}

export default function EmptyState({
  title = "Nothing here yet",
  description,
  icon,
  children,
  className = "",
}: EmptyStateProps) {
  return (
    <div className={`flex flex-col items-center justify-center gap-3 p-8 text-center ${className}`}>
      {icon ? (
        <div className="text-4xl text-aeon-fg-mute">{icon}</div>
      ) : (
        <div className="text-4xl opacity-40">🍃</div>
      )}
      <div className="text-base font-medium text-aeon-fg-soft">{title}</div>
      {description && <p className="max-w-md text-sm text-aeon-fg-mute">{description}</p>}
      {children && <div className="mt-2">{children}</div>}
    </div>
  );
}
