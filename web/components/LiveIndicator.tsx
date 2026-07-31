"use client";

import { motion } from "framer-motion";
import { useSectorDataContext } from "./SectorDashboardProvider";

/**
 * LiveIndicator
 * =============
 * Shows a pulsing green dot, animated countdown progress bar, status text,
 * and a manual refresh button.
 */
export function LiveIndicator() {
  const { isLive, nextRefreshIn, lastRefreshed, loading, refresh } = useSectorDataContext();

  const REFRESH_INTERVAL_MS = 30_000;
  const progressPct = isLive ? (nextRefreshIn / REFRESH_INTERVAL_MS) * 100 : 0;
  const secondsLeft = Math.ceil(nextRefreshIn / 1000);

  return (
    <motion.div
      className="live-indicator-row"
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <motion.div
        className="live-indicator"
        title={lastRefreshed ? `Last refreshed: ${lastRefreshed.toLocaleTimeString()}` : undefined}
      >
        {/* ── Pulsing dot ── */}
        <span className="live-dot-container" aria-label={isLive ? "Live" : "Connecting"}>
          <span className={`live-dot ${isLive ? "live" : "connecting"}`} />
          <span className={`live-dot-ring ${isLive ? "live" : "connecting"}`} />
        </span>

        {/* ── Status text ── */}
        <span className="live-text">
          {loading ? (
            "Refreshing..."
          ) : isLive ? (
            <>
              <strong className="live-status-label">Live</strong>
              <span className="live-countdown">
                — next refresh in <strong>{secondsLeft}s</strong>
              </span>
            </>
          ) : (
            "Connecting..."
          )}
        </span>

        {/* ── Countdown progress bar ── */}
        <span className="live-bar-track">
          <motion.span
            className="live-bar-fill"
            initial={false}
            animate={{ width: `${progressPct}%` }}
            transition={{ duration: 0.3, ease: "linear" }}
          />
        </span>
      </motion.div>

      {/* ── Manual Refresh Button ── */}
      <motion.button
        className="live-refresh-btn"
        onClick={refresh}
        disabled={loading}
        title="Refresh data now"
        whileTap={{ scale: 0.92 }}
        whileHover={{ scale: 1.05 }}
        transition={{ type: "spring", stiffness: 400, damping: 15 }}
      >
        <motion.span
          className="live-refresh-icon"
          animate={loading ? { rotate: 360 } : { rotate: 0 }}
          transition={
            loading ? { repeat: Infinity, duration: 0.8, ease: "linear" } : { duration: 0.3 }
          }
        >
          ↻
        </motion.span>
        <span className="live-refresh-label">Refresh</span>
      </motion.button>
    </motion.div>
  );
}

/**
 * LiveIndicatorBar — A standalone version for use outside SectorDataContext.
 */
export function LiveIndicatorBar({
  isLive,
  nextRefreshIn,
  lastRefreshed,
  loading,
  onRefresh,
}: {
  isLive: boolean;
  nextRefreshIn: number;
  lastRefreshed: Date | null;
  loading: boolean;
  onRefresh?: () => void;
}) {
  const REFRESH_INTERVAL_MS = 30_000;
  const progressPct = isLive ? (nextRefreshIn / REFRESH_INTERVAL_MS) * 100 : 0;
  const secondsLeft = Math.ceil(nextRefreshIn / 1000);

  return (
    <div className="live-indicator-row">
      <div
        className="live-indicator"
        title={lastRefreshed ? `Last refreshed: ${lastRefreshed.toLocaleTimeString()}` : undefined}
      >
        <span className="live-dot-container" aria-label={isLive ? "Live" : "Connecting"}>
          <span className={`live-dot ${isLive ? "live" : "connecting"}`} />
          <span className={`live-dot-ring ${isLive ? "live" : "connecting"}`} />
        </span>
        <span className="live-text">
          {loading ? (
            "Refreshing..."
          ) : isLive ? (
            <>
              <strong className="live-status-label">Live</strong>
              <span className="live-countdown">
                — next refresh in <strong>{secondsLeft}s</strong>
              </span>
            </>
          ) : (
            "Connecting..."
          )}
        </span>
        <span className="live-bar-track">
          <span className="live-bar-fill" style={{ width: `${progressPct}%` }} />
        </span>
      </div>
      {onRefresh && (
        <button
          className="live-refresh-btn"
          onClick={onRefresh}
          disabled={loading}
          title="Refresh data now"
        >
          <span className={`live-refresh-icon ${loading ? "spinning" : ""}`}>↻</span>
          <span className="live-refresh-label">Refresh</span>
        </button>
      )}
    </div>
  );
}
