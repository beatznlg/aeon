"use client";

import { KPICard, Widget, DashboardData } from "./shared";
import {
  BarComparisonChart,
  TrendLineChart,
  MiniStatCard,
  GaugeChart,
  FunnelProgress,
  COLORS,
} from "./charts";
import { motion } from "framer-motion";

export function SMEDashboard({ data }: { data: DashboardData }) {
  const workflows = data.workflow_data || [];
  const docs = data.document_queue || [];
  const tickets = data.support_tickets || [];
  const chains = data.supply_chain || [];
  const totalSavings = workflows.reduce((s, w) => s + w.cost_savings_annual, 0);
  const escalatedTickets = tickets.filter((t) => t.escalated).length;
  const highRiskChains = chains.filter((c) => c.risk_level === "high").length;
  const avgConfidence =
    docs.length > 0
      ? Math.round(docs.reduce((s, d) => s + d.confidence * 100, 0) / docs.length)
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
          🏢 SME Business Suite
        </motion.h2>
        <motion.p
          initial={{ y: -10, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 0.3, delay: 0.05 }}
        >
          Workflow automation, document processing, AI support, and supply chain analytics.
        </motion.p>
      </div>

      <motion.div
        className="module-kpi-row"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.1 }}
      >
        <KPICard
          title="Annual Savings"
          value={`$${totalSavings.toLocaleString()}`}
          sub="From automation"
        />
        <KPICard title="Docs Processed" value={docs.length} sub="In queue" />
        <KPICard
          title="Escalated Tickets"
          value={escalatedTickets}
          sub="Needs review"
          color={escalatedTickets > 0 ? "var(--danger)" : "var(--success)"}
        />
        <KPICard
          title="Supply Chain Risk"
          value={highRiskChains}
          sub="High risk"
          color={highRiskChains > 0 ? "var(--danger)" : "var(--success)"}
        />
      </motion.div>

      <div className="module-widgets-grid">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.2 }}
        >
          <Widget title="Automation Impact">
            <BarComparisonChart
              data={workflows.slice(0, 5).map((w) => ({
                name: w.process?.substring(0, 12) || "Process",
                savings: Math.round(w.cost_savings_annual / 1000),
                hours: w.hours_saved_per_month,
              }))}
              bars={[
                { key: "savings", color: "#10b981", label: "Annual Savings (K$)" },
                { key: "hours", color: "#6366f1", label: "Hours Saved/Mo" },
              ]}
              height={160}
            />
          </Widget>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.25 }}
        >
          <Widget title="Document Processing">
            <div className="flex items-center gap-4 mb-3">
              <GaugeChart
                value={avgConfidence}
                label="AI Confidence"
                max={100}
                color={
                  avgConfidence > 80
                    ? COLORS.success
                    : avgConfidence > 60
                      ? COLORS.warning
                      : COLORS.danger
                }
              />
              <div className="flex-1 space-y-2">
                {docs.slice(0, 3).map((d, i) => (
                  <MiniStatCard
                    key={i}
                    icon="📄"
                    label={d.document_type}
                    value={`${(d.confidence * 100).toFixed(0)}% · ${d.pages_processed} pages`}
                    color={d.confidence > 0.8 ? COLORS.success : COLORS.warning}
                  />
                ))}
              </div>
            </div>
          </Widget>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.3 }}
        >
          <Widget title="Support Triage">
            <div className="space-y-2">
              {tickets.slice(0, 4).map((t, i) => (
                <MiniStatCard
                  key={i}
                  icon="🎧"
                  label={t.detected_intent}
                  value={t.sentiment}
                  color={
                    t.escalated
                      ? COLORS.danger
                      : t.sentiment === "positive"
                        ? COLORS.success
                        : COLORS.warning
                  }
                />
              ))}
            </div>
          </Widget>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.35 }}
        >
          <Widget title="Supply Chain Analytics">
            <FunnelProgress
              stages={[
                {
                  label: "Total Chains",
                  value: chains.length,
                  max: Math.max(chains.length, 1),
                  color: "#6366f1",
                },
                {
                  label: "Healthy",
                  value: chains.filter((c) => c.risk_level === "low").length,
                  max: chains.length,
                  color: "#10b981",
                },
                { label: "At Risk", value: highRiskChains, max: chains.length, color: "#ef4444" },
              ]}
            />
          </Widget>
        </motion.div>
      </div>
    </motion.section>
  );
}
