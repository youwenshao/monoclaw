import type { ReactNode } from "react";

type CardVariant = "raised" | "inset" | "flat";
type Padding = "none" | "sm" | "md" | "lg";
type Radius = "md" | "lg";

interface NeuCardProps {
  variant?: CardVariant;
  padding?: Padding;
  radius?: Radius;
  className?: string;
  children: ReactNode;
}

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
}: NeuCardProps) {
  const v = variantStyles[variant];

  return (
    <div
      className={`border-0 ${className}`}
      style={{
        background: v.background,
        boxShadow: v.boxShadow,
        padding: paddingMap[padding],
        borderRadius: radiusMap[radius],
      }}
    >
      {children}
    </div>
  );
}
