/**
 * Admin sectors page loading boundary.
 */
export default function AdminSectorsLoading() {
  return (
    <div className="aeon-page" role="status" aria-label="Loading admin sectors">
      <span className="sr-only">Loading sector admin panel…</span>

      {/* Header */}
      <div className="mb-6 space-y-2">
        <div
          className="skeleton-shimmer"
          style={{ height: "1.5rem", width: 240, borderRadius: "var(--aeon-radius)" }}
        />
        <div className="skeleton-shimmer" style={{ height: "0.8rem", width: 320 }} />
      </div>

      {/* Controls bar */}
      <div className="admin-sectors-controls mb-6">
        <div
          className="skeleton-shimmer"
          style={{ height: "2.4rem", width: 280, borderRadius: "var(--aeon-radius)" }}
        />
        <div
          className="skeleton-shimmer"
          style={{ height: "2.4rem", width: 120, borderRadius: "var(--aeon-radius-sm)" }}
        />
      </div>

      {/* Global stats bar */}
      <div className="status-bar mb-6">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="skeleton-card">
            <div className="flex-1 space-y-1.5">
              <div className="skeleton-shimmer" style={{ height: "0.65rem", width: "50%" }} />
              <div className="skeleton-shimmer" style={{ height: "1.2rem", width: "30%" }} />
            </div>
          </div>
        ))}
      </div>

      {/* Sector cards grid */}
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="skeleton-card"
            style={{ flexDirection: "column", padding: "1.25rem" }}
          >
            <div className="flex items-center gap-3 mb-3">
              <div
                className="skeleton-shimmer"
                style={{
                  width: "2.5rem",
                  height: "2.5rem",
                  borderRadius: "var(--aeon-radius-sm)",
                  flexShrink: 0,
                }}
              />
              <div className="flex-1 space-y-1">
                <div className="skeleton-shimmer" style={{ height: "1rem", width: "40%" }} />
                <div className="skeleton-shimmer" style={{ height: "0.7rem", width: "60%" }} />
              </div>
            </div>
            <div className="flex gap-2">
              {[1, 2, 3, 4].map((j) => (
                <div
                  key={j}
                  className="skeleton-shimmer"
                  style={{
                    height: "1.6rem",
                    width: 100,
                    borderRadius: "var(--aeon-radius-sm)",
                  }}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
