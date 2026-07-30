"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { motion, type HTMLMotionProps } from "framer-motion";

// ════════════════════════════════════════════════════════════════
// AnimatedNumber — smoothly counts from previous value to new value
// ════════════════════════════════════════════════════════════════

export function AnimatedNumber({
  value,
  duration = 0.8,
  className,
  formatter,
}: {
  value: number;
  duration?: number;
  className?: string;
  formatter?: (v: number) => string;
}) {
  const [display, setDisplay] = useState(value);
  const prevRef = useRef(value);
  const rafRef = useRef<number>(0);

  useEffect(() => {
    const startVal = prevRef.current;
    const endVal = value;
    if (startVal === endVal) return;

    const startTime = performance.now();
    prevRef.current = endVal;

    const animate = (now: number) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / (duration * 1000), 1);
      // Cubic ease-out
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = Math.round(startVal + (endVal - startVal) * eased);
      setDisplay(current);
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(animate);
      } else {
        setDisplay(endVal);
      }
    };

    rafRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(rafRef.current);
  }, [value, duration]);

  const formatted = formatter ? formatter(display) : String(display);
  return <span className={className}>{formatted}</span>;
}

// ════════════════════════════════════════════════════════════════
// AnimatedKPICard — wrapper around KPI cards with number animation
// ════════════════════════════════════════════════════════════════

export function AnimatedKPICard({
  title,
  value,
  sub,
  color,
  refreshKey,
}: {
  title: string;
  value: string | number;
  sub?: string;
  color?: string;
  refreshKey: number;
}) {
  const numericValue = typeof value === "string" ? parseFloat(value.replace(/[^0-9.-]/g, "")) : value;

  return (
    <motion.div
      className="module-kpi-card"
      layout
      transition={{ type: "spring", stiffness: 200, damping: 25 }}
    >
      <motion.div
        className="module-kpi-dot"
        style={{ background: color || "var(--success)" }}
        animate={{ scale: [1, 1.3, 1] }}
        transition={{ duration: 0.4, ease: "easeOut" }}
      />
      <div>
        <div className="module-kpi-title">{title}</div>
        <motion.div
          className="module-kpi-value"
          key={`${refreshKey}-${title}`}
          initial={{ opacity: 0.4, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: "easeOut" }}
        >
          {!isNaN(numericValue) ? (
            <AnimatedNumber value={Math.round(numericValue)} duration={0.6} />
          ) : (
            value
          )}
        </motion.div>
        {sub && <div className="module-kpi-sub">{sub}</div>}
      </div>
    </motion.div>
  );
}

// ════════════════════════════════════════════════════════════════
// AnimatedWidget — card wrapper that pulses/highlights when data refreshes
// ════════════════════════════════════════════════════════════════

interface AnimatedWidgetProps extends HTMLMotionProps<"div"> {
  title: string;
  children: ReactNode;
  refreshKey: number;
  accentColor?: string;
}

export function AnimatedWidget({
  title,
  children,
  refreshKey,
  accentColor = "rgba(99, 102, 241, 0.08)",
  ...rest
}: AnimatedWidgetProps) {
  return (
    <motion.div
      className="module-widget"
      layout
      transition={{ type: "spring", stiffness: 150, damping: 20 }}
      {...rest}
    >
      <motion.div
        className="flex items-center justify-between"
        initial={false}
      >
        <motion.h3
          key={`title-${refreshKey}`}
          initial={{ opacity: 0.7 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.3 }}
        >
          {title}
        </motion.h3>
      </motion.div>
      <motion.div
        key={refreshKey}
        initial={{ opacity: 0.85 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.5, ease: "easeOut" }}
        className="relative"
      >
        {/* Subtle highlight flash on data refresh */}
        <motion.div
          className="absolute inset-0 rounded-lg pointer-events-none -m-2"
          initial={{ opacity: 0 }}
          animate={{ opacity: [0, 0.15, 0] }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          style={{ background: accentColor }}
        />
        {children}
      </motion.div>
    </motion.div>
  );
}
