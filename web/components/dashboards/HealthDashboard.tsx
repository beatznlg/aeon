"use client";

import { KPICard, Widget, DashboardData } from "./shared";
import { GaugeChart, TrendLineChart, BarComparisonChart, MiniStatCard, COLORS } from "./charts";
import { motion } from "framer-motion";

export function HealthDashboard({ data }: { data: DashboardData }) {
  const diagnostics = data.diagnostics || [];
  const vitals = data.patient_vitals || [];
  const interactions = data.drug_interactions || [];
  const telehealth = data.telehealth || [];
  const urgentCases = diagnostics.filter((d) => d.urgency === "high").length;
  const alerts = vitals.filter((v) => v.alert).length;

  const triageData = [
    {
      name: "Emergent",
      value: diagnostics.filter((d) => d.urgency === "high").length,
      color: "#ef4444",
    },
    {
      name: "Moderate",
      value: diagnostics.filter((d) => d.urgency === "moderate").length,
      color: "#f59e0b",
    },
    { name: "Low", value: diagnostics.filter((d) => d.urgency === "low").length, color: "#10b981" },
  ].filter((d) => d.value > 0);

  const mockVitalsTrend =
    vitals.length > 0
      ? vitals.slice(0, 6).map((v, i) => ({
          name: v.metric?.substring(0, 8) || `M${i}`,
          baseline: v.baseline,
          current: v.current,
        }))
      : [];

  const severityScore = urgentCases > 0 ? Math.min(urgentCases * 30, 100) : 10;

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
          🏥 Health Command Center
        </motion.h2>
        <motion.p
          initial={{ y: -10, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 0.3, delay: 0.05 }}
        >
          AI diagnostics, patient monitoring, drug interaction checks, and telehealth triage.
        </motion.p>
      </div>

      <motion.div
        className="module-kpi-row"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.1 }}
      >
        <KPICard title="Cases Triaged" value={diagnostics.length} sub="This shift" />
        <KPICard
          title="Urgent Cases"
          value={urgentCases}
          sub="Needs immediate attention"
          color={urgentCases > 0 ? "var(--danger)" : "var(--success)"}
        />
        <KPICard
          title="Vital Alerts"
          value={alerts}
          sub="Flagged patients"
          color={alerts > 0 ? "var(--danger)" : "var(--success)"}
        />
        <KPICard
          title="Telehealth Eligible"
          value={telehealth.filter((t) => t.urgency !== "emergent").length}
          sub="Virtual visits"
        />
      </motion.div>

      <div className="module-widgets-grid">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.2 }}
        >
          <Widget title="Diagnostic Triage">
            <div className="flex items-center gap-4">
              <GaugeChart value={severityScore} label="Severity Index" max={100} />
              <div className="flex-1 space-y-2">
                {triageData.map((d) => (
                  <MiniStatCard
                    key={d.name}
                    icon={d.name === "Emergent" ? "🔴" : d.name === "Moderate" ? "🟡" : "🟢"}
                    label={d.name}
                    value={d.value}
                    color={d.color}
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
          <Widget title="Patient Vitals Trend">
            {mockVitalsTrend.length > 0 ? (
              <TrendLineChart
                data={mockVitalsTrend}
                lines={[
                  { key: "current", color: "#6366f1", label: "Current" },
                  { key: "baseline", color: "#64748b", label: "Baseline" },
                ]}
              />
            ) : (
              <div className="text-xs text-aeon-fg-mute text-center py-8">
                No vitals data available
              </div>
            )}
          </Widget>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.3 }}
        >
          <Widget title="Drug Interaction Check">
            {interactions.map((d, i) => (
              <div key={i} className="mb-2">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xs font-semibold text-aeon-fg">
                    {d.medications.join(" + ")}
                  </span>
                  <span className="text-xs text-aeon-fg-mute">
                    ({d.interactions_found} interactions)
                  </span>
                </div>
                {d.interactions.length > 0 ? (
                  d.interactions.slice(0, 2).map((ix, j) => (
                    <div
                      key={j}
                      className="text-xs text-red-400 bg-red-400/5 rounded p-2 mb-1 border border-red-400/10"
                    >
                      <strong>{ix.severity}</strong> — {ix.warning}
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-green-400">No significant interactions predicted.</p>
                )}
              </div>
            ))}
          </Widget>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.35 }}
        >
          <Widget title="Telehealth Triage">
            <div className="space-y-2">
              {telehealth.slice(0, 4).map((t, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between p-2 rounded hover:bg-aeon-bg-2/50"
                >
                  <div className="flex-1 min-w-0">
                    <div className="text-xs text-aeon-fg truncate">{t.symptoms}</div>
                    <div className="text-[10px] text-aeon-fg-mute">Age: {t.age}</div>
                  </div>
                  <span
                    className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                      t.urgency === "emergent"
                        ? "bg-red-400/10 text-red-400"
                        : t.urgency === "urgent"
                          ? "bg-amber-400/10 text-amber-400"
                          : "bg-green-400/10 text-green-400"
                    }`}
                  >
                    {t.urgency}
                  </span>
                </div>
              ))}
            </div>
          </Widget>
        </motion.div>
      </div>
    </motion.section>
  );
}
