"use client";

import { ReactNode } from "react";
import {
  BACKEND_DOWN_MESSAGE,
  BACKEND_DOWN_TITLE,
  isBackendDownError,
} from "@/lib/backend-status";

interface ErrorStateProps {
  title?: string;
  error?: string | Error | null;
  onRetry?: () => void;
  className?: string;
  children?: ReactNode;
}

export default function ErrorState({
  title = "Something went wrong",
  error,
  onRetry,
  className = "",
  children,
}: ErrorStateProps) {
  const message =
    error instanceof Error
      ? error.message
      : typeof error === "string"
        ? error
        : "An unexpected error occurred.";

  const down = isBackendDownError(error);

  return (
    <div
      className={`rounded-aeon border p-6 text-center ${
        down
          ? "border-aeon-warning/40 bg-aeon-warning/10"
          : "border-aeon-danger/30 bg-aeon-danger-soft"
      } ${className}`}
    >
      <div className="mb-2 text-2xl">{down ? "🔌" : "⚠️"}</div>
      <h4
        className={`mb-1 text-base font-semibold ${
          down ? "text-aeon-warning" : "text-aeon-fg"
        }`}
      >
        {down ? BACKEND_DOWN_TITLE : title}
      </h4>
      <p className="mb-4 text-sm text-aeon-fg-soft">
        {down ? BACKEND_DOWN_MESSAGE : message}
      </p>
      {children}
      {onRetry && (
        <button
          onClick={onRetry}
          className={`mt-4 rounded-aeon-sm px-4 py-2 text-sm font-medium text-white ${
            down ? "bg-aeon-warning hover:bg-amber-500" : "bg-aeon-danger hover:bg-red-600"
          }`}
        >
          {down ? "Reconnect" : "Try again"}
        </button>
      )}
    </div>
  );
}
