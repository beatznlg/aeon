/**
 * Sector Tool Data Service
 * =========================
 * Granular API hooks for fetching data from individual sector tool endpoints.
 * Each sector exposes specific tools as dedicated /api/sector/[sector]/[tool] endpoints.
 *
 * Usage:
 *   import { useCybersecurityThreats } from "@/lib/sector-data";
 *   const { data, loading, error } = useCybersecurityThreats();
 */

import { useEffect, useState } from "react";

// ─── Generic fetch with error handling ───────────────────────────────────────

async function fetchSector<T>(path: string): Promise<T> {
  const res = await fetch(`/api/sector/${path}`, { cache: "no-store" });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`Sector API error (${res.status}): ${text}`);
  }
  return res.json() as Promise<T>;
}

// ─── Hook factory ────────────────────────────────────────────────────────────

function useSectorData<T>(path: string) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);

    fetchSector<T>(path)
      .then((result) => {
        if (alive) setData(result);
      })
      .catch((err) => {
        if (alive) setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (alive) setLoading(false);
      });

    return () => {
      alive = false;
    };
  }, [path]);

  return { data, loading, error, refresh: () => { setLoading(true); fetchSector<T>(path).then(setData).catch(setError).finally(() => setLoading(false)); } };
}

// ─── Types ───────────────────────────────────────────────────────────────────

export interface SectorResponse {
  ok: boolean;
}

// Cybersecurity
export interface Threat {
  id: string; indicator: string; type: string; severity: string; status: string;
  first_seen?: string; last_seen?: string;
}
export interface Vulnerability {
  cve: string; severity: string; cvss: number; affected: string; patch_available: boolean; discovered?: string;
}
export interface ComplianceData {
  framework: string; score: number; maturity: string; gaps: string[]; last_assessment?: string;
}
export interface IpReputation {
  score: number; known_malicious: boolean; source_countries: string[]; last_seen_days: number;
}
export interface SecurityNewsItem { title: string; url: string; source?: string; date?: string; }

// Health
export interface Diagnostic {
  analyzed_symptoms: string;
  possible_conditions: { name: string; probability: number; severity: string; action: string }[];
  urgency: string; recommendation: string;
}
export interface Vital {
  patient_id: string; metric: string; baseline: number; current: number; trend: string; alert: boolean;
}
export interface DrugInteraction {
  medications: string[]; interactions_found: number;
  interactions: { drugs: string[]; severity: string; warning: string }[];
}
export interface TelehealthItem { symptoms: string; age: number; urgency: string; recommendation: string; }

// Finance
export interface RiskData {
  asset: string; portfolio_value: number; var_95_1d: number; var_95_pct: number;
  sharpe_estimate: number; beta: number; risk_rating: string; diversification_score: number; recommendation: string;
}
export interface MarketData {
  market: string; predicted_direction: string; confidence: number; price_target_pct: number;
  volatility_forecast: string; key_indicators?: Record<string, unknown>;
}
export interface FraudCase {
  transaction_id: string; amount: number; fraud_score: number; risk_level: string; action: string; timestamp?: string;
}
export interface CreditApp {
  applicant_id: string; credit_score: number; rating: string; approval_probability: number; recommended_limit?: number;
}
export interface PaymentAccount {
  account_id: string; total_transactions: number; total_volume: number; anomaly_count: number; spending_trend: string;
}

// Retail
export interface ForecastItem {
  sku: string; current_stock: number; projected_demand: number;
  recommended_order_qty: number; confidence: number;
}
export interface InventoryData {
  alerts: Array<{ sku: string; status: string; days_remaining: number }>;
  reorder_recommendations: Array<{ sku: string; qty: number; supplier: string; est_delivery_days?: number }>;
  healthy: Array<{ sku: string; status: string; days_supply: number; suggestion?: string }>;
  summary: { total_skus: number; stockout_risks: number; overstocks: number; healthy?: number };
}
export interface SupplierRisk {
  supplier: string; risk_score: number; classification: string;
  on_time_delivery_pct: number; contract_end?: string;
}
export interface PriceElasticity {
  sku: string; price_change_pct: number; elasticity: number;
  projected_demand_change_pct: number; optimal_price?: number; current_price?: number;
}

// Transport
export interface TrafficZone {
  zone: string; current_congestion: number; predicted_improvement: string; incident_nearby: boolean;
}
export interface FleetData {
  depot?: string; vehicles_available: number; shifts: number;
  utilization_pct: number; recommendation: string;
}
export interface RoutePlan {
  stops: string[]; estimated_distance_km: number; estimated_time_min: number;
  fuel_cost_est: number; optimized?: boolean;
}

