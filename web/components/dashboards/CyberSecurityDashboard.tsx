"use client";

import { KPICard, Widget, DashboardData } from "./shared";
import { GaugeChart, SeverityPieChart, RadarScoreChart, TimelineChart, MiniStatCard , COLORS } from "./charts";
import { motion } from "framer-motion";

export function CyberSecurityDashboard({ data }: { data: DashboardData }) {
  const threats = data.threats || [];
  const vulns = data.vulnerabilities || [];
  const ip = data.ip_reputation;
  const compliance = data.compliance;
  const criticalVulns = vulns.filter((v) => v.severity.toLowerCase() === "critical").length;
  const highVulns = vulns.filter((v) => v.severity.toLowerCase() === "high").length;
  const activeThreats = threats.filter((t) => t.status === "blocked" || t.status === "quarantined").length;
  const threatLevel = threats.length > 0 ? Math.min(threats.length * 20, 100) : 15;

  const severityData = [
    { name: "Critical", value: criticalVulns, color: "#ef4444" },
    { name: "High", value: highVulns, color: "#f59e0b" },
    { name: "Medium", value: vulns.filter((v) => v.severity.toLowerCase() === "medium").length, color: "#06b6d4" },
    { name: "Low", value: vulns.filter((v) => v.severity.toLowerCase() === "low").length, color: "#10b981" },
  ].filter((d) => d.value > 0);

  const radarData = compliance
    ? [
        { subject: "Access Control", score: Math.max(0, Math.min(100, compliance.score - 5)) },
        { subject: "Encryption", score: Math.max(0, Math.min(100, compliance.score + 10)) },
        { subject: "Audit Logs", score: Math.max(0, Math.min(100, compliance.score + 15)) },
        { subject: "Patch Mgmt", score: Math.max(0, Math.min(100, compliance.score - 10)) },
        { subject: "Incident Resp", score: Math.max(0, Math.min(100, compliance.score + 5)) },
      ]
    : [];

  const timelineEvents = threats.slice(0, 5).map((t) => ({
    time: t.id?.substring(0, 8) || `Threat`,
    label: `${t.indicator?.substring(0, 30)} — ${t.status}`,
    type: (t.severity === "critical" ? "danger" : t.severity === "high" ? "warn" : "ok") as "ok" | "warn" | "danger",
  }));

  return (
    <motion.section className="module-dashboard" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.3 }}>
      <div className="module-dashboard-header">
        <motion.h2 initial={{ y: -10, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ duration: 0.3 }}>🛡️ Security Command Center</motion.h2>
        <motion.p initial={{ y: -10, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ duration: 0.3, delay: 0.05 }}>Threat intelligence, vulnerability tracking, IP reputation, and compliance posture.</motion.p>
      </div>

      <motion.div className="module-kpi-row" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.1 }}>
        <KPICard title="Active Threats" value={activeThreats} sub="Blocked / quarantined" color={activeThreats > 0 ? "var(--danger)" : "var(--success)"} />
        <KPICard title="Critical Vulns" value={criticalVulns} sub="Need immediate patch" color={criticalVulns > 0 ? "var(--danger)" : "var(--success)"} />
        {ip && <KPICard title="IP Rep Score" value={ip.score.toFixed(2)} sub="0-1 reputation" color={ip.score > 0.5 ? "var(--danger)" : "var(--success)"} />}
        {compliance && <KPICard title="Compliance" value={`${compliance.score}%`} sub={compliance.framework} />}
      </motion.div>

      <div className="module-widgets-grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))" }}>
        {/* Threat gauge + pie side by side */}
        <motion.div key="widget-1" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.2 }}>
          <Widget title="Threat Intelligence">
            <div className="flex items-start gap-6">
              <GaugeChart value={threatLevel} label="Threat Level" max={100} />
              {severityData.length > 0 && <SeverityPieChart data={severityData} size={140} />}
            </div>
            {threats.length > 0 && (
              <div className="mt-3 space-y-1">
                {threats.slice(0, 3).map((t, i) => (
                  <MiniStatCard key={i} icon="⚠️" label={t.type} value={t.indicator} color={t.severity === "critical" ? COLORS.danger : COLORS.warning} />
                ))}
              </div>
            )}
          </Widget>
        </motion.div>

        {/* Vulnerability scan with radar */}
        <motion.div key="widget-2" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.25 }}>
          <Widget title="Vulnerability Posture">
            {radarData.length > 0 && <RadarScoreChart data={radarData} height={180} />}
            <div className="mt-2 grid grid-cols-3 gap-2 text-center">
              <MiniStatCard icon="🔴" label="Critical" value={criticalVulns} color={COLORS.danger} />
              <MiniStatCard icon="🟡" label="High" value={highVulns} color={COLORS.warning} />
              <MiniStatCard icon="🟢" label="Patched" value={vulns.filter((v) => v.patch_available).length} color={COLORS.success} />
            </div>
          </Widget>
        </motion.div>

        {/* Compliance posture */}
        {compliance && (
          <motion.div key="widget-3" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.3 }}>
            <Widget title="Compliance Posture">
              <div className="module-elasticity">
                <div><span>Framework</span><strong>{compliance.framework}</strong></div>
                <div><span>Maturity</span><strong>{compliance.maturity}</strong></div>
              </div>
              <GaugeChart value={compliance.score} label="Compliance Score" size={100} />
              {compliance.gaps.length > 0 && (
                <div className="mt-2">
                  <h4 className="text-xs text-aeon-fg-mute mb-1">Gaps</h4>
                  {compliance.gaps.map((g, i) => (
                    <div key={i} className="text-xs text-red-400 py-0.5">⚠ {g}</div>
                  ))}
                </div>
              )}
            </Widget>
          </motion.div>
        )}

        {/* IP Reputation */}
        {ip && (
          <motion.div key="widget-4" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.35 }}>
            <Widget title="IP Reputation">
              <div className="flex items-center gap-4">
                <GaugeChart value={Math.round((1 - ip.score) * 100)} label="Reputation" max={100} color={ip.score > 0.5 ? COLORS.danger : COLORS.success} />
                <div className="space-y-1 text-xs text-aeon-fg-mute">
                  <div>Known malicious: <strong className="text-aeon-fg">{ip.known_malicious ? "Yes" : "No"}</strong></div>
                  <div>Sources: <strong className="text-aeon-fg">{ip.source_countries.join(", ")}</strong></div>
                  <div>Last seen: <strong className="text-aeon-fg">{ip.last_seen_days}d ago</strong></div>
                </div>
              </div>
            </Widget>
          </motion.div>
        )}

        {/* Attack timeline */}
        {timelineEvents.length > 0 && (
          <motion.div key="widget-5" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.4 }}>
            <Widget title="Recent Threat Timeline">
              <TimelineChart events={timelineEvents} />
            </Widget>
          </motion.div>
        )}

        {/* Security news */}
        {data.security_news && data.security_news.length > 0 && (
          <motion.div key="widget-6" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.45 }}>
            <Widget title="Security News">
              <div className="space-y-2">
                {data.security_news.slice(0, 4).map((n, i) => (
                  <a key={i} href={n.url} className="block text-xs text-aeon-fg hover:text-aeon-primary transition-colors p-2 rounded hover:bg-aeon-bg-2/50">
                    📰 {n.title}
                  </a>
                ))}
              </div>
            </Widget>
          </motion.div>
        )}
      </div>
    </motion.section>
  );
}
