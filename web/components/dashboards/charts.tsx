"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  AreaChart,
  Area,
  PieChart,
  Pie,
  Cell,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
} from "recharts";
import { motion } from "framer-motion";

// ════════════════════════════════════════════════════════════════
// Color palette
// ════════════════════════════════════════════════════════════════

export const COLORS = {
  success: "#10b981",
  warning: "#f59e0b",
  danger: "#ef4444",
  primary: "#6366f1",
  info: "#06b6d4",
  purple: "#8b5cf6",
  pink: "#ec4899",
  slate: "#64748b",
};

const CHART_COLORS = [
  "#6366f1",
  "#10b981",
  "#f59e0b",
  "#ef4444",
  "#06b6d4",
  "#8b5cf6",
  "#ec4899",
  "#14b8a6",
  "#eab308",
  "#3b82f6",
];

// ════════════════════════════════════════════════════════════════
// 1. GaugeChart — single-value circular gauge (0-100)
// ════════════════════════════════════════════════════════════════

export function GaugeChart({
  value,
  label,
  max = 100,
  size = 120,
  color,
}: {
  value: number;
  label: string;
  max?: number;
  size?: number;
  color?: string;
}) {
  const pct = Math.min(value / max, 1);
  const strokeColor =
    color || (pct > 0.75 ? COLORS.danger : pct > 0.5 ? COLORS.warning : COLORS.success);
  const cx = size / 2;
  const cy = size / 2 + 8;
  const r = size / 2 - 16;
  const circumference = 2 * Math.PI * r;
  const offset = circumference * (1 - pct);

  return (
    <motion.div
      className="flex flex-col items-center"
      initial={{ opacity: 0, scale: 0.8 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ type: "spring", stiffness: 200, damping: 20 }}
    >
      <svg width={size} height={size} style={{ overflow: "visible" }}>
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="var(--aeon-border)" strokeWidth={8} />
        <motion.circle
          cx={cx}
          cy={cy}
          r={r}
          fill="none"
          stroke={strokeColor}
          strokeWidth={8}
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1.2, ease: "easeOut" }}
          transform={`rotate(-90 ${cx} ${cy})`}
        />
        <text
          x={cx}
          y={cy - 4}
          textAnchor="middle"
          fill="var(--aeon-fg)"
          fontSize={18}
          fontWeight={700}
        >
          {Math.round(pct * 100)}%
        </text>
        <text x={cx} y={cy + 14} textAnchor="middle" fill="var(--aeon-fg-mute)" fontSize={10}>
          {label}
        </text>
      </svg>
    </motion.div>
  );
}

// ════════════════════════════════════════════════════════════════
// 2. SeverityPieChart — pie chart for severity/status distribution
// ════════════════════════════════════════════════════════════════

export function SeverityPieChart({
  data,
  size = 160,
}: {
  data: { name: string; value: number; color: string }[];
  size?: number;
}) {
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.5 }}>
      <ResponsiveContainer width="100%" height={size}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={30}
            outerRadius={60}
            paddingAngle={3}
            dataKey="value"
            animationBegin={200}
            animationDuration={800}
          >
            {data.map((entry, i) => (
              <Cell key={i} fill={entry.color} stroke="transparent" />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              background: "var(--aeon-bg-1)",
              border: "1px solid var(--aeon-border)",
              borderRadius: 8,
              fontSize: 12,
            }}
          />
        </PieChart>
      </ResponsiveContainer>
      <div className="flex flex-wrap justify-center gap-3 mt-1">
        {data.map((d) => (
          <div key={d.name} className="flex items-center gap-1 text-xs text-aeon-fg-mute">
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                background: d.color,
                display: "inline-block",
              }}
            />
            {d.name} ({d.value})
          </div>
        ))}
      </div>
    </motion.div>
  );
}

// ════════════════════════════════════════════════════════════════
// 3. TrendLineChart — line chart with multiple series
// ════════════════════════════════════════════════════════════════

