"use client";

import { KPICard, Widget, DashboardData } from "./shared";
import { BarComparisonChart, TrendLineChart, MiniStatCard, FunnelProgress, COLORS } from "./charts";
import { motion } from "framer-motion";

export function RetailDashboard({ data }: { data: DashboardData }) {
  const forecast = data.forecast || [];
  const inventory = data.inventory || {
    alerts: [],
    reorder_recommendations: [],
    healthy: [],
    summary: { total_skus: 0, stockout_risks: 0, overstocks: 0 },
  };
  const suppliers = data.supplier_risks || [];
  const elasticity = data.price_elasticity;
  const personalizer = data.personalizer;

  const stockoutPct =
    inventory.summary.total_skus > 0
      ? Math.round((inventory.summary.stockout_risks / inventory.summary.total_skus) * 100)
      : 0;

  return (
    <motion.section
      className="module-dashboard"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
    >
      <div className="module-dashboard-header">
        <motion.h2
          initial={{ y: -10, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 0.3 }}
        >
          📦 Commerce Command Center
        </motion.h2>
        <motion.p
          initial={{ y: -10, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 0.3, delay: 0.05 }}
        >
          Real-time forecasting, inventory, supplier risk, and storefront personalization.
        </motion.p>
      </div>

      <motion.div
        className="module-kpi-row"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.1 }}
      >
        <KPICard
          title="Projected Demand"
          value={forecast.reduce((s, f) => s + f.projected_demand, 0).toLocaleString()}
          sub="Next 30 days"
        />
        <KPICard
          title="Stockout Risks"
          value={inventory.summary.stockout_risks}
          sub="SKUs need reorder"
          color={inventory.summary.stockout_risks > 0 ? "var(--danger)" : "var(--success)"}
        />
        <KPICard
          title="Stockout Rate"
          value={`${stockoutPct}%`}
          sub="Of total SKUs"
          color={stockoutPct > 10 ? "var(--danger)" : "var(--success)"}
        />
        {personalizer && (
          <KPICard
            title="Conversion Lift"
            value={`+${personalizer.estimated_conversion_lift_pct}%`}
            sub={personalizer.segment}
          />
        )}
      </motion.div>

      <div className="module-widgets-grid">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.2 }}
        >
          <Widget title="Demand vs Stock">
            <BarComparisonChart
              data={forecast.slice(0, 6)}
              xKey="sku"
              bars={[
                { key: "current_stock", color: "#64748b", label: "Stock" },
                { key: "projected_demand", color: "#6366f1", label: "Demand" },
              ]}
            />
          </Widget>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.25 }}
        >
          <Widget title="Inventory Health">
            <FunnelProgress
              stages={[
                {
                  label: "Total SKUs",
                  value: inventory.summary.total_skus,
                  max: Math.max(inventory.summary.total_skus, 1),
                  color: "#6366f1",
                },
                {
                  label: "Healthy",
                  value: inventory.healthy.length,
                  max: inventory.summary.total_skus,
                  color: "#10b981",
                },
                {
                  label: "Stockout Risk",
                  value: inventory.summary.stockout_risks,
                  max: inventory.summary.total_skus,
                  color: "#ef4444",
                },
                {
                  label: "Overstocks",
                  value: inventory.summary.overstocks,
                  max: inventory.summary.total_skus,
                  color: "#f59e0b",
                },
              ]}
            />
          </Widget>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.3 }}
        >
          <Widget title="Supplier Risk">
            <div className="space-y-2">
              {suppliers.slice(0, 4).map((s, i) => (
                <MiniStatCard
                  key={i}
                  icon="🚚"
                  label={s.supplier}
                  value={`${s.risk_score}/100`}
                  color={
                    s.risk_score > 70
                      ? COLORS.danger
                      : s.risk_score > 45
                        ? COLORS.warning
                        : COLORS.success
                  }
                />
              ))}
            </div>
          </Widget>
        </motion.div>

        {elasticity && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.35 }}
          >
            <Widget title="Price Elasticity">
              <div className="flex items-center gap-4">
                <div className="flex-1 space-y-2 text-xs text-aeon-fg-mute">
                  <div className="flex justify-between">
                    <span>SKU</span>
                    <strong className="text-aeon-fg">{elasticity.sku}</strong>
                  </div>
                  <div className="flex justify-between">
                    <span>Elasticity</span>
                    <strong className="text-aeon-fg">{elasticity.elasticity.toFixed(2)}</strong>
                  </div>
                  <div className="flex justify-between">
                    <span>Price Change</span>
                    <strong
                      className={
                        elasticity.price_change_pct > 0 ? "text-green-400" : "text-red-400"
                      }
                    >
                      {elasticity.price_change_pct}%
                    </strong>
                  </div>
                  <div className="flex justify-between">
                    <span>Demand Impact</span>
                    <strong
                      className={
                        elasticity.projected_demand_change_pct > 0
                          ? "text-green-400"
                          : "text-red-400"
                      }
                    >
                      {elasticity.projected_demand_change_pct}%
                    </strong>
                  </div>
                </div>
              </div>
            </Widget>
          </motion.div>
        )}

        {personalizer && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.4 }}
          >
            <Widget title="Storefront Personalization">
              <div className="text-xs text-aeon-fg-mute mb-2">
                Segment: <strong className="text-aeon-fg">{personalizer.segment}</strong>
              </div>
              <div className="flex flex-wrap gap-2 mb-2">
                {personalizer.recommended_products.slice(0, 4).map((p) => (
                  <span
                    key={p}
                    className="text-xs px-2 py-1 rounded-full bg-aeon-bg-2 text-aeon-fg"
                  >
                    {p}
                  </span>
                ))}
              </div>
              <MiniStatCard
                icon="📈"
                label="Conversion Lift"
                value={`+${personalizer.estimated_conversion_lift_pct}%`}
                trend="up"
              />
            </Widget>
          </motion.div>
        )}
      </div>
    </motion.section>
  );
}
