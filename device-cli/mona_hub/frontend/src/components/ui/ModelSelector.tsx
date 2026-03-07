import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import { NeuCard } from "./NeuCard";

interface ModelInfo {
  model_id: string;
  name: string;
  category?: string;
  size_bytes?: number;
}

interface ModelSelectorProps {
  models: ModelInfo[];
  activeModel: string | null;
  autoRoutingEnabled: boolean;
  autoRoutingActive: boolean;
  onSelectModel: (id: string) => void;
  onToggleAutoRouting: (auto: boolean) => void;
}

const categoryColors: Record<string, string> = {
  fast: "var(--accent)",
  standard: "var(--text-secondary)",
  think: "var(--accent-warm)",
  coder: "var(--success)",
};

function truncate(str: string, max: number) {
  return str.length > max ? str.slice(0, max) + "…" : str;
}

export function ModelSelector({
  models,
  activeModel,
  autoRoutingEnabled,
  autoRoutingActive,
  onSelectModel,
  onToggleAutoRouting,
}: ModelSelectorProps) {
  const reducedMotion = useReducedMotion();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const activeModelInfo = models.find((m) => m.model_id === activeModel);
  const displayName = autoRoutingActive
    ? "Auto"
    : activeModelInfo
      ? truncate(activeModelInfo.name, 15)
      : "Select model";

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [open]);

  return (
    <div ref={containerRef} className="relative inline-block">
      {/* Pill trigger */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-2 font-sans text-sm font-medium text-text-secondary border-0 cursor-pointer select-none"
        style={{
          height: 36,
          paddingLeft: 14,
          paddingRight: 14,
          borderRadius: 9999,
          background: "var(--surface-raised)",
          boxShadow:
            "4px 4px 8px var(--shadow-dark), -4px -4px 8px var(--shadow-light)",
          transition: "box-shadow 200ms ease-out",
          minHeight: 44,
          minWidth: 44,
        }}
      >
        <span>{displayName}</span>
        <svg
          width="12"
          height="12"
          viewBox="0 0 12 12"
          fill="none"
          aria-hidden="true"
          className="transition-transform"
          style={{ transform: open ? "rotate(180deg)" : "rotate(0)" }}
        >
          <path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {/* Dropdown */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={reducedMotion ? false : { opacity: 0, y: -4, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.97 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
            className="absolute top-full mt-2 right-0 z-50"
            style={{ minWidth: 220 }}
          >
            <NeuCard variant="raised" padding="sm" radius="md">
              <div className="flex flex-col gap-1">
                {autoRoutingEnabled && (
                  <button
                    type="button"
                    onClick={() => {
                      onToggleAutoRouting(!autoRoutingActive);
                      setOpen(false);
                    }}
                    className="flex items-center justify-between w-full px-3 py-2 rounded-lg text-sm font-sans border-0 cursor-pointer text-left transition-colors hover:bg-surface-inset"
                    style={{
                      background: autoRoutingActive
                        ? "var(--surface-inset)"
                        : "transparent",
                      color: "var(--text-primary)",
                      minHeight: 44,
                    }}
                  >
                    <span>Auto-select based on complexity</span>
                    <div
                      className="flex-shrink-0 rounded-full"
                      style={{
                        width: 8,
                        height: 8,
                        background: autoRoutingActive
                          ? "var(--accent)"
                          : "var(--text-tertiary)",
                      }}
                    />
                  </button>
                )}

                {autoRoutingEnabled && (
                  <div
                    className="my-1"
                    style={{
                      height: 1,
                      background: "var(--surface-inset)",
                    }}
                  />
                )}

                {models.map((model) => {
                  const isActive = model.model_id === activeModel && !autoRoutingActive;
                  return (
                    <button
                      key={model.model_id}
                      type="button"
                      onClick={() => {
                        onSelectModel(model.model_id);
                        if (autoRoutingActive) onToggleAutoRouting(false);
                        setOpen(false);
                      }}
                      className="flex items-center justify-between w-full px-3 py-2 rounded-lg text-sm font-sans border-0 cursor-pointer text-left transition-colors hover:bg-surface-inset"
                      style={{
                        background: isActive
                          ? "var(--surface-inset)"
                          : "transparent",
                        boxShadow: isActive
                          ? "inset 2px 2px 4px var(--shadow-dark), inset -2px -2px 4px var(--shadow-light)"
                          : "none",
                        color: "var(--text-primary)",
                        minHeight: 44,
                      }}
                    >
                      <span className="truncate">{model.name}</span>
                      {model.category && (
                        <span
                          className="flex-shrink-0 text-xs font-medium rounded-full px-2 py-0.5"
                          style={{
                            color: categoryColors[model.category] ?? "var(--text-tertiary)",
                            background: "var(--accent-subtle)",
                          }}
                        >
                          {model.category}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </NeuCard>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
