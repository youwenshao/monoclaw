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
        width: 44,
        height: 24,
        borderRadius: 12,
        background: "transparent",
        border: `2px solid ${enabled ? "var(--accent)" : "var(--text-tertiary)"}`,
        transition: "border-color 200ms ease-out",
        minWidth: 44,
        minHeight: 24,
      }}
    >
      <motion.span
        className="absolute rounded-full"
        style={{
          width: 16,
          height: 16,
          top: 2,
          background: enabled ? "var(--accent)" : "var(--text-tertiary)",
          transition: "background 200ms ease-out",
        }}
        animate={{ left: enabled ? 22 : 2 }}
        transition={
          reducedMotion
            ? { duration: 0 }
            : { type: "spring", stiffness: 500, damping: 30 }
        }
      />
    </button>
  );
}
