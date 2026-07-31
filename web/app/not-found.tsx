import Link from "next/link";

export default function NotFound() {
  return (
    <div className="aeon-page flex items-center justify-center min-h-screen">
      {/* Background effects */}
      <div
        className="fixed inset-0 -z-10 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse at 20% 50%, rgba(99, 102, 241, 0.03) 0%, transparent 60%), radial-gradient(ellipse at 80% 20%, rgba(168, 85, 247, 0.02) 0%, transparent 50%)",
        }}
      />

      <div className="text-center max-w-lg">
        {/* Large decorative 404 */}
        <div className="relative mb-8">
          <div
            className="text-[10rem] font-bold leading-none select-none"
            style={{
              background: "linear-gradient(135deg, var(--aeon-primary), #a855f7)",
              WebkitBackgroundClip: "text",
              backgroundClip: "text",
              color: "transparent",
              opacity: 0.15,
              letterSpacing: "-0.04em",
            }}
          >
            404
          </div>

          {/* AEON glyph overlay */}
          <div className="absolute inset-0 flex items-center justify-center">
            <div
              className="w-20 h-20 rounded-2xl flex items-center justify-center text-4xl"
              style={{
                background: "var(--aeon-primary-soft)",
                color: "var(--aeon-primary)",
                boxShadow: "0 0 40px rgba(99, 102, 241, 0.15)",
              }}
            >
              ⟁
            </div>
          </div>
        </div>

        {/* Glass card with message */}
        <div className="glass-card-static p-8 mb-8">
          <h1 className="text-xl font-bold text-aeon-fg mb-3">This dimension doesn&apos;t exist</h1>
          <p className="text-sm text-aeon-fg-soft leading-relaxed mb-6">
            The page you&apos;re looking for has either been moved, never existed, or is orbiting in
            a parallel AEON kernel. Let&apos;s get you back on course.
          </p>

          <div className="flex flex-wrap gap-3 justify-center">
            <Link href="/" className="pill-btn pill-btn-primary">
              ◈ Dashboard
            </Link>
            <Link href="/os" className="pill-btn">
              ⊞ OS Modules
            </Link>
            <Link href="/chat" className="pill-btn">
              💬 Chat
            </Link>
          </div>
        </div>

        {/* Status hint */}
        <div className="text-xs text-aeon-fg-mute space-y-1">
          <div className="flex items-center justify-center gap-2">
            <span
              className="inline-block w-1.5 h-1.5 rounded-full"
              style={{
                background: "var(--aeon-primary)",
                boxShadow: "0 0 6px rgba(99, 102, 241, 0.5)",
              }}
            />
            <span>AEON OS · Route not found</span>
          </div>
        </div>
      </div>
    </div>
  );
}
