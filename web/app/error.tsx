"use client";

import Link from "next/link";

/**
 * Root error boundary — catches errors in the route tree and shows a
 * themed error UI with retry capability.
 */
export default function RootError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="aeon-page flex items-center justify-center min-h-[80vh]">
      {/* Background effects */}
      <div
        className="fixed inset-0 -z-10 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse at 20% 50%, rgba(239, 68, 68, 0.03) 0%, transparent 60%), radial-gradient(ellipse at 80% 20%, rgba(99, 102, 241, 0.02) 0%, transparent 50%)",
        }}
      />

      <div className="text-center max-w-lg">
        {/* Decorative glyph */}
        <div className="mb-6">
          <div
            className="w-20 h-20 rounded-2xl flex items-center justify-center text-3xl mx-auto"
            style={{
              background: "var(--aeon-danger-soft)",
              color: "var(--aeon-danger)",
              boxShadow: "0 0 40px rgba(239, 68, 68, 0.15)",
            }}
          >
            ⟁
          </div>
        </div>

        {/* Glass card */}
        <div className="glass-card-static p-8 mb-8">
          <h1 className="text-xl font-bold text-aeon-fg mb-2">Something went wrong</h1>
          <p className="text-sm text-aeon-fg-soft leading-relaxed mb-6">
            The AEON OS encountered an unexpected error. This has been logged.
            {error.digest && (
              <span className="block mt-2 text-xs font-mono text-aeon-fg-mute">
                Error ID: {error.digest}
              </span>
            )}
          </p>

          <div className="flex flex-wrap gap-3 justify-center">
            <button onClick={reset} className="pill-btn pill-btn-primary">
              🔄 Try Again
            </button>
            <Link href="/" className="pill-btn">
              ◈ Dashboard
            </Link>
          </div>
        </div>

        {/* Subtle error type hint */}
        <div className="text-xs text-aeon-fg-mute">
          <span
            className="inline-block w-1.5 h-1.5 rounded-full mr-2"
            style={{
              background: "var(--aeon-danger)",
              boxShadow: "0 0 6px rgba(239, 68, 68, 0.5)",
            }}
          />
          {error.name || "RuntimeError"}
        </div>
      </div>
    </div>
  );
}
