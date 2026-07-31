import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const revalidate = 0;

/**
 * Deterministic time-varying data helpers (mirrors the /live endpoint).
 */
function timeVaryingValue(seed: number, min: number, max: number): number {
  const h = (seed * 9301 + 49297) % 233280;
  const r = h / 233280;
  return Math.round((min + r * (max - min)) * 100) / 100;
}

function timeVaryingString(seed: number, options: string[]): string {
  return options[Math.abs(seed) % options.length];
}

const STATUSES = ["healthy", "healthy", "healthy", "warning", "healthy", "critical", "healthy"];

interface Alert {
  id: string;
  module_id: string;
  module_name: string;
  severity: "critical" | "warning" | "info";
  title: string;
  message: string;
  metric: string;
  value: number;
  threshold: number;
  detected_at: number;
}

const MODULE_NAMES: Record<string, string> = {
  cybersecurity: "Security Command",
  health: "Health Command",
  finance: "Finance Command",
  retail: "Commerce Command",
  transport: "Transport Command",
  manufacturing: "Factory Command",
  tourism: "Hospitality Command",
  cultural_heritage: "Cultural Command",
  professional: "Professional Hub",
  utilities: "Utilities Command",
  sme: "SME Business Suite",
};

const MODULE_ALERTS: Record<string, (seed: number, ts: number) => Alert[]> = {
  cybersecurity: (s, ts) => [
    {
      id: `cyb-${s % 100}`,
      module_id: "cybersecurity",
      module_name: "Security Command",
      severity: "critical",
      title: "Active Breach Attempt",
      message: "Suspicious IP pattern detected — 12 failed auth attempts in 2 min",
      metric: "Threats Blocked",
      value: 12,
      threshold: 5,
      detected_at: ts - 45000,
    },
    {
      id: `cyb-${s % 100}-1`,
      module_id: "cybersecurity",
      module_name: "Security Command",
      severity: "warning",
      title: "Vulnerability Scan Lag",
      message: "Last CVE scan was 47 hours ago — exceeds 24h SLA",
      metric: "Vulns Scanned",
      value: 47,
      threshold: 24,
      detected_at: ts - 7200000,
    },
  ],
  health: (s, ts) => {
    const alerts: Alert[] = [];
    if (s % 3 === 0) {
      alerts.push({
        id: `hlth-${s % 100}`,
        module_id: "health",
        module_name: "Health Command",
        severity: "critical",
        title: "ICU Bed Shortage",
        message: "Critical care units at 98% capacity — 2 beds remaining",
        metric: "Bed Occupancy",
        value: 98,
        threshold: 90,
        detected_at: ts - 120000,
      });
    }
    if (s % 5 < 3) {
      alerts.push({
        id: `hlth-${s % 100}-1`,
        module_id: "health",
        module_name: "Health Command",
        severity: "warning",
        title: "Telehealth Queue Growing",
        message: "Average wait time exceeds 15 min threshold",
        metric: "Telehealth",
        value: 18,
        threshold: 15,
        detected_at: ts - 300000,
      });
    }
    return alerts;
  },
  finance: (s, ts) => {
    const alerts: Alert[] = [];
    if (s % 4 < 2) {
      alerts.push({
        id: `fin-${s % 100}`,
        module_id: "finance",
        module_name: "Finance Command",
        severity: "warning",
        title: "Fraud Alert Spike",
        message: "Fraud detection flagged 8 high-risk transactions this hour",
        metric: "Fraud Detected",
        value: 8,
        threshold: 5,
        detected_at: ts - 60000,
      });
    }
    return alerts;
  },
  retail: (s, ts) => {
    const alerts: Alert[] = [];
    if (s % 7 < 3) {
      alerts.push({
        id: `ret-${s % 100}`,
        module_id: "retail",
        module_name: "Commerce Command",
        severity: "warning",
        title: "Stockout Risk",
        message: "SKU-107 projected to stockout in 2 days — reorder now",
        metric: "Stock Health",
        value: 2,
        threshold: 5,
        detected_at: ts - 180000,
      });
    }
    return alerts;
  },
  transport: (s, ts) => {
    const alerts: Alert[] = [];
    if (s % 6 < 2) {
      alerts.push({
        id: `trn-${s % 100}`,
        module_id: "transport",
        module_name: "Transport Command",
        severity: "critical",
        title: "Incident — Route Blocked",
        message: "Major accident on I-95 corridor — 45 min estimated delay",
        metric: "Incident Clear",
        value: 45,
        threshold: 15,
        detected_at: ts - 90000,
      });
    }
    return alerts;
  },
  manufacturing: (s, ts) => {
    const alerts: Alert[] = [];
    if (s % 8 < 2) {
      alerts.push({
        id: `mfg-${s % 100}`,
        module_id: "manufacturing",
        module_name: "Factory Command",
        severity: "critical",
        title: "Machine Failure Imminent",
        message: "CNC-04 spindle overheat — predicted failure in 3 days",
        metric: "Machine Health",
        value: 41,
        threshold: 60,
        detected_at: ts - 240000,
      });
    }
    return alerts;
  },
  tourism: (s, _ts) => {
    return s % 5 < 2
      ? [
          {
            id: `tour-${s % 100}`,
            module_id: "tourism",
            module_name: "Hospitality Command",
            severity: "warning",
            title: "No-Show Rate Elevated",
            message: "Guest no-show rate for Hotel-West is 22% — overbooking adjustment needed",
            metric: "No-Show Rate",
            value: 22,
            threshold: 15,
            detected_at: Date.now() - 600000,
          },
        ]
      : [];
  },
  cultural_heritage: (_s, _ts) => [],
  professional: (s, _ts) => {
    return s % 9 < 2
      ? [
          {
            id: `prof-${s % 100}`,
            module_id: "professional",
            module_name: "Professional Hub",
            severity: "warning",
            title: "Contract Overdue",
            message: "Client MSA renewal overdue by 14 days — auto-renewal clause may trigger",
            metric: "Contract Cycle",
            value: 14,
            threshold: 7,
            detected_at: Date.now() - 86400000,
          },
        ]
      : [];
  },
  utilities: (s, ts) => {
    const alerts: Alert[] = [];
    if (s % 5 < 2) {
      alerts.push({
        id: `util-${s % 100}`,
        module_id: "utilities",
        module_name: "Utilities Command",
        severity: "critical",
        title: "Water Supply Deficit",
        message: "Zone A water demand exceeds supply by 18% — conservation alert",
        metric: "Water Supply",
        value: 18,
        threshold: 10,
        detected_at: ts - 3600000,
      });
    }
    return alerts;
  },
  sme: (s, _ts) => {
    return s % 10 < 3
      ? [
          {
            id: `sme-${s % 100}`,
            module_id: "sme",
            module_name: "SME Business Suite",
            severity: "warning",
            title: "Support Escalation",
            message: "3 premium-tier tickets escalated in last hour — review staffing",
            metric: "Ticket Res",
            value: 3,
            threshold: 1,
            detected_at: Date.now() - 300000,
          },
        ]
      : [];
  },
};

