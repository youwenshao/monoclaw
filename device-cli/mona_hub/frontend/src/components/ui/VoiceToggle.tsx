import { motion, useReducedMotion } from "framer-motion";

interface VoiceToggleProps {
  enabled: boolean;
  onToggle: (enabled: boolean) => void;
}

export function VoiceToggle({ enabled, onToggle }: VoiceToggleProps) {
  const reducedMotion = useReducedMotion();

  return (
    <button
      type="button"
      role="switch"
      aria-checked={enabled}
      aria-label="Toggle voice interaction"
      onClick={() => onToggle(!enabled)}
      className="relative inline-flex items-center border-0 cursor-pointer p-0"
      style={{
        width: 48,
        height: 28,
        borderRadius: 9999,
        background: enabled ? "var(--surface-raised)" : "var(--surface-inset)",
        boxShadow: enabled
          ? "4px 4px 8px var(--shadow-dark), -4px -4px 8px var(--shadow-light)"
          : "inset 3px 3px 6px var(--shadow-dark), inset -3px -3px 6px var(--shadow-light)",
        transition: "background 200ms ease-out, box-shadow 200ms ease-out",
        minWidth: 44,
        minHeight: 44,
        /* Center the 48×28 visual within the 44px min touch target */
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      {/* Inner track for visual reference */}
      <span
        className="absolute"
        style={{
          left: 0,
          top: 0,
          width: 48,
          height: 28,
          borderRadius: 9999,
          pointerEvents: "none",
        }}
      />
      {/* Indicator dot */}
      <motion.span
        className="absolute rounded-full"
        style={{
          width: 18,
          height: 18,
          top: 5,
        }}
        animate={
          reducedMotion
            ? { left: enabled ? 26 : 4 }
            : { left: enabled ? 26 : 4 }
        }
        transition={{ type: "spring", stiffness: 500, damping: 30 }}
      >
        <span
          className="block w-full h-full rounded-full"
          style={{
            background: enabled ? "var(--accent)" : "var(--text-tertiary)",
            boxShadow: enabled
              ? "2px 2px 4px var(--shadow-dark)"
              : "none",
            transition: "background 200ms ease-out, box-shadow 200ms ease-out",
          }}
        />
      </motion.span>
    </button>
  );
}
