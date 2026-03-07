import { motion, useReducedMotion, type Variants } from "framer-motion";

type OrbState = "idle" | "listening" | "speaking" | "thinking" | "success";
type OrbSize = "sm" | "md" | "lg";

interface OrbProps {
  state?: OrbState;
  size?: OrbSize;
}

const sizeMap: Record<OrbSize, number> = { sm: 80, md: 100, lg: 120 };

const orbVariants: Variants = {
  idle: {
    scale: [1, 1.03, 1],
    rotate: 0,
    transition: {
      scale: { duration: 4, repeat: Infinity, ease: "easeInOut" },
    },
  },
  listening: {
    scale: [1, 1.05, 1],
    transition: {
      scale: { duration: 2, repeat: Infinity, ease: "easeInOut" },
    },
  },
  speaking: {
    scale: [1, 1.06, 1],
    transition: {
      scale: { duration: 1.2, repeat: Infinity, ease: "easeInOut" },
    },
  },
  thinking: {
    scale: 1,
    rotate: 360,
    transition: {
      rotate: { duration: 8, repeat: Infinity, ease: "linear" },
    },
  },
  success: {
    scale: [1, 1.08, 1],
    transition: {
      scale: { duration: 0.6, ease: "easeInOut" },
    },
  },
};

const staticVariant: Variants = {
  idle: { scale: 1, rotate: 0 },
  listening: { scale: 1, rotate: 0 },
  speaking: { scale: 1, rotate: 0 },
  thinking: { scale: 1, rotate: 0 },
  success: { scale: 1, rotate: 0 },
};

const ringVariants: Variants = {
  idle: { scale: 1, opacity: 0 },
  listening: {
    scale: [1, 1.6],
    opacity: [0.5, 0],
    transition: { duration: 1.5, repeat: Infinity, ease: "easeOut" },
  },
  speaking: { scale: 1, opacity: 0 },
  thinking: { scale: 1, opacity: 0 },
  success: { scale: 1, opacity: 0 },
};

export function Orb({ state = "idle", size = "md" }: OrbProps) {
  const reducedMotion = useReducedMotion();
  const d = sizeMap[size];

  const gradient =
    state === "success"
      ? "radial-gradient(circle, var(--success) 0%, transparent 70%)"
      : "radial-gradient(circle, var(--accent) 0%, transparent 70%)";

  return (
    <div
      className="relative flex items-center justify-center"
      style={{ width: d, height: d }}
      aria-hidden="true"
    >
      {/* Ring pulse for listening state */}
      <motion.div
        className="absolute inset-0 rounded-full"
        style={{
          border: "2px solid var(--accent)",
        }}
        variants={reducedMotion ? staticVariant : ringVariants}
        animate={state}
        transition={{ duration: 0.6, ease: "easeInOut" }}
      />

      {/* Main orb */}
      <motion.div
        className="rounded-full"
        style={{
          width: d,
          height: d,
          background: gradient,
          filter:
            state === "speaking"
              ? "brightness(1.15)"
              : "brightness(1)",
        }}
        variants={reducedMotion ? staticVariant : orbVariants}
        animate={state}
        initial={false}
        transition={{ duration: 0.6, ease: "easeInOut" }}
      />
    </div>
  );
}
