import { type ButtonHTMLAttributes, type ReactNode } from "react";
import { motion, useReducedMotion } from "framer-motion";

type Variant = "primary" | "secondary" | "ghost";
type Size = "sm" | "md" | "lg";

interface NeuButtonProps
  extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children" | "onAnimationStart" | "onDragStart" | "onDragEnd" | "onDrag"> {
  variant?: Variant;
  size?: Size;
  pill?: boolean;
  loading?: boolean;
  children: ReactNode;
  className?: string;
}

const sizeStyles: Record<Size, { height: number; px: number; fontSize: number }> = {
  sm: { height: 40, px: 16, fontSize: 14 },
  md: { height: 48, px: 24, fontSize: 16 },
  lg: { height: 56, px: 32, fontSize: 16 },
};

const shadows = {
  raised: "6px 6px 12px var(--shadow-dark), -6px -6px 12px var(--shadow-light)",
  hover: "8px 8px 16px var(--shadow-dark), -8px -8px 16px var(--shadow-light)",
  pressed: "inset 4px 4px 8px var(--shadow-dark), inset -4px -4px 8px var(--shadow-light)",
  secondaryRaised:
    "3px 3px 6px color-mix(in srgb, var(--shadow-dark) 50%, transparent), -3px -3px 6px color-mix(in srgb, var(--shadow-light) 50%, transparent)",
  secondaryHover:
    "4px 4px 8px color-mix(in srgb, var(--shadow-dark) 50%, transparent), -4px -4px 8px color-mix(in srgb, var(--shadow-light) 50%, transparent)",
  none: "none",
};

export function NeuButton({
  variant = "primary",
  size = "md",
  pill = false,
  loading = false,
  disabled = false,
  children,
  className = "",
  ...rest
}: NeuButtonProps) {
  const reducedMotion = useReducedMotion();
  const s = sizeStyles[size];

  const resolveShadow = (state: "rest" | "hover" | "pressed") => {
    if (disabled) return shadows.none;
    if (variant === "ghost") return shadows.none;
    if (state === "pressed") return shadows.pressed;
    if (variant === "secondary") {
      return state === "hover" ? shadows.secondaryHover : shadows.secondaryRaised;
    }
    return state === "hover" ? shadows.hover : shadows.raised;
  };

  const textColor =
    variant === "primary"
      ? "var(--accent)"
      : "var(--text-secondary)";

  const bg =
    variant === "ghost" ? "transparent" : "var(--surface-raised)";

  return (
    <motion.button
      type="button"
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center font-sans font-medium select-none border-0 outline-none cursor-pointer ${
        disabled ? "opacity-50 cursor-not-allowed" : ""
      } ${className}`}
      style={{
        height: s.height,
        paddingLeft: s.px,
        paddingRight: s.px,
        fontSize: s.fontSize,
        borderRadius: pill ? 9999 : 12,
        color: textColor,
        background: bg,
        boxShadow: resolveShadow("rest"),
        transition: "box-shadow 200ms ease-out",
        minWidth: 44,
        minHeight: 44,
      }}
      whileHover={
        disabled || reducedMotion
          ? undefined
          : { boxShadow: resolveShadow("hover") }
      }
      whileTap={
        disabled || reducedMotion
          ? undefined
          : { boxShadow: resolveShadow("pressed"), background: "var(--surface-inset)" }
      }
      {...rest}
    >
      {loading ? (
        <motion.span
          className="inline-block w-5 h-1 rounded-full"
          style={{ background: textColor }}
          animate={
            reducedMotion
              ? undefined
              : { opacity: [0.3, 0.8, 0.3] }
          }
          transition={{ duration: 1.2, repeat: Infinity, ease: "easeInOut" }}
          aria-label="Loading"
        />
      ) : (
        children
      )}
    </motion.button>
  );
}
