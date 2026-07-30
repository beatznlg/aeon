"use client";

/**
 * AEON OS — Loading Skeleton Components
 *
 * Use these in place of bare "Loading…" text to give users
 * a polished shimmer-based loading experience that matches
 * the glassmorphism design system.
 */

interface SkeletonProps {
  className?: string;
  /** Number of skeleton lines/blocks to render */
  count?: number;
  /** Optional aria label for screen readers */
  label?: string;
}

/* ─── Base shimmer block ─── */

function SkeletonBlock({ className = "" }: { className?: string }) {
  return (
    <div
      className={`skeleton-shimmer ${className}`}
      aria-hidden="true"
    />
  );
}

/* ─── Variants ─── */

/** A single line of text (e.g. for table cells, labels) */
export function SkeletonText({ className = "" }: { className?: string }) {
  return <SkeletonBlock className={`skeleton-text ${className}`} />;
}

/** A card-shaped skeleton (for dashboard cards, stat cards) */
export function SkeletonCard({ className = "" }: { className?: string }) {
  return (
    <div className={`skeleton-card ${className}`}>
      <SkeletonBlock className="skeleton-card-icon" />
      <div className="flex-1 space-y-2">
        <SkeletonBlock className="skeleton-text w-2/3" />
        <SkeletonBlock className="skeleton-text w-1/3" />
      </div>
    </div>
  );
}

/** A stat/value skeleton (for metric displays) */
export function SkeletonStat({ className = "" }: { className?: string }) {
  return (
    <div className={`skeleton-stat ${className}`}>
      <SkeletonBlock className="skeleton-stat-value" />
      <SkeletonBlock className="skeleton-text w-1/2" />
    </div>
  );
}

/** A table row skeleton */
export function SkeletonTableRow({ columns = 4, className = "" }: { columns?: number; className?: string }) {
  return (
    <div className={`skeleton-table-row ${className}`}>
      {Array.from({ length: columns }).map((_, i) => (
        <SkeletonBlock
          key={i}
          className={`skeleton-text ${i === 0 ? "w-1/3" : "w-1/2"}`}
        />
      ))}
    </div>
  );
}

/** Full page loading state with multiple skeletons */
export function SkeletonPage({
  title = true,
  cards = 6,
  tables = 0,
  className = "",
}: {
  title?: boolean;
  cards?: number;
  tables?: number;
  className?: string;
}) {
  return (
    <div className={`skeleton-page ${className}`} role="status" aria-label="Loading content">
      {/* Screen-reader-only text */}
      <span className="sr-only">Loading, please wait…</span>

      {/* Title */}
      {title && (
        <div className="mb-6 space-y-2">
          <SkeletonBlock className="skeleton-title" />
          <SkeletonBlock className="skeleton-text w-1/2" />
        </div>
      )}

      {/* Cards grid */}
      {cards > 0 && (
        <div className="skeleton-grid" style={{ "--skeleton-cols": Math.min(cards, 4) } as React.CSSProperties}>
          {Array.from({ length: cards }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      )}

      {/* Table rows */}
      {tables > 0 && (
        <div className="mt-6 space-y-2">
          <SkeletonBlock className="skeleton-text w-1/4" />
          {Array.from({ length: tables }).map((_, i) => (
            <SkeletonTableRow key={i} columns={4} />
          ))}
        </div>
      )}
    </div>
  );
}

/** Dashboard-specific skeleton (title + KPI stats + section) */
export function SkeletonDashboard({ className = "" }: { className?: string }) {
  return (
    <div className={className} role="status" aria-label="Loading dashboard">
      <span className="sr-only">Loading dashboard data…</span>
      <div className="mb-6 space-y-2">
        <SkeletonBlock className="skeleton-title" />
        <SkeletonBlock className="skeleton-text w-1/2" />
      </div>
      <div className="dashboard-grid">
        {Array.from({ length: 6 }).map((_, i) => (
          <SkeletonStat key={i} />
        ))}
      </div>
      <div className="mt-6 skeleton-grid" style={{ "--skeleton-cols": 2 } as React.CSSProperties}>
        {Array.from({ length: 2 }).map((_, i) => (
          <div key={i} className="skeleton-card p-4">
            <SkeletonBlock className="skeleton-text w-1/3 mb-3" />
            <SkeletonTableRow columns={3} />
            <SkeletonTableRow columns={3} />
            <SkeletonTableRow columns={3} />
          </div>
        ))}
      </div>
    </div>
  );
}
