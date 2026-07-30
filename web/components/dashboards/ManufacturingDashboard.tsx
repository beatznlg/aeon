"use client";

import { KPICard, Widget, DashboardData } from "./shared";
import { GaugeChart, BarComparisonChart, TrendLineChart, MiniStatCard, TimelineChart , COLORS } from "./charts";
import { motion } from "framer-motion";

export function ManufacturingDashboard({ data }: { data: DashboardData }) {
  const maintenance = data.maintenance || [];
  const qc = data.qc || [];
  const logistics = data.logistics || [];
  const atRisk = maintenance.filter((m) => m.failure_risk_pct > 60).length;
  const delayedRoutes = logistics.filter((l) => l.status === "delayed").length;
  const avgTemp = Math.round(maintenance.reduce((s, m) => s + m.temp_c, 0) / (maintenance.length || 1));

  const machineMetrics = [
    { name: "Healthy", value: maintenance.filter((m) => m.status === "healthy").length, color: "#10b981" },
    { name: "Warning", value: maintenance.filter((m) => m.status === "warning").length, color: "#f59e0b" },
    { name: "Critical", value: maintenance.filter((m) => m.status === "critical").length, color: "#ef4444" },
  ].filter((d) => d.value > 0);

  return (
    <motion.section className="module-dashboard" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.3 }}>
      <div className="module-dashboard-header">
        <motion.h2 initial={{ y: -10, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ duration: 0.3 }}>🏭 Factory Command Center</motion.h2>
        <motion.p initial={{ y: -10, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ duration: 0.3, delay: 0.05 }}>Predictive maintenance, quality control, and smart logistics monitoring.</motion.p>
      </div>

      <motion.div className="module-kpi-row" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.1 }}>
        <KPICard title="Machines at Risk" value={atRisk} sub="Need attention" color={atRisk > 0 ? "var(--danger)" : "var(--success)"} />
        <KPICard title="Avg Defect Rate" value={`${(qc.reduce((s, q) => s + q.defect_rate, 0) / (qc.length || 1) * 100).toFixed(2)}%`} sub="Across batches" />
        <KPICard title="Avg Temperature" value={`${avgTemp}°C`} sub="Machine average" color={avgTemp > 80 ? "var(--danger)" : avgTemp > 60 ? "var(--warning)" : "var(--success)"} />
        <KPICard title="Logistics Delays" value={delayedRoutes} sub="Routes delayed" color={delayedRoutes > 0 ? "var(--danger)" : "var(--success)"} />
      </motion.div>

      <div className="module-widgets-grid">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.2 }}>
          <Widget title="Machine Health Overview">
            <div className="grid grid-cols-2 gap-3 mb-3">
              <GaugeChart value={avgTemp} label="Avg Temp °C" max={120} color={avgTemp > 80 ? COLORS.danger : avgTemp > 60 ? COLORS.warning : COLORS.success} />
              <GaugeChart value={atRisk > 0 ? Math.min(atRisk * 25, 100) : 5} label="Risk Index" max={100} color={atRisk > 0 ? COLORS.danger : COLORS.success} />
            </div>
            {maintenance.slice(0, 3).map((m, i) => (
              <MiniStatCard
                key={i} icon="⚙️"
                label={m.machine_id}
                value={`${m.temp_c}°C · ${m.vibration_hz}Hz · ${m.failure_risk_pct}% risk`}
                color={m.status === "critical" ? COLORS.danger : m.status === "warning" ? COLORS.warning : COLORS.success}
              />
            ))}
          </Widget>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.25 }}>
          <Widget title="Quality Control">
            <BarComparisonChart
              data={qc.slice(0, 5).map((q) => ({
                name: q.batch_id?.substring(0, 8) || "Batch",
                defects: q.defects_found,
                scanned: Math.round(q.items_scanned / 10),
              }))}
              bars={[
                { key: "defects", color: "#ef4444", label: "Defects" },
                { key: "scanned", color: "#6366f1", label: "Scanned (÷10)" },
              ]}
              height={150}
            />
            <div className="mt-2 text-xs text-center text-aeon-fg-mute">
              {qc.filter((q) => q.status === "pass").length}/{qc.length} batches passed
            </div>
          </Widget>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.3 }}>
          <Widget title="Smart Logistics">
            <div className="space-y-2">
              {logistics.slice(0, 4).map((l, i) => (
                <MiniStatCard
                  key={i} icon={l.status === "delayed" ? "⏰" : "✅"}
                  label={`Route ${l.route_id?.substring(0, 8) || i + 1}`}
                  value={`ETA: ${l.eta_days}d · ${l.status}`}
                  color={l.status === "delayed" ? COLORS.warning : COLORS.success}
                />
              ))}
            </div>
          </Widget>
        </motion.div>
      </div>
    </motion.section>
  );
}
