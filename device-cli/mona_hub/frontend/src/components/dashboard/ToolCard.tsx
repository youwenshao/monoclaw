import { forwardRef } from "react";
import { motion, useReducedMotion } from "framer-motion";
import type { DraggableAttributes } from "@dnd-kit/core";
import type { SyntheticListenerMap } from "@dnd-kit/core/dist/hooks/utilities";
import type { ToolInfo } from "@/lib/api";

interface ToolCardProps {
  tool: ToolInfo;
  editing: boolean;
  hidden: boolean;
  isDragging?: boolean;
  dragListeners?: SyntheticListenerMap;
  dragAttributes?: DraggableAttributes;
  style?: React.CSSProperties;
  onClick?: () => void;
  onToggleVisibility?: () => void;
}

function EyeIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function EyeOffIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
      <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
      <path d="M14.12 14.12a3 3 0 1 1-4.24-4.24" />
      <line x1="1" y1="1" x2="23" y2="23" />
    </svg>
  );
}

function GripIcon({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
      <circle cx="9" cy="6" r="1.5" />
      <circle cx="15" cy="6" r="1.5" />
      <circle cx="9" cy="12" r="1.5" />
      <circle cx="15" cy="12" r="1.5" />
      <circle cx="9" cy="18" r="1.5" />
      <circle cx="15" cy="18" r="1.5" />
    </svg>
  );
}

const TOOL_ICONS: Record<string, string> = {
  "real-estate": "🏠",
  "immigration": "🌏",
  "fnb-hospitality": "🍽️",
  "accounting": "📊",
  "legal": "⚖️",
  "medical-dental": "🏥",
  "construction": "🏗️",
  "import-export": "🚢",
  "academic": "📚",
  "vibe-coder": "💻",
  "solopreneur": "🚀",
  "student": "🎓",
};

export const ToolCard = forwardRef<HTMLDivElement, ToolCardProps>(
  function ToolCard(
    { tool, editing, hidden, isDragging, dragListeners, dragAttributes, style, onClick, onToggleVisibility },
    ref,
  ) {
    const reducedMotion = useReducedMotion();
    const emoji = TOOL_ICONS[tool.slug] ?? "🔧";

    return (
      <motion.div
        ref={ref}
        layout={!reducedMotion}
        layoutId={tool.slug}
        style={{
          ...style,
          background: "var(--surface-raised)",
          boxShadow: isDragging
            ? "12px 12px 24px var(--shadow-dark), -12px -12px 24px var(--shadow-light)"
            : "6px 6px 12px var(--shadow-dark), -6px -6px 12px var(--shadow-light)",
          borderRadius: 16,
          padding: 20,
          opacity: hidden ? 0.5 : 1,
          cursor: editing ? (isDragging ? "grabbing" : "default") : "pointer",
          zIndex: isDragging ? 10 : 0,
          transition: isDragging ? undefined : "box-shadow 200ms ease-out, opacity 200ms ease-out",
          touchAction: "none",
        }}
        whileHover={
          editing || reducedMotion
            ? undefined
            : {
                scale: 1.02,
                boxShadow: "8px 8px 16px var(--shadow-dark), -8px -8px 16px var(--shadow-light)",
              }
        }
        whileTap={editing || reducedMotion ? undefined : { scale: 0.98 }}
        onClick={editing ? undefined : onClick}
      >
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-3">
            {editing && (
              <button
                type="button"
                className="flex-shrink-0 cursor-grab border-0 bg-transparent p-0 text-text-tertiary hover:text-text-secondary active:cursor-grabbing"
                style={{ touchAction: "none" }}
                {...dragListeners}
                {...dragAttributes}
              >
                <GripIcon className="h-5 w-5" />
              </button>
            )}
            <span className="text-2xl" role="img" aria-label={tool.name}>
              {emoji}
            </span>
          </div>

          {editing && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onToggleVisibility?.();
              }}
              className="flex-shrink-0 border-0 bg-transparent p-1 cursor-pointer text-text-tertiary hover:text-text-primary"
              aria-label={hidden ? "Show tool" : "Hide tool"}
            >
              {hidden ? (
                <EyeOffIcon className="h-4 w-4" />
              ) : (
                <EyeIcon className="h-4 w-4" />
              )}
            </button>
          )}
        </div>

        <h3 className="mt-3 text-base font-medium text-text-primary leading-snug">
          {tool.name}
        </h3>

        {tool.description && (
          <p className="mt-1 text-sm text-text-secondary line-clamp-2">
            {tool.description}
          </p>
        )}

        {tool.tools.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {tool.tools.slice(0, 3).map((t) => (
              <span
                key={t}
                className="inline-block rounded-full px-2.5 py-0.5 text-xs font-medium text-accent"
                style={{ background: "color-mix(in srgb, var(--accent) 10%, transparent)" }}
              >
                {t}
              </span>
            ))}
            {tool.tools.length > 3 && (
              <span className="inline-block rounded-full px-2.5 py-0.5 text-xs text-text-tertiary">
                +{tool.tools.length - 3}
              </span>
            )}
          </div>
        )}
      </motion.div>
    );
  },
);