export async function GET(_req: Request) {
  const now = Date.now();
  const tick = Math.floor(now / 5000);
  const seed = tick * 17;

  const allAlerts: Alert[] = [];
  let criticalCount = 0;
  let warningCount = 0;

  for (const [moduleId, generator] of Object.entries(MODULE_ALERTS)) {
    const alerts = generator(seed + moduleId.length, now);
    const status = timeVaryingString(seed + moduleId.length, STATUSES);

    // If the module status is critical/warning and no specific alerts generated, add a generic one
    if (alerts.length === 0 && (status === "critical" || status === "warning")) {
      alerts.push({
        id: `${moduleId}-gen-${seed % 100}`,
        module_id: moduleId,
        module_name: MODULE_NAMES[moduleId] || moduleId,
        severity: status as "critical" | "warning",
        title: status === "critical" ? "System Degraded" : "Performance Warning",
        message:
          status === "critical"
            ? `${MODULE_NAMES[moduleId] || moduleId} is critically degraded — immediate attention required`
            : `${MODULE_NAMES[moduleId] || moduleId} performance is below nominal thresholds`,
        metric: "System Status",
        value: status === "critical" ? 25 : 65,
        threshold: 80,
        detected_at: now - 120000,
      });
    }

    for (const alert of alerts) {
      if (alert.severity === "critical") criticalCount++;
      else if (alert.severity === "warning") warningCount++;
    }
    allAlerts.push(...alerts);
  }

  // Sort: critical first, then by recency
  allAlerts.sort((a, b) => {
    if (a.severity !== b.severity) {
      return a.severity === "critical" ? -1 : 1;
    }
    return b.detected_at - a.detected_at;
  });

  return NextResponse.json(
    {
      ok: true,
      ts: now,
      total: allAlerts.length,
      critical_count: criticalCount,
      warning_count: warningCount,
      alerts: allAlerts,
      summary: {
        has_critical: criticalCount > 0,
        has_warning: warningCount > 0,
        highest_severity: criticalCount > 0 ? "critical" : warningCount > 0 ? "warning" : "healthy",
      },
    },
    {
      headers: {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        Pragma: "no-cache",
        Expires: "0",
      },
    }
  );
}
