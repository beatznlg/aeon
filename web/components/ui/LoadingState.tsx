"use client";

interface LoadingStateProps {
  message?: string;
  className?: string;
}

export default function LoadingState({ message = "Loading…", className = "" }: LoadingStateProps) {
  return (
    <div className={`flex flex-col items-center justify-center gap-3 p-8 text-aeon-fg-mute ${className}`}>
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-aeon-border border-t-aeon-primary" />
      <span className="text-sm">{message}</span>
    </div>
  );
}
