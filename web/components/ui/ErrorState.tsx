"use client";

import { ReactNode } from "react";

interface ErrorStateProps {
  title?: string;
  error?: string | Error | null;
  onRetry?: () => void;
  className?: string;
  children?: ReactNode;
}

export default function ErrorState({ title = "Something went wrong", error, onRetry, className = "", children }: ErrorStateProps) {
  const message = error instanceof Error ? error.message : typeof error === "string" ? error : "An unexpected error occurred.";
  return (
    <div className={`rounded-aeon border border-aeon-danger/30 bg-aeon-danger-soft p-6 text-center ${className}`}>
      <div className="mb-2 text-2xl">⚠️</div>
      <h4 className="mb-1 text-base font-semibold text-aeon-fg">{title}</h4>
      {message && <p className="mb-4 text-sm text-aeon-fg-soft">{message}</p>}
      {children}
      {onRetry && (
        <button onClick={onRetry} className="mt-4 rounded-aeon-sm bg-aeon-danger px-4 py-2 text-sm font-medium text-white hover:bg-red-600">
          Try again
        </button>
      )}
    </div>
  );
}
