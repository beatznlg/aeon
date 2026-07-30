"use client";

import { ReactNode } from "react";

type BadgeVariant = "default" | "success" | "warning" | "danger" | "info" | "neutral" | "primary";

interface BadgeProps {
  children: ReactNode;
  variant?: BadgeVariant;
  className?: string;
  title?: string;
}

const variantClasses: Record<BadgeVariant, string> = {
  default: "bg-aeon-primary-soft text-aeon-primary",
  primary: "bg-aeon-primary-soft text-aeon-primary",
  success: "bg-aeon-success-soft text-aeon-success",
  warning: "bg-aeon-warning-soft text-aeon-warning",
  danger: "bg-aeon-danger-soft text-aeon-danger",
  info: "bg-aeon-info-soft text-aeon-info",
  neutral: "bg-aeon-bg-2 text-aeon-fg-soft",
};

export default function Badge({ children, variant = "default", className = "", title }: BadgeProps) {
  return (
    <span
      title={title}
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide ${variantClasses[variant]} ${className}`}
    >
      {children}
    </span>
  );
}
