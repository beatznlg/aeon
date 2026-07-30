/**
 * Root loading boundary — shown while the server prepares the page shell.
 * Uses the skeleton CSS classes from globals.css.
 */
export default function RootLoading() {
  return (
    <div className="aeon-page">
      <div className="skeleton-page" role="status" aria-label="Loading page">
        <span className="sr-only">Loading AEON OS…</span>

        {/* Welcome banner skeleton */}
        <div
          className="welcome-banner"
          style={{ padding: "1.75rem", marginBottom: "1.5rem" }}
        >
          <div className="flex items-center gap-2 mb-3">
            <div
              className="skeleton-shimmer"
              style={{ width: 8, height: 8, borderRadius: "50%" }}
            />
            <div
              className="skeleton-shimmer"
              style={{ height: "0.7rem", width: 100 }}
            />
          </div>
          <div
            className="skeleton-shimmer"
            style={{ height: "1.5rem", width: "50%", marginBottom: "0.75rem" }}
          />
          <div
            className="skeleton-shimmer"
            style={{ height: "0.8rem", width: "70%" }}
          />
        </div>

        {/* Status bar skeletons */}
        <div className="status-bar mb-6">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="skeleton-card">
              <div
                className="skeleton-shimmer"
                style={{
                  width: "2.25rem",
                  height: "2.25rem",
                  borderRadius: "var(--aeon-radius-sm)",
                  flexShrink: 0,
                }}
              />
              <div className="flex-1 space-y-1.5">
                <div
                  className="skeleton-shimmer"
                  style={{ height: "0.65rem", width: "60%" }}
                />
                <div
                  className="skeleton-shimmer"
                  style={{ height: "1rem", width: "40%" }}
                />
              </div>
            </div>
          ))}
        </div>

        {/* Live metrics grid */}
        <div className="dashboard-grid">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="skeleton-stat">
              <div
                className="skeleton-shimmer"
                style={{
                  height: "1.75rem",
                  width: "40%",
                  borderRadius: "var(--aeon-radius)",
                }}
              />
              <div
                className="skeleton-shimmer"
                style={{ height: "0.7rem", width: "50%" }}
              />
            </div>
          ))}
        </div>

        {/* Module grid skeletons */}
        <div className="mt-8">
          <div className="skeleton-shimmer" style={{ height: "1rem", width: "25%", marginBottom: "1rem" }} />
          <div className="module-grid">
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <div key={i} className="skeleton-card" style={{ flexDirection: "column" }}>
                <div className="flex items-center gap-3">
                  <div
                    className="skeleton-shimmer"
                    style={{
                      width: "2.5rem",
                      height: "2.5rem",
                      borderRadius: "var(--aeon-radius-sm)",
                      flexShrink: 0,
                    }}
                  />
                  <div className="flex-1 space-y-1.5">
                    <div className="skeleton-shimmer" style={{ height: "0.9rem", width: "60%" }} />
                    <div className="skeleton-shimmer" style={{ height: "0.7rem", width: "40%" }} />
                  </div>
                </div>
                <div className="skeleton-shimmer" style={{ height: "0.7rem", width: "85%", marginTop: "0.5rem" }} />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
