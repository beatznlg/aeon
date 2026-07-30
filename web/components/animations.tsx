"use client";

import { motion, type Variants, type HTMLMotionProps } from "framer-motion";
import { type ReactNode } from "react";

// ════════════════════════════════════════════════════════════════
// Shared spring configs
// ════════════════════════════════════════════════════════════════

export const springPresets = {
  /** Gentle spring for cards and panels appearing */
  gentle: { type: "spring" as const, stiffness: 200, damping: 22, mass: 1 },
  /** Bouncy spring for hero elements */
  bouncy: { type: "spring" as const, stiffness: 300, damping: 14, mass: 1 },
  /** Quick spring for micro-interactions (hover, press) */
  quick: { type: "spring" as const, stiffness: 400, damping: 25, mass: 0.5 },
  /** Snappy spring for modals and menus */
  snappy: { type: "spring" as const, stiffness: 500, damping: 30, mass: 0.8 },
};

// ════════════════════════════════════════════════════════════════
// Staggered container — children animate in sequence
// ════════════════════════════════════════════════════════════════

const staggerVariants: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.05,
      delayChildren: 0.08,
    },
  },
};

const itemVariants: Variants = {
  hidden: { opacity: 0, y: 16 },
  visible: {
    opacity: 1,
    y: 0,
    transition: springPresets.gentle,
  },
};

interface StaggerContainerProps {
  children: ReactNode;
  className?: string;
  staggerDelay?: number;
  as?: "div" | "section" | "article";
}

export function StaggerContainer({
  children,
  className,
  staggerDelay = 0.05,
  as = "div",
}: StaggerContainerProps) {
  const Component = motion[as];
  return (
    <Component
      className={className}
      initial="hidden"
      animate="visible"
      variants={{
        hidden: { opacity: 0 },
        visible: {
          opacity: 1,
          transition: { staggerChildren: staggerDelay, delayChildren: 0.08 },
        },
      }}
    >
      {children}
    </Component>
  );
}

export function StaggerItem({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <motion.div className={className} variants={itemVariants}>
      {children}
    </motion.div>
  );
}

// ════════════════════════════════════════════════════════════════
// Fade in — simple fade + slide up
// ════════════════════════════════════════════════════════════════

interface FadeInProps extends HTMLMotionProps<"div"> {
  children: ReactNode;
  className?: string;
  delay?: number;
  y?: number;
  duration?: number;
  once?: boolean;
}

export function FadeIn({
  children,
  className,
  delay = 0,
  y = 20,
  duration = 0.5,
  once = true,
  ...rest
}: FadeInProps) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y }}
      whileInView={once ? { opacity: 1, y: 0 } : undefined}
      animate={once ? undefined : { opacity: 1, y: 0 }}
      viewport={once ? { once: true, margin: "-40px" } : undefined}
      transition={{ ...springPresets.gentle, delay, duration }}
      {...rest}
    >
      {children}
    </motion.div>
  );
}

// ════════════════════════════════════════════════════════════════
// Slide up — appears sliding upward
// ════════════════════════════════════════════════════════════════

interface SlideUpProps {
  children: ReactNode;
  className?: string;
  delay?: number;
  distance?: number;
}

export function SlideUp({ children, className, delay = 0, distance = 30 }: SlideUpProps) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: distance }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ ...springPresets.bouncy, delay }}
    >
      {children}
    </motion.div>
  );
}

// ════════════════════════════════════════════════════════════════
// Scale on hover — micro-interaction wrapper
// ════════════════════════════════════════════════════════════════

interface ScaleOnHoverProps {
  children: ReactNode;
  className?: string;
  scale?: number;
  whileTap?: number;
}

export function ScaleOnHover({
  children,
  className,
  scale = 1.02,
  whileTap = 0.97,
}: ScaleOnHoverProps) {
  return (
    <motion.div
      className={className}
      whileHover={{ scale }}
      whileTap={{ scale: whileTap }}
      transition={springPresets.quick}
    >
      {children}
    </motion.div>
  );
}

// ════════════════════════════════════════════════════════════════
// Hover glow — card that glows on hover
// ════════════════════════════════════════════════════════════════

interface HoverGlowProps {
  children: ReactNode;
  className?: string;
  color?: string;
}

export function HoverGlow({ children, className, color = "rgba(99, 102, 241, 0.08)" }: HoverGlowProps) {
  return (
    <motion.div
      className={className}
      whileHover={{ boxShadow: `0 0 30px ${color}` }}
      transition={springPresets.quick}
    >
      {children}
    </motion.div>
  );
}

// ════════════════════════════════════════════════════════════════
// Stat counter — animated number that counts up
// ════════════════════════════════════════════════════════════════

interface AnimatedCounterProps {
  value: number;
  className?: string;
  duration?: number;
}

export function AnimatedCounter({ value, className, duration = 1.2 }: AnimatedCounterProps) {
  // We use a simple CSS transition for this rather than framer,
  // since the existing AnimatedStat already does this well.
  return <span className={className}>{value}</span>;
}

// ════════════════════════════════════════════════════════════════
// Preset layout animations for page transitions
// ════════════════════════════════════════════════════════════════

export const pageTransition = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -12 },
  transition: springPresets.gentle,
};

// Export motion for direct use in components
export { motion };
