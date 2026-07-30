"use client";

import { KPICard, Widget, DashboardData } from "./shared";
import { BarComparisonChart, TrendLineChart, MiniStatCard, GaugeChart , COLORS } from "./charts";
import { motion } from "framer-motion";

export function TransportDashboard({ data }: { data: DashboardData }) {
  const traffic = data.traffic || [];
  const fleet = data.fleet || [];
  const routes = data.route_plan || [];
  const activeIncidents = traffic.filter((t) => t.incident_nearby).length;
  const avgUtilization = Math.round(fleet.reduce((s, f) => s + f.utilization_pct, 0) / (fleet.length || 1));
  const avgCongestion = Math.round(traffic.reduce((s, t) => s + t.current_congestion, 0) / (traffic.length || 1));

  return (
    <motion.section className="module-dashboard" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.3 }}>
      <div className="module-dashboard-header">
        <motion.h2 initial={{ y: -10, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ duration: 0.3 }}>🚚 Transport Command Center</motion.h2>
        <motion.p initial={{ y: -10, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ duration: 0.3, delay: 0.05 }}>Traffic optimization, fleet scheduling, and route planning.</motion.p>
      </div>

      <motion.div className="module-kpi-row" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.1 }}>
        <KPICard title="Zones Monitored" value={traffic.length} sub="Active zones" />
        <KPICard title="Avg Congestion" value={`${avgCongestion}/10`} sub="Network-wide" color={avgCongestion > 6 ? "var(--danger)" : avgCongestion > 3 ? "var(--warning)" : "var(--success)"} />
        <KPICard title="Active Incidents" value={activeIncidents} sub="Nearby" color={activeIncidents > 0 ? "var(--danger)" : "var(--success)"} />
        <KPICard title="Fleet Utilization" value={`${avgUtilization}%`} sub="Average" />
      </motion.div>

      <div className="module-widgets-grid">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.2 }}>
          <Widget title="Traffic Congestion">
            <GaugeChart value={avgCongestion * 10} label="Congestion Level" max={100} color={avgCongestion > 6 ? COLORS.danger : avgCongestion > 3 ? COLORS.warning : COLORS.success} />
            <div className="mt-3 space-y-2">
              {traffic.slice(0, 3).map((t, i) => (
                <MiniStatCard
                  key={i} icon={t.incident_nearby ? "🚨" : "🚦"}
                  label={t.zone}
                  value={`${t.current_congestion}/10`}
                  color={t.current_congestion > 6 ? COLORS.danger : t.current_congestion > 3 ? COLORS.warning : COLORS.success}
                />
              ))}
            </div>
          </Widget>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.25 }}>
          <Widget title="Fleet Utilization">
            <BarComparisonChart
              data={fleet.map((f, i) => ({
                name: `Fleet ${i + 1}`,
                utilization: f.utilization_pct,
                available: 100 - f.utilization_pct,
              }))}
              bars={[
                { key: "utilization", color: "#6366f1", label: "Utilized" },
                { key: "available", color: "#64748b", label: "Available" },
              ]}
              height={150}
            />
            <div className="mt-2 text-xs text-center text-aeon-fg-mute">
              {fleet.length > 0 && `${fleet.reduce((s, f) => s + f.vehicles_available, 0)} vehicles across ${fleet.length} fleets`}
            </div>
          </Widget>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.3 }}>
          <Widget title="Route Comparison">
            <BarComparisonChart
              data={routes.slice(0, 5).map((r, i) => ({
                name: `Route ${i + 1}`,
                "Distance (km)": r.estimated_distance_km,
                "Time (min)": r.estimated_time_min / 10,
              }))}
              bars={[
                { key: "Distance (km)", color: "#6366f1", label: "Distance (km)" },
                { key: "Time (min)", color: "#10b981", label: "Time (min/10)" },
              ]}
              height={150}
            />
          </Widget>
        </motion.div>
      </div>
    </motion.section>
  );
}