export function TrendLineChart({
  data,
  lines,
  height = 180,
  xKey = "name",
}: {
  data: any[];
  lines: { key: string; color: string; label: string }[];
  height?: number;
  xKey?: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.1 }}
    >
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--aeon-border)" opacity={0.3} />
          <XAxis
            dataKey={xKey}
            tick={{ fill: "var(--aeon-fg-mute)", fontSize: 10 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: "var(--aeon-fg-mute)", fontSize: 10 }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            contentStyle={{
              background: "var(--aeon-bg-1)",
              border: "1px solid var(--aeon-border)",
              borderRadius: 8,
              fontSize: 12,
            }}
          />
          {lines.map((l) => (
            <Line
              key={l.key}
              type="monotone"
              dataKey={l.key}
              stroke={l.color}
              strokeWidth={2}
              dot={{ r: 3, fill: l.color }}
              activeDot={{ r: 5 }}
              animationDuration={1000}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
      <div className="flex gap-4 mt-1 justify-center text-xs text-aeon-fg-mute">
        {lines.map((l) => (
          <span key={l.key} className="flex items-center gap-1">
            <span
              style={{
                width: 12,
                height: 3,
                borderRadius: 2,
                background: l.color,
                display: "inline-block",
              }}
            />
            {l.label}
          </span>
        ))}
      </div>
    </motion.div>
  );
}

// ════════════════════════════════════════════════════════════════
// 4. BarComparisonChart — horizontal or vertical bar comparison
// ════════════════════════════════════════════════════════════════

export function BarComparisonChart({
  data,
  bars,
  height = 200,
  xKey = "name",
  layout = "vertical",
}: {
  data: any[];
  bars: { key: string; color: string; label: string }[];
  height?: number;
  xKey?: string;
  layout?: "vertical" | "horizontal";
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.15 }}
    >
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={data} layout={layout} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--aeon-border)" opacity={0.3} />
          {layout === "vertical" ? (
            <>
              <XAxis
                dataKey={xKey}
                tick={{ fill: "var(--aeon-fg-mute)", fontSize: 10 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: "var(--aeon-fg-mute)", fontSize: 10 }}
                axisLine={false}
                tickLine={false}
              />
            </>
          ) : (
            <>
              <YAxis
                dataKey={xKey}
                type="category"
                tick={{ fill: "var(--aeon-fg-mute)", fontSize: 10 }}
                axisLine={false}
                tickLine={false}
              />
              <XAxis
                type="number"
                tick={{ fill: "var(--aeon-fg-mute)", fontSize: 10 }}
                axisLine={false}
                tickLine={false}
              />
            </>
          )}
          <Tooltip
            contentStyle={{
              background: "var(--aeon-bg-1)",
              border: "1px solid var(--aeon-border)",
              borderRadius: 8,
              fontSize: 12,
            }}
          />
          {bars.map((b) => (
            <Bar
              key={b.key}
              dataKey={b.key}
              fill={b.color}
              radius={[3, 3, 0, 0]}
              animationDuration={800}
              animationBegin={200}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </motion.div>
  );
}

// ════════════════════════════════════════════════════════════════
// 5. RadarScoreChart — radar chart for multi-dimensional scoring
// ════════════════════════════════════════════════════════════════

export function RadarScoreChart({
  data,
  height = 200,
}: {
  data: { subject: string; score: number; fullMark?: number }[];
  height?: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.5, delay: 0.2 }}
    >
      <ResponsiveContainer width="100%" height={height}>
        <RadarChart data={data}>
          <PolarGrid stroke="var(--aeon-border)" opacity={0.3} />
          <PolarAngleAxis dataKey="subject" tick={{ fill: "var(--aeon-fg-mute)", fontSize: 10 }} />
          <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} axisLine={false} />
          <Radar
            name="Score"
            dataKey="score"
            stroke={COLORS.primary}
            fill={COLORS.primary}
            fillOpacity={0.15}
            animationDuration={1000}
          />
        </RadarChart>
      </ResponsiveContainer>
    </motion.div>
  );
}

// ════════════════════════════════════════════════════════════════
// 6. AreaTrendChart — filled area for cumulative trends
// ════════════════════════════════════════════════════════════════

