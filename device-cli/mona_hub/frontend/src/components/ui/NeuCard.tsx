import type { ReactNode, HTMLAttributes } from "react";
import { motion, type MotionProps } from "framer-motion";

type CardVariant = "raised" | "inset" | "flat";
type Padding = "none" | "sm" | "md" | "lg";
type Radius = "md" | "lg";

type NeuCardProps = {
  variant?: CardVariant;
  padding?: Padding;
  radius?: Radius;
  className?: string;
  children: ReactNode;
} & Omit<HTMLAttributes<HTMLDivElement>, "children"> &
  MotionProps;

const paddingMap: Record<Padding, number> = {
  none: 0,
  sm: 16,
  md: 24,
  lg: 32,
};

const radiusMap: Record<Radius, number> = {
  md: 12,
  lg: 16,
};

const variantStyles: Record<CardVariant, { background: string; boxShadow: string }> = {
  raised: {
    background: "var(--surface-raised)",
    boxShadow: "6px 6px 12px var(--shadow-dark), -6px -6px 12px var(--shadow-light)",
  },
  inset: {
    background: "var(--surface-inset)",
    boxShadow: "inset 4px 4px 8px var(--shadow-dark), inset -4px -4px 8px var(--shadow-light)",
  },
  flat: {
    background: "var(--surface-raised)",
    boxShadow: "none",
  },
};

export function NeuCard({
  variant = "raised",
  padding = "md",
  radius = "lg",
  className = "",
  children,
  ...rest
}: NeuCardProps) {
  const v = variantStyles[variant];

  return (
    <motion.div
      className={`border-0 ${className}`}
      style={{
        background: v.background,
        boxShadow: v.boxShadow,
        padding: paddingMap[padding],
        borderRadius: radiusMap[radius],
      }}
      {...rest}
    >
      {children}
    </motion.div>
  );
}
