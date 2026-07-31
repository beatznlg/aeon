"use client";

import { KPICard, Widget, DashboardData } from "./shared";
import { TrendLineChart, BarComparisonChart, MiniStatCard, GaugeChart, COLORS } from "./charts";
import { motion } from "framer-motion";

export function CulturalHeritageDashboard({ data }: { data: DashboardData }) {
  const visitors = data.visitor_data || [];
  const sites = data.heritage_sites || [];
  const exhibitions = data.exhibitions || [];
  const tours = data.virtual_tours || [];
  const avgEngagement = Math.round(
    visitors.reduce((s, v) => s + v.engagement_score, 0) / (visitors.length || 1)
  );

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
          🎭 Cultural Heritage Command Center
        </motion.h2>
        <motion.p
          initial={{ y: -10, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 0.3, delay: 0.05 }}
        >
          Visitor engagement, heritage site insights, exhibition planning, and virtual tours.
        </motion.p>
      </div>

      <motion.div
        className="module-kpi-row"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.1 }}
      >
        <KPICard title="Venues" value={visitors.length} sub="Monitored" />
        <KPICard
          title="Engagement Score"
          value={`${avgEngagement}%`}
          sub="Average"
          color={avgEngagement > 65 ? "var(--success)" : "var(--warning)"}
        />
        <KPICard
          title="Total Annual Visitors"
          value={sites.reduce((s, si) => s + si.annual_visitors, 0).toLocaleString()}
          sub="Across sites"
        />
        <KPICard title="Exhibitions Planned" value={exhibitions.length} sub="In pipeline" />
      </motion.div>

      <div className="module-widgets-grid">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.2 }}
        >
          <Widget title="Visitor Engagement">
            <div className="flex items-center gap-4 mb-3">
              <GaugeChart
                value={avgEngagement}
                label="Engagement"
                max={100}
                color={
                  avgEngagement > 65
                    ? COLORS.success
                    : avgEngagement > 40
                      ? COLORS.warning
                      : COLORS.danger
                }
              />
              <div className="flex-1 space-y-2">
                {visitors.slice(0, 3).map((v, i) => (
                  <MiniStatCard
                    key={i}
                    icon="👥"
                    label={v.venue}
                    value={`${v.daily_visitors}/day`}
                  />
                ))}
              </div>
            </div>
          </Widget>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.25 }}
        >
          <Widget title="Heritage Sites">
            <BarComparisonChart
              data={sites.slice(0, 5).map((s) => ({
                name: s.site?.substring(0, 12) || "Site",
                visitors: Math.round(s.annual_visitors / 1000),
              }))}
              bars={[{ key: "visitors", color: "#6366f1", label: "Annual Visitors (K)" }]}
              height={160}
            />
          </Widget>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.3 }}
        >
          <Widget title="Exhibition Revenue">
            <BarComparisonChart
              data={exhibitions.slice(0, 5).map((e) => ({
                name: e.theme?.substring(0, 10) || "Exhibition",
                revenue: Math.round(e.projected_revenue / 1000),
              }))}
              bars={[{ key: "revenue", color: "#10b981", label: "Revenue (K$)" }]}
              height={160}
            />
          </Widget>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.35 }}
        >
          <Widget title="Virtual Tours">
            <div className="space-y-2">
              {tours.slice(0, 4).map((t, i) => (
                <MiniStatCard
                  key={i}
                  icon="🎧"
                  label={t.site}
                  value={`${t.interest} · ${Math.floor(t.audio_duration_seconds / 60)}m ${t.audio_duration_seconds % 60}s`}
                />
              ))}
            </div>
          </Widget>
        </motion.div>
      </div>
    </motion.section>
  );
}
