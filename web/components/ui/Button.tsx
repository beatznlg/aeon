"use client";

import { ButtonHTMLAttributes, forwardRef } from "react";

type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";
type ButtonSize = "sm" | "md" | "lg";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary: "aeon-btn-primary",
  secondary: "aeon-btn-secondary",
  danger: "aeon-btn-danger",
  ghost: "aeon-btn border-transparent bg-transparent text-aeon-fg-soft hover:bg-aeon-bg-2 hover:text-aeon-fg",
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: "px-3 py-1.5 text-xs",
  md: "px-4 py-2 text-sm",
  lg: "px-6 py-3 text-base",
};

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = "secondary", size = "md", loading = false, leftIcon, rightIcon, children, className = "", disabled, ...props }, ref) => {
    const base = "inline-flex items-center justify-center gap-2 rounded-aeon-sm font-medium transition-all focus:outline-none focus:ring-2 focus:ring-aeon-primary/50 focus:ring-offset-2 focus:ring-offset-aeon-bg disabled:cursor-not-allowed disabled:opacity-50";
    const classes = `${base} ${variantClasses[variant]} ${sizeClasses[size]} ${className}`;
    return (
      <button ref={ref} className={classes} disabled={disabled || loading} {...props}>
        {loading && (
          <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
        )}
        {!loading && leftIcon}
        {children}
        {!loading && rightIcon}
      </button>
    );
  }
);
Button.displayName = "Button";
export default Button;
