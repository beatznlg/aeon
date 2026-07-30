"use client";

import { CSSProperties, ReactNode } from "react";

export default function Card({
  title,
  children,
  className = "",
  style,
}: {
  title?: string;
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <div
      className={`rounded-aeon border border-aeon-border bg-aeon-bg-1 p-5 shadow-aeon transition-all ${className}`}
      style={style}
    >
      {title && (
        <h3 className="mb-4 text-sm font-semibold uppercase tracking-wide text-aeon-fg-mute">
          {title}
        </h3>
      )}
      {children}
    </div>
  );
}
