"use client";

import { KPICard, Widget, DashboardData } from "./shared";
import { BarComparisonChart, TrendLineChart, MiniStatCard, GaugeChart, COLORS } from "./charts";
import { motion } from "framer-motion";

export function TourismDashboard({ data }: { data: DashboardData }) {
  const bookings = data.bookings || [];
  const pricing = data.pricing || [];
  const concierge = data.concierge || [];
  const avgOccupancy = Math.round(
    bookings.reduce((s, b) => s + b.occupancy_pct, 0) / (bookings.length || 1)
  );
  const avgPrice = Math.round(
    pricing.reduce((s, p) => s + p.recommended_price, 0) / (pricing.length || 1)
  );
  const positiveSentiment = concierge.filter((c) => c.sentiment === "positive").length;

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
          🏨 Hospitality Command Center
        </motion.h2>
        <motion.p
          initial={{ y: -10, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 0.3, delay: 0.05 }}
        >
          Booking optimization, dynamic pricing, and automated concierge.
        </motion.p>
      </div>

      <motion.div
        className="module-kpi-row"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.1 }}
      >
        <KPICard title="Avg Occupancy" value={`${avgOccupancy}%`} sub="Across properties" />
        <KPICard title="Avg Recommended Price" value={`$${avgPrice}`} sub="Per night" />
        <KPICard title="Guest Requests" value={concierge.length} sub="Triaged" />
        <KPICard
          title="Positive Sentiment"
          value={positiveSentiment}
          sub={`Of ${concierge.length} guests`}
          color={positiveSentiment > concierge.length / 2 ? "var(--success)" : "var(--warning)"}
        />
      </motion.div>

      <div className="module-widgets-grid">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.2 }}
        >
          <Widget title="Occupancy by Property">
            <BarComparisonChart
              data={bookings.slice(0, 5).map((b) => ({
                name: b.property?.substring(0, 12) || "Property",
                occupancy: b.occupancy_pct,
              }))}
              bars={[{ key: "occupancy", color: "#6366f1", label: "Occupancy %" }]}
              height={180}
            />
            <GaugeChart value={avgOccupancy} label="Avg Occupancy" max={100} />
          </Widget>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.25 }}
        >
          <Widget title="Dynamic Pricing">
            <BarComparisonChart
              data={pricing.slice(0, 5).map((p) => ({
                name: p.room?.substring(0, 10) || "Room",
                "Base Price": p.base_price,
                Recommended: p.recommended_price,
              }))}
              bars={[
                { key: "Base Price", color: "#64748b", label: "Base" },
                { key: "Recommended", color: "#10b981", label: "AI Recommended" },
              ]}
              height={180}
            />
          </Widget>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.3 }}
        >
          <Widget title="Concierge Triage">
            <div className="space-y-2">
              {concierge.slice(0, 5).map((c, i) => (
                <MiniStatCard
                  key={i}
                  icon="🤵"
                  label={c.intent}
                  value={c.sentiment}
                  color={
                    c.sentiment === "positive"
                      ? COLORS.success
                      : c.sentiment === "negative"
                        ? COLORS.danger
                        : COLORS.warning
                  }
                />
              ))}
            </div>
          </Widget>
        </motion.div>
      </div>
    </motion.section>
  );
}
