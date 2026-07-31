"use client";

import { createContext, useContext, ReactNode } from "react";

interface SidebarContextValue {
  close: () => void;
}

const SidebarContext = createContext<SidebarContextValue>({ close: () => {} });

export function SidebarProvider({ children, close }: { children: ReactNode; close: () => void }) {
  return <SidebarContext.Provider value={{ close }}>{children}</SidebarContext.Provider>;
}

export function useSidebar() {
  return useContext(SidebarContext);
}
