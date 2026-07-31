/**
 * OS page loading boundary.
 */
export default function OSLoading() {
  return (
    <div className="os-page">
      <header className="os-header">
        <div>
          <div
            className="skeleton-shimmer"
            style={{
              height: "1.8rem",
              width: 280,
              borderRadius: "var(--aeon-radius)",
              marginBottom: "0.5rem",
            }}
          />
          <div className="skeleton-shimmer" style={{ height: "0.8rem", width: 360 }} />
        </div>
        <div className="flex gap-3">
          <div
            className="skeleton-shimmer"
            style={{ height: "2.2rem", width: 120, borderRadius: 999 }}
          />
          <div
            className="skeleton-shimmer"
            style={{ height: "2.2rem", width: 100, borderRadius: 999 }}
          />
        </div>
      </header>

      <div className="os-grid" role="status" aria-label="Loading OS modules">
        <span className="sr-only">Loading module launcher…</span>
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <div
            key={i}
            className="skeleton-card"
            style={{
              flexDirection: "column",
              padding: "1.5rem",
              borderTop: "3px solid var(--glass-border)",
            }}
          >
            <div className="flex items-center justify-between mb-3">
              <div
                className="skeleton-shimmer"
                style={{
                  width: "2.5rem",
                  height: "2.5rem",
                  borderRadius: "var(--aeon-radius-sm)",
                }}
              />
              <div
                className="skeleton-shimmer"
                style={{ height: "0.7rem", width: 60, borderRadius: 999 }}
              />
            </div>
            <div
              className="skeleton-shimmer"
              style={{ height: "0.95rem", width: "60%", marginBottom: "0.4rem" }}
            />
            <div
              className="skeleton-shimmer"
              style={{ height: "0.7rem", width: "40%", marginBottom: "0.5rem" }}
            />
            <div className="skeleton-shimmer" style={{ height: "0.7rem", width: "80%" }} />
            <div className="flex gap-2 mt-4">
              <div
                className="skeleton-shimmer"
                style={{ height: "1.8rem", width: 80, borderRadius: "var(--aeon-radius-sm)" }}
              />
              <div
                className="skeleton-shimmer"
                style={{ height: "1.8rem", width: 100, borderRadius: "var(--aeon-radius-sm)" }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