// Manufacturing
export interface Machine {
  machine_id: string; status: string; temp_c: number; vibration_hz: number;
  failure_risk_pct: number; days_to_failure: number; last_service?: string;
}
export interface QCData {
  batch_id: string; items_scanned: number; defects_found: number;
  defect_rate: number; status: string; root_cause?: string;
}
export interface Shipment {
  route_id: string; status: string; eta_days: number;
  reroute_cost_usd: number; delay_reason?: string;
}

// Tourism
export interface Booking {
  property: string; occupancy_pct: number; predictive_no_shows: number;
  net_expected_occupancy: number; revenue_ytd?: number;
}
export interface PricingRec {
  room: string; base_price: number; recommended_price: number;
  reason: string; demand_level?: string;
}
export interface ConciergeRequest {
  guest_id: string; sentiment: string; intent: string;
  automated_response: string; upsell?: string | null;
}
export interface VenueData {
  venue: string; daily_visitors: number; engagement_score: number;
  recommended_strategies: string[];
}

// Utilities
export interface ResourceData {
  resource: string; demand: number; supply: number; deficit: number;
  status: string; optimization_suggestion?: string;
}
export interface PublicService {
  service: string; kpi_score: number; status: string;
  citizen_satisfaction: number; trend: string;
}
export interface WasteData {
  district: string; total_waste_tons: number; recycled_pct: number;
  landfill_pct: number; collection_efficiency: number;
}
export interface GridRegion {
  region: string; current_load_mw: number; capacity_mw: number;
  utilization_pct: number; renewable_share_pct: number; status: string; action?: string;
}

// Heritage
export interface HeritageSite {
  site: string; era: string; significance: string;
  annual_visitors: number; conservation_status: string;
}
export interface Exhibition {
  theme: string; recommended_duration_days: number; estimated_visitors: number;
  ticket_price: number; projected_revenue: number;
}
export interface VirtualTour {
  site: string; interest: string; narration: string; audio_duration_seconds: number;
}

// SME
export interface WorkflowData {
  process: string; employees_involved: number; hours_saved_per_month: number;
  cost_savings_annual: number; automation_rate?: number;
}
export interface DocumentItem {
  document_type: string; confidence: number; pages_processed: number;
  fields_extracted: string[]; status?: string;
}
export interface SupportTicket {
  query: string; detected_intent: string; sentiment: string;
  response: string; escalated: boolean;
}
export interface SupplyChain {
  chain_id: string; health_score: number; lead_time_days: number;
  risk_level: string; bottlenecks: string[];
}

// ─── Cybersecurity Hooks ─────────────────────────────────────────────────────

export function useCybersecurityThreats() {
  return useSectorData<{ ok: boolean; threats: Threat[]; total?: number }>("cybersecurity/threats");
}
export function useCybersecurityVulnerabilities() {
  return useSectorData<{ ok: boolean; vulnerabilities: Vulnerability[]; scan_summary?: { total: number; critical: number; high: number; medium: number; low: number } }>("cybersecurity/vulnerabilities");
}
export function useCybersecurityCompliance() {
  return useSectorData<{ ok: boolean; compliance: ComplianceData }>("cybersecurity/compliance");
}
export function useCybersecurityIpReputation() {
  return useSectorData<{ ok: boolean; ip_reputation: IpReputation }>("cybersecurity/ip-reputation");
}
export function useCybersecurityNews() {
  return useSectorData<{ ok: boolean; news: SecurityNewsItem[] }>("cybersecurity/news");
}

// ─── Health Hooks ────────────────────────────────────────────────────────────

export function useHealthDiagnostics() {
  return useSectorData<{ ok: boolean; diagnostics: Diagnostic[] }>("health/diagnostics");
}
export function useHealthVitals() {
  return useSectorData<{ ok: boolean; vitals: Vital[] }>("health/vitals");
}
export function useHealthDrugInteractions() {
  return useSectorData<{ ok: boolean; interactions: DrugInteraction[] }>("health/drug-interactions");
}
export function useHealthTelehealth() {
  return useSectorData<{ ok: boolean; triage: TelehealthItem[] }>("health/telehealth");
}

// ─── Finance Hooks ───────────────────────────────────────────────────────────

export function useFinanceRisk() {
  return useSectorData<{ ok: boolean; risk: RiskData }>("finance/risk");
}
export function useFinanceMarket() {
  return useSectorData<{ ok: boolean; market: MarketData }>("finance/market");
}
export function useFinanceFraud() {
  return useSectorData<{ ok: boolean; fraud_cases: FraudCase[] }>("finance/fraud");
}
export function useFinanceCredit() {
  return useSectorData<{ ok: boolean; applications: CreditApp[] }>("finance/credit");
}
export function useFinancePayments() {
  return useSectorData<{ ok: boolean; accounts: PaymentAccount[] }>("finance/payments");
}

