"use client";

import { KPICard, Widget, DashboardData } from "./shared";
import { BarComparisonChart, TrendLineChart, MiniStatCard, GaugeChart, FunnelProgress , COLORS } from "./charts";
import { motion } from "framer-motion";

export function UtilitiesDashboard({ data }: { data: DashboardData }) {
  const resources = data.resource_data || [];
  const services = data.public_services || [];
  const waste = data.waste_data || [];
  const grid = data.energy_grid || [];
  const criticalResources = resources.filter((r) => r.status === "critical").length;
  const gridCritical = grid.filter((g) => g.status === "critical").length;
  const avgRenewable = Math.round(grid.reduce((s, g) => s + g.renewable_share_pct, 0) / (grid.length || 1));
  const avgRecycling = Math.round(waste.reduce((s, w) => s + w.recycled_pct, 0) / (waste.length || 1));

  return (
    <motion.section className="module-dashboard" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.3 }}>
      <div className="module-dashboard-header">
        <motion.h2 initial={{ y: -10, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ duration: 0.3 }}>⚡ Utilities Command Center</motion.h2>
        <motion.p initial={{ y: -10, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ duration: 0.3, delay: 0.05 }}>Resource optimization, public service monitoring, waste management, and energy grid oversight.</motion.p>
      </div>

      <motion.div className="module-kpi-row" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.1 }}>
        <KPICard title="Critical Resources" value={criticalResources} sub="Need attention" color={criticalResources > 0 ? "var(--danger)" : "var(--success)"} />
        <KPICard title="Renewable Energy" value={`${avgRenewable}%`} sub="Grid share" color={avgRenewable > 40 ? "var(--success)" : "var(--warning)"} />
        <KPICard title="Recycling Rate" value={`${avgRecycling}%`} sub="Average" />
        <KPICard title="Grid Critical Zones" value={gridCritical} sub="Need attention" color={gridCritical > 0 ? "var(--danger)" : "var(--success)"} />
      </motion.div>

      <div className="module-widgets-grid">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.2 }}>
          <Widget title="Resource Optimization">
            <BarComparisonChart
              data={resources.slice(0, 6).map((r) => ({
                name: r.resource?.substring(0, 10) || "Resource",
                supply: r.supply,
                demand: r.demand,
              }))}
              bars={[
                { key: "supply", color: "#10b981", label: "Supply" },
                { key: "demand", color: "#ef4444", label: "Demand" },
              ]}
              height={160}
            />
          </Widget>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.25 }}>
          <Widget title="Waste Management">
            <FunnelProgress
              stages={[
                { label: "Total Waste (T)", value: Math.round(waste.reduce((s, w) => s + w.total_waste_tons, 0)), max: Math.max(Math.round(waste.reduce((s, w) => s + w.total_waste_tons, 0)), 1), color: "#64748b" },
                { label: "Recycled %", value: avgRecycling, max: 100, color: "#10b981" },
                { label: "Collection Eff.", value: Math.round(waste.reduce((s, w) => s + w.collection_efficiency, 0) / (waste.length || 1)), max: 100, color: "#6366f1" },
              ]}
            />
          </Widget>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.3 }}>
          <Widget title="Energy Grid Load">
            <BarComparisonChart
              data={grid.slice(0, 5).map((g) => ({
                name: g.region?.substring(0, 10) || "Region",
                load: Math.round(g.current_load_mw / 10),
                renewable: Math.round(g.renewable_share_pct / 5),
              }))}
              bars={[
                { key: "load", color: "#f59e0b", label: "Load (MW/10)" },
                { key: "renewable", color: "#10b981", label: "Renewable % (/5)" },
              ]}
              height={160}
            />
            <GaugeChart value={avgRenewable} label="Renewable %" max={100} color={avgRenewable > 40 ? COLORS.success : COLORS.warning} />
          </Widget>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.35 }}>
          <Widget title="Public Service KPIs">
            <div className="space-y-2">
              {services.slice(0, 4).map((s, i) => (
                <MiniStatCard
                  key={i} icon="🏛️"
                  label={s.service}
                  value={`${s.kpi_score}%`}
                  color={s.kpi_score > 80 ? COLORS.success : s.kpi_score > 60 ? COLORS.warning : COLORS.danger}
                />
              ))}
            </div>
          </Widget>
        </motion.div>
      </div>
    </motion.section>
  );
}
