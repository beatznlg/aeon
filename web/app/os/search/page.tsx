"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import "@/app/command-palette.css";

interface SearchResult {
  id: string;
  type: string;
  title: string;
  subtitle?: string;
  href?: string;
  icon?: string;
}

const TYPE_ICONS: Record<string, string> = {
  nav: "⌘",
  workspace: "🏢",
  user: "👤",
  audit_log: "📋",
  connector: "🔗",
  knowledge: "📚",
  notification: "🔔",
};

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const performSearch = useCallback(async (term: string) => {
    if (!term.trim() || term.trim().length < 2) {
      setResults([]);
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`/api/search?q=${encodeURIComponent(term)}&limit=50`, {
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
  }, []);

  useEffect(() => {
    const timeout = setTimeout(() => performSearch(query), 250);
    return () => clearTimeout(timeout);
  }, [query, performSearch]);

  const grouped = results.reduce<Record<string, SearchResult[]>>((acc, item) => {
    acc[item.type] = acc[item.type] || [];
    acc[item.type].push(item);
    return acc;
  }, {});

  return (
    <div className="os-page">
      <header className="os-header">
        <div>
          <h1>🔍 Global Search</h1>
          <p className="dashboard-subtitle">Search across workspaces, users, knowledge, and more</p>
        </div>
      </header>

      <div className="search-page-input-wrap">
        <input
          ref={inputRef}
          type="text"
          className="search-page-input"
          placeholder="Search anything…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      {loading && <div className="search-page-loading">Searching…</div>}

      {!loading && query.trim().length < 2 && (
        <div className="search-page-empty">
          <div className="search-page-empty-title">Start typing to search</div>
          <p>Search across pages, workspaces, users, knowledge bases, and notifications.</p>
        </div>
      )}

      {!loading && query.trim().length >= 2 && results.length === 0 && (
        <div className="search-page-empty">
          <div className="search-page-empty-title">No results found</div>
          <p>Try a different keyword or check spelling.</p>
        </div>
      )}

      {Object.keys(grouped).length > 0 && (
        <div className="search-page-results">
          {Object.entries(grouped).map(([type, items]) => (
            <section key={type} className="search-page-section">
              <h3 className="search-page-section-title">
                {TYPE_ICONS[type] || "•"} {type.replace("_", " ")}
              </h3>
              <div className="search-page-list">
                {items.map((item) => (
                  <Link
                    key={`${type}-${item.id}`}
                    href={item.href || "#"}
                    className="search-page-item"
                  >
                    <span className="search-page-item-icon">{item.icon || TYPE_ICONS[type] || "•"}</span>
                    <div className="search-page-item-body">
                      <div className="search-page-item-title">{item.title}</div>
                      {item.subtitle && (
                        <div className="search-page-item-subtitle">{item.subtitle}</div>
                      )}
                    </div>
                  </Link>
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
