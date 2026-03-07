import { motion, useReducedMotion } from "framer-motion";

interface StopButtonProps {
  onClick: () => void;
  className?: string;
}

export function StopButton({ onClick, className = "" }: StopButtonProps) {
  const reducedMotion = useReducedMotion();

  return (
    <motion.button
      type="button"
      onClick={onClick}
      aria-label="Stop generation"
      className={`inline-flex items-center justify-center border-0 cursor-pointer bg-transparent ${className}`}
      style={{
        height: 40,
        width: 40,
        padding: 0,
        borderRadius: 9999,
        color: "var(--text-secondary)",
        minWidth: 44,
        minHeight: 44,
      }}
      whileHover={
        reducedMotion
          ? undefined
          : {
              background: "var(--surface-raised)",
              boxShadow:
                "4px 4px 8px var(--shadow-dark), -4px -4px 8px var(--shadow-light)",
            }
      }
      whileTap={
        reducedMotion
          ? undefined
          : {
              background: "var(--surface-inset)",
              boxShadow:
                "inset 2px 2px 4px var(--shadow-dark), inset -2px -2px 4px var(--shadow-light)",
            }
      }
      transition={{ duration: 0.2 }}
    >
      {/* Square stop icon 8×8 */}
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <rect x="4" y="4" width="8" height="8" rx="1" fill="currentColor" />
      </svg>
    </motion.button>
  );
}