// ─── Retail Hooks ────────────────────────────────────────────────────────────

export function useRetailForecast() {
  return useSectorData<{ ok: boolean; forecast: ForecastItem[] }>("retail/forecast");
}
export function useRetailInventory() {
  return useSectorData<{ ok: boolean; inventory: InventoryData }>("retail/inventory");
}
export function useRetailSuppliers() {
  return useSectorData<{ ok: boolean; suppliers: SupplierRisk[] }>("retail/suppliers");
}
export function useRetailPricing() {
  return useSectorData<{ ok: boolean; elasticity: PriceElasticity }>("retail/pricing");
}

// ─── Transport Hooks ─────────────────────────────────────────────────────────

export function useTransportTraffic() {
  return useSectorData<{ ok: boolean; zones: TrafficZone[] }>("transport/traffic");
}
export function useTransportFleet() {
  return useSectorData<{ ok: boolean; fleet: FleetData[] }>("transport/fleet");
}
export function useTransportRoutes() {
  return useSectorData<{ ok: boolean; routes: RoutePlan[] }>("transport/routes");
}

// ─── Manufacturing Hooks ─────────────────────────────────────────────────────

export function useManufacturingMaintenance() {
  return useSectorData<{ ok: boolean; machines: Machine[] }>("manufacturing/maintenance");
}
export function useManufacturingQuality() {
  return useSectorData<{ ok: boolean; batches: QCData[] }>("manufacturing/quality");
}
export function useManufacturingLogistics() {
  return useSectorData<{ ok: boolean; shipments: Shipment[] }>("manufacturing/logistics");
}

// ─── Tourism Hooks ───────────────────────────────────────────────────────────

export function useTourismBookings() {
  return useSectorData<{ ok: boolean; bookings: Booking[] }>("tourism/bookings");
}
export function useTourismPricing() {
  return useSectorData<{ ok: boolean; pricing: PricingRec[] }>("tourism/pricing");
}
export function useTourismConcierge() {
  return useSectorData<{ ok: boolean; requests: ConciergeRequest[] }>("tourism/concierge");
}
export function useTourismVisitors() {
  return useSectorData<{ ok: boolean; venues: VenueData[] }>("tourism/visitors");
}

// ─── Utilities Hooks ─────────────────────────────────────────────────────────

export function useUtilitiesResources() {
  return useSectorData<{ ok: boolean; resources: ResourceData[] }>("utilities/resources");
}
export function useUtilitiesServices() {
  return useSectorData<{ ok: boolean; services: PublicService[] }>("utilities/services");
}
export function useUtilitiesWaste() {
  return useSectorData<{ ok: boolean; districts: WasteData[] }>("utilities/waste");
}
export function useUtilitiesGrid() {
  return useSectorData<{ ok: boolean; regions: GridRegion[] }>("utilities/grid");
}

// ─── Heritage Hooks ──────────────────────────────────────────────────────────

export function useHeritageVisitors() {
  return useSectorData<{ ok: boolean; venues: VenueData[] }>("heritage/visitors");
}
export function useHeritageSites() {
  return useSectorData<{ ok: boolean; sites: HeritageSite[] }>("heritage/sites");
}
export function useHeritageExhibitions() {
  return useSectorData<{ ok: boolean; exhibitions: Exhibition[] }>("heritage/exhibitions");
}
export function useHeritageTours() {
  return useSectorData<{ ok: boolean; tours: VirtualTour[] }>("heritage/tours");
}

// ─── SME Hooks ───────────────────────────────────────────────────────────────

export function useSmeWorkflows() {
  return useSectorData<{ ok: boolean; workflows: WorkflowData[] }>("sme/workflows");
}
export function useSmeDocuments() {
  return useSectorData<{ ok: boolean; documents: DocumentItem[] }>("sme/documents");
}
export function useSmeSupport() {
  return useSectorData<{ ok: boolean; tickets: SupportTicket[] }>("sme/support");
}
export function useSmeSupplyChain() {
  return useSectorData<{ ok: boolean; chains: SupplyChain[] }>("sme/supply-chain");
}

// ─── Response type wrappers for direct fetch callers ─────────────────────────

export type SectorApiResponse<T> = { ok: boolean } & T;

export async function fetchSectorTool<T>(sector: string, tool: string): Promise<SectorApiResponse<T>> {
  return fetchSector<SectorApiResponse<T>>(`${sector}/${tool}`);
}
