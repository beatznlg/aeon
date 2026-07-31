"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ALL_NAV_LINKS, NavItem } from "@/lib/nav";
import "@/app/command-palette.css";

interface SearchResult {
  id: string;
  type: string;
  title: string;
  subtitle?: string;
  href?: string;
  icon?: string;
  metadata?: Record<string, any>;
}

const STATIC_ICONS: Record<string, string> = {
  nav: "⌘",
  workspace: "🏢",
  user: "👤",
  audit_log: "📋",
  connector: "🔗",
  knowledge: "📚",
  notification: "🔔",
};

function useDebounce<T>(value: T, delay = 200) {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timeout = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timeout);
  }, [value, delay]);

  return debounced;
}

export default function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // Static navigation matches (client-side)
  const staticResults = useMemo<SearchResult[]>(() => {
    if (!query.trim()) return [];
    const q = query.trim().toLowerCase();
    return ALL_NAV_LINKS.filter(
      (item) => item.label.toLowerCase().includes(q) || item.section.toLowerCase().includes(q)
    ).map((item) => ({
      id: `nav-${item.href}`,
      type: "nav",
      title: item.label,
      subtitle: `Navigation · ${item.section}`,
      href: item.href,
      icon: item.icon,
    }));
  }, [query]);

  const debouncedQuery = useDebounce(query, 250);

  useEffect(() => {
    if (!debouncedQuery.trim()) {
      setResults([]);
      return;
    }

    const fetchResults = async () => {
      setLoading(true);
      try {
        const res = await fetch(`/api/search?q=${encodeURIComponent(debouncedQuery)}&limit=20`, {
          cache: "no-store",
        });
        const data = await res.json();
        if (data.ok) {
          setResults(data.results || []);
        }
      } catch (e) {
        console.error("Search failed:", e);
      } finally {
        setLoading(false);
      }
    };

    fetchResults();
  }, [debouncedQuery]);

  // Combine static + dynamic results
  const allResults: SearchResult[] = useMemo(() => {
    const merged = [...staticResults, ...results];
    const seen = new Set<string>();
    return merged.filter((item) => {
      if (seen.has(`${item.type}-${item.id}`)) return false;
      seen.add(`${item.type}-${item.id}`);
      return true;
    });
  }, [staticResults, results]);

  // Keyboard shortcut: Cmd+K / Ctrl+K
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
      if (e.key === "Escape") {
        setOpen(false);
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Reset selection when results change
  useEffect(() => {
    setSelectedIndex(0);
  }, [allResults]);

  // Focus input when opened
  useEffect(() => {
    if (open && inputRef.current) {
      inputRef.current.focus();
      setSelectedIndex(0);
    }
  }, [open]);

  const navigateTo = useCallback(
    (href?: string) => {
      if (!href) return;
      setOpen(false);
      router.push(href);
    },
    [router]
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (allResults.length === 0) return;

    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setSelectedIndex((prev) => (prev + 1) % allResults.length);
        break;
      case "ArrowUp":
        e.preventDefault();
        setSelectedIndex((prev) => (prev - 1 + allResults.length) % allResults.length);
        break;
      case "Enter":
        e.preventDefault();
        navigateTo(allResults[selectedIndex]?.href);
        break;
      case "Escape":
        e.preventDefault();
        setOpen(false);
        break;
    }
  };

  // Scroll selected item into view
  useEffect(() => {
    if (!listRef.current) return;
    const selected = listRef.current.querySelector(`[data-index="${selectedIndex}"]`);
    if (selected) {
      selected.scrollIntoView({ block: "nearest" });
    }
  }, [selectedIndex]);

  if (!open) {
    return null;
  }

  return (
    <div className="cmd-palette-overlay" onClick={() => setOpen(false)}>
      <div
        className="cmd-palette-modal"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
      >
        <div className="cmd-palette-header">
          <span className="cmd-palette-search-icon">🔍</span>
          <input
            ref={inputRef}
            type="text"
            className="cmd-palette-input"
            placeholder="Search commands, workspaces, users, knowledge..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            aria-label="Search"
          />
          {query && (
            <button
              className="cmd-palette-clear"
              onClick={() => {
                setQuery("");
                inputRef.current?.focus();
              }}
              aria-label="Clear search"
            >
              ×
            </button>
          )}
        </div>

        <div className="cmd-palette-body" ref={listRef}>
          {query.trim().length < 2 ? (
            <div className="cmd-palette-empty">
              <div className="cmd-palette-empty-title">Type to search</div>
              <p>Search across pages, workspaces, users, knowledge, and notifications.</p>
            </div>
          ) : loading ? (
            <div className="cmd-palette-loading">Searching…</div>
          ) : allResults.length === 0 ? (
            <div className="cmd-palette-empty">
              <div className="cmd-palette-empty-title">No results found</div>
              <p>Try a different keyword or check spelling.</p>
            </div>
          ) : (
            <div className="cmd-palette-results">
              {allResults.map((item, index) => {
                const Icon = item.icon || STATIC_ICONS[item.type] || "•";
                return (
                  <div
                    key={`${item.type}-${item.id}`}
                    data-index={index}
                    className={`cmd-palette-item ${index === selectedIndex ? "selected" : ""}`}
                    onClick={() => navigateTo(item.href)}
                    onMouseEnter={() => setSelectedIndex(index)}
                  >
                    <span className="cmd-palette-item-icon">{Icon}</span>
                    <div className="cmd-palette-item-body">
                      <div className="cmd-palette-item-title">{item.title}</div>
                      {item.subtitle && (
                        <div className="cmd-palette-item-subtitle">{item.subtitle}</div>
                      )}
                    </div>
                    <span className="cmd-palette-item-type">{item.type}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="cmd-palette-footer">
          <div className="cmd-palette-hints">
            <span>
              <kbd>↑</kbd> <kbd>↓</kbd> Navigate
            </span>
            <span>
              <kbd>↵</kbd> Select
            </span>
            <span>
              <kbd>Esc</kbd> Close
            </span>
          </div>
          <Link href="/os/search" className="cmd-palette-advanced" onClick={() => setOpen(false)}>
            Advanced search →
          </Link>
        </div>
      </div>
    </div>
  );
}
