"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Link from "next/link";

// ─── Types ───────────────────────────────────────────────────────────────────

interface SearchResult {
  sectorId: string;
  sectorName: string;
  sectorIcon: string;
  toolPath: string;
  toolLabel: string;
  matchField: string;
  matchValue: string;
}

// ─── Color map by sector ─────────────────────────────────────────────────────

const SECTOR_COLORS: Record<string, string> = {
  cybersecurity: "#ef4444",
  health: "#10b981",
  finance: "#f59e0b",
  retail: "#a855f7",
  transport: "#3b82f6",
  manufacturing: "#f97316",
  tourism: "#ec4899",
  utilities: "#06b6d4",
  cultural_heritage: "#14b8a6",
  sme: "#6366f1",
  professional: "#8b5cf6",
};

// ─── Search Result Card ──────────────────────────────────────────────────────

function ResultCard({ result, onSelect }: { result: SearchResult; onSelect: () => void }) {
  const color = SECTOR_COLORS[result.sectorId] || "#6366f1";

  return (
    <motion.div
      className="sector-search-result"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -4 }}
      transition={{ type: "spring", stiffness: 300, damping: 25 }}
    >
      <Link
        href={`/os/${result.sectorId}`}
        className="sector-search-result-link"
        onClick={onSelect}
        style={{ textDecoration: "none" }}
      >
        <div className="sector-search-result-header">
          <span
            className="sector-search-sector-badge"
            style={{ background: `${color}18`, color, borderColor: color }}
          >
            {result.sectorIcon} {result.sectorName}
          </span>
          <span className="sector-search-tool-label">{result.toolLabel}</span>
        </div>
        <div className="sector-search-match">
          <span className="sector-search-field">{result.matchField.replace(/_/g, " ")}:</span>
          <span className="sector-search-value">{result.matchValue}</span>
        </div>
      </Link>
    </motion.div>
  );
}

// ─── Main Search Component ───────────────────────────────────────────────────

interface CrossSectorSearchProps {
  /** Optional className for positioning */
  className?: string;
  /** Placeholder text */
  placeholder?: string;
  /** Auto-focus the input on mount */
  autoFocus?: boolean;
}

export default function CrossSectorSearch({
  className = "",
  placeholder = "Search across all 40+ sector tools...",
  autoFocus = false,
}: CrossSectorSearchProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [totalResults, setTotalResults] = useState(0);
  const [showPanel, setShowPanel] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const panelRef = useRef<HTMLDivElement | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [selectedIndex, setSelectedIndex] = useState(-1);

  // Keyboard shortcut: Cmd/Ctrl + K to focus search
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        inputRef.current?.focus();
        setShowPanel(true);
      }
      if (e.key === "Escape") {
        setShowPanel(false);
        inputRef.current?.blur();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  // Debounced search
  const doSearch = useCallback(async (q: string) => {
    if (!q.trim()) {
      setResults([]);
      setSearched(false);
      setLoading(false);
      return;
    }

    setLoading(true);
    setSearched(true);

    try {
      const res = await fetch(`/api/sector/search?q=${encodeURIComponent(q)}&limit=20`);
      const data = await res.json();
      if (data.ok) {
        setResults(data.results || []);
        setTotalResults(data.totalResults || 0);
      }
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (query.trim()) {
      debounceRef.current = setTimeout(() => doSearch(query), 250);
    } else {
      setResults([]);
      setSearched(false);
      setTotalResults(0);
    }
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query, doSearch]);

  // Close on click outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (
        panelRef.current &&
        !panelRef.current.contains(e.target as Node) &&
        inputRef.current &&
        !inputRef.current.contains(e.target as Node)
      ) {
        setShowPanel(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // Keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((i) => Math.max(i - 1, -1));
    } else if (e.key === "Enter" && selectedIndex >= 0 && results[selectedIndex]) {
      window.location.href = `/os/${results[selectedIndex].sectorId}`;
    }
  };

  const handleSelect = () => {
    setShowPanel(false);
    setQuery("");
    setResults([]);
  };

  return (
    <div className={`sector-search-wrapper ${className}`} ref={panelRef}>
      {/* ── Search Bar ── */}
      <div className={`sector-search-bar ${showPanel && query ? "active" : ""}`}>
        <span className="sector-search-icon">
          {loading ? (
            <motion.span
              animate={{ rotate: 360 }}
              transition={{ repeat: Infinity, duration: 0.8, ease: "linear" }}
            >
              ↻
            </motion.span>
          ) : (
            "🔍"
          )}
        </span>
        <input
          ref={inputRef}
          type="text"
          className="sector-search-input"
          placeholder={placeholder}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setShowPanel(true);
            setSelectedIndex(-1);
          }}
          onFocus={() => setShowPanel(true)}
          onKeyDown={handleKeyDown}
        />
        <span className="sector-search-shortcut">{autoFocus ? "" : "⌘K"}</span>
        {query && (
          <button
            className="sector-search-clear"
            onClick={() => {
              setQuery("");
              setResults([]);
              setSearched(false);
            }}
          >
            ✕
          </button>
        )}
      </div>

      {/* ── Results Panel ── */}
      <AnimatePresence>
        {showPanel && (query || loading) && (
          <motion.div
            className="sector-search-panel"
            initial={{ opacity: 0, y: -8, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.98 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
          >
            {/* Loading skeleton */}
            {loading && (
              <div className="sector-search-loading">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="sector-search-skeleton">
                    <div
                      className="skeleton-shimmer"
                      style={{ height: "0.7rem", width: "30%", marginBottom: "0.5rem" }}
                    />
                    <div className="skeleton-shimmer" style={{ height: "0.6rem", width: "80%" }} />
                  </div>
                ))}
              </div>
            )}

            {/* Results */}
            {!loading && searched && (
              <>
                {results.length > 0 ? (
                  <>
                    <div className="sector-search-panel-header">
                      Found <strong>{totalResults}</strong> match{totalResults !== 1 ? "es" : ""}{" "}
                      across <strong>{new Set(results.map((r) => r.sectorId)).size}</strong> sectors
                    </div>
                    <div className="sector-search-results">
                      {results.map((r, i) => (
                        <div
                          key={`${r.sectorId}-${r.toolPath}-${i}`}
                          className={i === selectedIndex ? "selected" : ""}
                          style={
                            i === selectedIndex ? { background: "var(--aeon-bg-2)" } : undefined
                          }
                        >
                          <ResultCard result={r} onSelect={handleSelect} />
                        </div>
                      ))}
                    </div>
                  </>
                ) : (
                  <div className="sector-search-empty">
                    <span className="sector-search-empty-icon">🔍</span>
                    <p>
                      No results found for <strong>&quot;{query}&quot;</strong>
                    </p>
                    <p className="sector-search-empty-hint">
                      Try a different search term or browse a sector directly
                    </p>
                  </div>
                )}
              </>
            )}

            {/* Hint when empty */}
            {!loading && !searched && !query && (
              <div className="sector-search-empty">
                <p className="sector-search-empty-hint">
                  Type to search across all 40+ sector tools
                </p>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
