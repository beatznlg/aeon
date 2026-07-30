"use client";

import { ReactNode } from "react";

export interface TabItem {
  id: string;
  label: ReactNode;
  icon?: ReactNode;
}

interface TabsProps {
  tabs: TabItem[];
  active: string;
  onChange: (id: string) => void;
  className?: string;
}

export default function Tabs({ tabs, active, onChange, className = "" }: TabsProps) {
  return (
    <div className={`flex w-fit gap-1 rounded-aeon-sm border border-aeon-border bg-aeon-bg p-1 ${className}`}>
      {tabs.map((tab) => {
        const isActive = tab.id === active;
        return (
          <button
            key={tab.id}
            onClick={() => onChange(tab.id)}
            className={`flex items-center gap-2 rounded-aeon-sm px-4 py-2 text-sm font-medium transition-all ${
              isActive
                ? "bg-aeon-primary text-white shadow-sm"
                : "text-aeon-fg-soft hover:bg-aeon-bg-1 hover:text-aeon-fg"
            }`}
          >
            {tab.icon}
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
