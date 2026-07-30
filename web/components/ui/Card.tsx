"use client";

import { CSSProperties, ReactNode } from "react";

interface CardProps {
  title?: ReactNode;
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
  action?: ReactNode;
}

export default function Card({ title, children, className = "", style, action }: CardProps) {
  return (
    <div
      className={`rounded-aeon border border-aeon-border bg-aeon-bg-1 p-5 shadow-aeon transition-all ${className}`}
      style={style}
    >
      {(title || action) && (
        <div className="mb-4 flex items-center justify-between">
          {title && (
            <h3 className="text-sm font-semibold uppercase tracking-wide text-aeon-fg-mute">
              {title}
            </h3>
          )}
          {action && <div className="ml-auto">{action}</div>}
        </div>
      )}
      {children}
    </div>
  );
}
