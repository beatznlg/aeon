"use client";

import { useState } from "react";
import {
  DashboardComponent,
  getAllComponents,
  getComponentsByCategory,
} from "@/lib/dashboard-registry";

/* ─── Props ─── */

interface DashboardEditorProps {
  /** Currently enabled component IDs */
  enabledComponents: string[];
  /** Called when the user toggles a component */
  onChange: (ids: string[]) => void;
  /** Current user role for access-aware UI */
  role?: string;
}

/* ─── Category labels ─── */

const CATEGORY_LABELS: Record<string, string> = {
  core: "Core Dashboard",
  security: "Security & Operations",
  modules: "Industry Modules",
  platform: "Platform & Features",
};

/* ─── Component ─── */

export default function DashboardEditor({
  enabledComponents,
  onChange,
  role,
}: DashboardEditorProps) {
  const [filter, setFilter] = useState<string | null>(null);
  const all = getAllComponents();
  const categories = ["core", "security", "modules", "platform"] as const;
  const isAdmin = role === "ADMIN" || role === "SUPER_ADMIN";

  const toggle = (id: string) => {
    const next = enabledComponents.includes(id)
      ? enabledComponents.filter((c) => c !== id)
      : [...enabledComponents, id];
    onChange(next);
  };

  const enableAll = () => onChange(all.map((c) => c.id));
  const disableAll = () => onChange([]);

  const filtered = filter
    ? all.filter((c) => c.category === filter)
    : all;

  return (
    <div>
      <div className="flex items-center justify-between flex-wrap gap-3 mb-4">
        <div className="flex items-center gap-2">
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setFilter(filter === cat ? null : cat)}
              className={`pill-btn text-xs ${filter === cat ? "pill-btn-primary" : ""}`}
            >
              {CATEGORY_LABELS[cat]}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <button onClick={enableAll} className="pill-btn text-xs">
            Enable All
          </button>
          <button onClick={disableAll} className="pill-btn text-xs">
            Disable All
          </button>
        </div>
      </div>

      {filtered.length === 0 && (
        <div className="text-sm text-aeon-fg-mute py-4 text-center">
          No components in this category.
        </div>
      )}

      {categories.map(
        (cat) =>
          (!filter || filter === cat) && (
            <div key={cat} className="mb-4">
              {!filter && (
                <div className="text-xs font-semibold uppercase tracking-wider text-aeon-fg-mute mb-2">
                  {CATEGORY_LABELS[cat]}
                </div>
              )}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                {all
                  .filter((c) => c.category === cat)
                  .filter((c) => !filter || c.id === "placeholder")
                  .map((comp) => {
                    const enabled = enabledComponents.includes(comp.id);
                    const accessDenied =
                      comp.minRole === "admin" && !isAdmin;
                    return (
                      <label
                        key={comp.id}
                        className={`
                          flex items-start gap-3 p-3 rounded-xl cursor-pointer
                          transition-all duration-200
                          border
                          ${
                            enabled
                              ? "border-aeon-primary/30 bg-aeon-primary/5"
                              : "border-aeon-border bg-transparent hover:border-aeon-border-strong"
                          }
                          ${accessDenied ? "opacity-40 cursor-not-allowed" : ""}
                        `}
                      >
                        <input
                          type="checkbox"
                          checked={enabled}
                          onChange={() => !accessDenied && toggle(comp.id)}
                          disabled={accessDenied}
                          className="mt-0.5 accent-[var(--aeon-primary)]"
                        />
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <span className="text-sm">{comp.icon}</span>
                            <span className="text-sm font-medium text-aeon-fg">
                              {comp.label}
                            </span>
                          </div>
                          <div className="text-xs text-aeon-fg-mute mt-0.5">
                            {comp.description}
                          </div>
                          <div className="flex items-center gap-2 mt-1">
                            <span
                              className={`inline-flex items-center rounded-full px-1.5 py-0.5 text-[0.6rem] font-semibold uppercase tracking-wider ${
                                comp.minRole === "admin"
                                  ? "bg-amber-400/10 text-amber-400"
                                  : comp.minRole === "operator"
                                  ? "bg-blue-400/10 text-blue-400"
                                  : "bg-green-400/10 text-green-400"
                              }`}
                            >
                              {comp.minRole}
                            </span>
                            {accessDenied && (
                              <span className="text-[0.6rem] text-aeon-fg-mute">
                                Admin only
                              </span>
                            )}
                          </div>
                        </div>
                      </label>
                    );
                  })}
              </div>
            </div>
          )
      )}
    </div>
  );
}
