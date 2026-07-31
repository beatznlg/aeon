"use client";

import { KPICard, Widget, DashboardData } from "./shared";
import {
  GaugeChart,
  RadarScoreChart,
  TrendLineChart,
  SeverityPieChart,
  MiniStatCard,
  COLORS,
} from "./charts";
import { motion } from "framer-motion";

export function FinanceDashboard({ data }: { data: DashboardData }) {
  const risk = data.risk_data;
  const payments = data.payment_analysis || [];
  const market = data.market_data;
  const fraud = data.fraud_cases || [];
  const credit = data.credit_applications || [];
  const highFraud = fraud.filter((f) => f.risk_level === "high").length;

  const radarData = risk
    ? [
        { subject: "Diversification", score: (risk.diversification_score / 10) * 100 },
        { subject: "Risk/Reward", score: Math.min(100, (risk.sharpe_estimate / 3) * 100) },
        { subject: "Liquidity", score: 75 },
        {
          subject: "Volatility",
          score: risk.risk_rating === "high" ? 30 : risk.risk_rating === "medium" ? 55 : 80,
        },
        {
          subject: "Portfolio Health",
          score: risk.risk_rating === "low" ? 85 : risk.risk_rating === "medium" ? 60 : 35,
        },
      ]
    : [];

  const fraudSeverity = [
    { name: "High Risk", value: highFraud, color: "#ef4444" },
    {
      name: "Medium Risk",
      value: fraud.filter((f) => f.risk_level === "medium").length,
      color: "#f59e0b",
    },
    {
      name: "Low Risk",
      value: fraud.filter((f) => f.risk_level === "low").length,
      color: "#10b981",
    },
  ].filter((d) => d.value > 0);

  const fraudScore =
    fraud.length > 0
      ? Math.round((fraud.reduce((s, f) => s + f.fraud_score, 0) / fraud.length) * 100)
      : 0;

  const mockMarketData = market
    ? [
        { name: "Current", value: 100 },
        {
          name: "Forecast",
          value:
            market.predicted_direction === "bullish"
              ? 115
              : market.predicted_direction === "bearish"
                ? 88
                : 100,
        },
      ]
    : [];

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
          💰 Finance Command Center
        </motion.h2>
        <motion.p
          initial={{ y: -10, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 0.3, delay: 0.05 }}
        >
          Risk assessment, market forecasting, fraud detection, and credit scoring.
        </motion.p>
      </div>

      <motion.div
        className="module-kpi-row"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.1 }}
      >
        {risk && (
          <KPICard
            title="VaR (95%)"
            value={`$${risk.var_95_1d.toLocaleString()}`}
            sub={`${risk.var_95_pct}% of portfolio`}
          />
        )}
        {market && (
          <KPICard
            title="Market Outlook"
            value={market.predicted_direction}
            sub={`${(market.confidence * 100).toFixed(0)}% confidence`}
            color={
              market.predicted_direction === "bullish"
                ? "var(--success)"
                : market.predicted_direction === "bearish"
                  ? "var(--danger)"
                  : "var(--accent-2)"
            }
          />
        )}
        <KPICard
          title="Fraud Alerts"
          value={highFraud}
          sub="Need review"
          color={highFraud > 0 ? "var(--danger)" : "var(--success)"}
        />
        <KPICard title="Credit Applications" value={credit.length} sub="Processed" />
      </motion.div>

      <div className="module-widgets-grid">
        {radarData.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.2 }}
          >
            <Widget title="Portfolio Risk Radar">
              <RadarScoreChart data={radarData} height={200} />
              {risk && (
                <div className="mt-2 grid grid-cols-3 gap-2 text-center text-xs">
                  <div>
                    <span className="text-aeon-fg-mute">Sharpe</span>
                    <br />
                    <strong className="text-aeon-fg">{risk.sharpe_estimate}</strong>
                  </div>
                  <div>
                    <span className="text-aeon-fg-mute">Beta</span>
                    <br />
                    <strong className="text-aeon-fg">{risk.beta}</strong>
                  </div>
                  <div>
                    <span className="text-aeon-fg-mute">Diversification</span>
                    <br />
                    <strong className="text-aeon-fg">{risk.diversification_score}/10</strong>
                  </div>
                </div>
              )}
            </Widget>
          </motion.div>
        )}

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.25 }}
        >
          <Widget title="Fraud Detection">
            <div className="flex items-center gap-4 mb-3">
              <GaugeChart
                value={fraudScore}
                label="Fraud Index"
                max={100}
                color={
                  fraudScore > 60
                    ? COLORS.danger
                    : fraudScore > 30
                      ? COLORS.warning
                      : COLORS.success
                }
              />
              {fraudSeverity.length > 0 && <SeverityPieChart data={fraudSeverity} size={120} />}
            </div>
            {fraud.slice(0, 3).map((f, i) => (
              <MiniStatCard
                key={i}
                icon="💳"
                label={`${f.transaction_id?.substring(0, 12)}`}
                value={`$${f.amount?.toLocaleString() || 0}`}
                color={
                  f.risk_level === "high"
                    ? COLORS.danger
                    : f.risk_level === "medium"
                      ? COLORS.warning
                      : COLORS.success
                }
              />
            ))}
          </Widget>
        </motion.div>

        {market && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.3 }}
          >
            <Widget title="Market Forecast">
              {mockMarketData.length > 0 && (
                <TrendLineChart
                  data={[
                    { name: "Jan", value: 100, forecast: 102 },
                    { name: "Feb", value: 105, forecast: 108 },
                    { name: "Mar", value: 103, forecast: 110 },
                    {
                      name: "Apr",
                      value: 108,
                      forecast: market.predicted_direction === "bullish" ? 118 : 98,
                    },
                    {
                      name: "May",
                      value: 112,
                      forecast: market.predicted_direction === "bullish" ? 125 : 92,
                    },
                  ]}
                  lines={[
                    { key: "value", color: "#6366f1", label: "Actual" },
                    {
                      key: "forecast",
                      color: market.predicted_direction === "bullish" ? "#10b981" : "#ef4444",
                      label: "Forecast",
                    },
                  ]}
                />
              )}
              <div className="flex justify-between text-xs text-aeon-fg-mute mt-1">
                <span>Confidence: {(market.confidence * 100).toFixed(0)}%</span>
                <span>
                  Target:{" "}
                  {market.price_target_pct > 0
                    ? `+${market.price_target_pct}%`
                    : `${market.price_target_pct}%`}
                </span>
                <span>Volatility: {market.volatility_forecast}</span>
              </div>
            </Widget>
          </motion.div>
        )}

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.35 }}
        >
          <Widget title="Credit Scoring">
            <div className="grid grid-cols-2 gap-2">
              {credit.slice(0, 4).map((c, i) => (
                <MiniStatCard
                  key={i}
                  icon="📊"
                  label={c.applicant_id?.substring(0, 12) || `App #${i + 1}`}
                  value={`${c.credit_score} (${c.rating})`}
                  color={
                    c.credit_score > 670
                      ? COLORS.success
                      : c.credit_score > 580
                        ? COLORS.warning
                        : COLORS.danger
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
