import type { Variants } from "framer-motion";

const ease = [0.25, 0.1, 0.25, 1] as const;

export const containerVariants: Variants = {
  initial: {},
  enter: {
    transition: {
      staggerChildren: 0.12,
      delayChildren: 0.1,
    },
  },
};

export const childVariants: Variants = {
  initial: { opacity: 0, y: 16 },
  enter: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.45, ease: [...ease] },
  },
};
