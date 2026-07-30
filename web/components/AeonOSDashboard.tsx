/**
 * AEON OS — Dashboard Components
 *
 * Barrel re-export from individual dashboard files.
 * Import directly from "@/components/dashboards/CyberSecurityDashboard" for new code.
 *
 * @module
 */
"use client";

export {
  KPICard,
  Widget,
  Badge,
  SimpleLineChart,
  DataTable,
  useDashboard,
} from "./dashboards/shared";

export type { KPIData, DashboardData } from "./dashboards/shared";

export { CyberSecurityDashboard } from "./dashboards/CyberSecurityDashboard";
export { HealthDashboard } from "./dashboards/HealthDashboard";
export { FinanceDashboard } from "./dashboards/FinanceDashboard";
export { RetailDashboard } from "./dashboards/RetailDashboard";
export { TransportDashboard } from "./dashboards/TransportDashboard";
export { ManufacturingDashboard } from "./dashboards/ManufacturingDashboard";
export { TourismDashboard } from "./dashboards/TourismDashboard";
export { CulturalHeritageDashboard } from "./dashboards/CulturalHeritageDashboard";
export { UtilitiesDashboard } from "./dashboards/UtilitiesDashboard";
export { SMEDashboard } from "./dashboards/SMEDashboard";
export { ProfessionalDashboard } from "./dashboards/ProfessionalDashboard";
