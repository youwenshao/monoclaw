import type { ReactNode } from "react";
import { motion, useReducedMotion } from "framer-motion";

interface PageTransitionProps {
  children: ReactNode;
  centered?: boolean;
  fullHeight?: boolean;
  className?: string;
}

const ease = [0.25, 0.1, 0.25, 1] as const;

export function PageTransition({
  children,
  centered = false,
  fullHeight = false,
  className = "",
}: PageTransitionProps) {
  const reducedMotion = useReducedMotion();

  return (
    <motion.div
      className={`max-w-[640px] mx-auto px-6 sm:px-12 py-16 ${
        centered ? "flex items-center justify-center flex-col" : ""
      } ${fullHeight ? "min-h-screen" : ""} ${className}`}
      initial={reducedMotion ? false : { opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={reducedMotion ? undefined : { opacity: 0, y: -10 }}
      transition={{
        duration: 0.4,
        ease: [...ease],
      }}
    >
      {children}
    </motion.div>
  );
}