export function AreaTrendChart({
  data,
  areas,
  height = 180,
  xKey = "name",
}: {
  data: any[];
  areas: { key: string; color: string; label: string }[];
  height?: number;
  xKey?: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.1 }}
    >
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--aeon-border)" opacity={0.3} />
          <XAxis
            dataKey={xKey}
            tick={{ fill: "var(--aeon-fg-mute)", fontSize: 10 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: "var(--aeon-fg-mute)", fontSize: 10 }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            contentStyle={{
              background: "var(--aeon-bg-1)",
              border: "1px solid var(--aeon-border)",
              borderRadius: 8,
              fontSize: 12,
            }}
          />
          {areas.map((a) => (
            <Area
              key={a.key}
              type="monotone"
              dataKey={a.key}
              stroke={a.color}
              fill={a.color}
              fillOpacity={0.08}
              strokeWidth={2}
              animationDuration={1000}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </motion.div>
  );
}

// ════════════════════════════════════════════════════════════════
// 7. FunnelProgress — horizontal funnel/progress bars
// ════════════════════════════════════════════════════════════════

export function FunnelProgress({
  stages,
}: {
  stages: { label: string; value: number; max: number; color: string }[];
}) {
  return (
    <motion.div
      className="space-y-2"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.5 }}
    >
      {stages.map((s, i) => (
        <div key={s.label} className="flex items-center gap-2">
          <span className="text-xs text-aeon-fg-mute w-24 shrink-0 text-right">{s.label}</span>
          <div className="flex-1 h-5 rounded-full bg-aeon-bg-2 overflow-hidden relative">
            <motion.div
              className="h-full rounded-full"
              style={{ background: s.color }}
              initial={{ width: 0 }}
              animate={{ width: `${Math.min((s.value / s.max) * 100, 100)}%` }}
              transition={{ duration: 0.8, delay: i * 0.1, ease: "easeOut" }}
            />
          </div>
          <span className="text-xs text-aeon-fg-mute w-12 shrink-0">
            {s.value}/{s.max}
          </span>
        </div>
      ))}
    </motion.div>
  );
}

// ════════════════════════════════════════════════════════════════
// 8. MiniStatCard — compact KPI with icon and sparkline
// ════════════════════════════════════════════════════════════════

export function MiniStatCard({
  icon,
  label,
  value,
  trend,
  color = COLORS.primary,
}: {
  icon: string;
  label: string;
  value: string | number;
  trend?: "up" | "down" | "neutral";
  color?: string;
}) {
  return (
    <motion.div
      className="flex items-center gap-3 p-3 rounded-lg border border-aeon-border bg-aeon-bg-2/50"
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ type: "spring", stiffness: 200, damping: 20 }}
      whileHover={{ scale: 1.02, borderColor: color }}
    >
      <span className="text-xl">{icon}</span>
      <div className="flex-1 min-w-0">
        <div className="text-xs text-aeon-fg-mute truncate">{label}</div>
        <div className="text-sm font-semibold text-aeon-fg">{value}</div>
      </div>
      {trend && (
        <span
          className={`text-xs ${trend === "up" ? "text-green-400" : trend === "down" ? "text-red-400" : "text-aeon-fg-mute"}`}
        >
          {trend === "up" ? "↑" : trend === "down" ? "↓" : "→"}
        </span>
      )}
    </motion.div>
  );
}

// ════════════════════════════════════════════════════════════════
// 9. TimelineChart — horizontal timeline for events/incidents
// ════════════════════════════════════════════════════════════════

export function TimelineChart({
  events,
}: {
  events: { time: string; label: string; type: "ok" | "warn" | "danger" }[];
}) {
  const typeColors = { ok: COLORS.success, warn: COLORS.warning, danger: COLORS.danger };
  return (
    <motion.div
      className="space-y-2"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.5 }}
    >
      {events.map((e, i) => (
        <motion.div
          key={i}
          className="flex items-center gap-3 p-2 rounded-lg hover:bg-aeon-bg-2/50 transition-colors"
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: i * 0.05, duration: 0.3 }}
        >
          <div
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: typeColors[e.type],
              flexShrink: 0,
            }}
          />
          <span className="text-xs text-aeon-fg-mute w-16 shrink-0">{e.time}</span>
          <span className="text-xs text-aeon-fg">{e.label}</span>
        </motion.div>
      ))}
    </motion.div>
  );
}
