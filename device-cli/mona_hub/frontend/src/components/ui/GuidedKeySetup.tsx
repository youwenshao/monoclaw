import { useState, useCallback } from "react";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import { NeuButton } from "./NeuButton";
import { NeuCard } from "./NeuCard";
import { NeuInput } from "./NeuInput";

export interface ProviderConfig {
  id: string;
  name: string;
  description: string;
  steps: Array<{
    title: string;
    body: string;
    link?: { label: string; url: string };
  }>;
  fields: Array<{
    key: string;
    label: string;
    placeholder: string;
    type?: string;
  }>;
  validationErrors: Record<string, string>;
}

type ValidationState = "idle" | "checking" | "valid" | "invalid";

interface GuidedKeySetupProps {
  config: ProviderConfig;
  onComplete: (credentials: Record<string, string>) => void;
  onSkip: () => void;
  onValidate?: (credentials: Record<string, string>) => Promise<{ valid: boolean; error?: string }>;
}

export function GuidedKeySetup({
  config,
  onComplete,
  onSkip,
  onValidate,
}: GuidedKeySetupProps) {
  const reducedMotion = useReducedMotion();
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(config.fields.map((f) => [f.key, ""]))
  );
  const [validation, setValidation] = useState<ValidationState>("idle");
  const [errorMsg, setErrorMsg] = useState("");

  const allFilled = config.fields.every((f) => values[f.key].trim().length > 0);

  const handleChange = useCallback(
    (key: string, value: string) => {
      setValues((prev) => ({ ...prev, [key]: value }));
      if (validation !== "idle") {
        setValidation("idle");
        setErrorMsg("");
      }
    },
    [validation]
  );

  const handleVerify = useCallback(async () => {
    setValidation("checking");
    setErrorMsg("");

    try {
      if (onValidate) {
        const result = await onValidate(values);
        if (result.valid) {
          setValidation("valid");
          setTimeout(() => onComplete(values), 800);
        } else {
          setValidation("invalid");
          setErrorMsg(result.error || "Invalid credentials. Try again.");
        }
      } else {
        await new Promise((r) => setTimeout(r, 1200));
        setValidation("valid");
        setTimeout(() => onComplete(values), 800);
      }
    } catch (err) {
      setValidation("invalid");
      setErrorMsg(err instanceof Error ? err.message : "Verification failed. Try again.");
    }
  }, [values, onValidate, onComplete]);

  const borderForState = (): string | undefined => {
    if (validation === "checking")
      return "0 0 0 2px var(--accent)";
    if (validation === "valid")
      return "0 0 0 2px var(--success)";
    if (validation === "invalid")
      return "0 0 0 2px var(--error)";
    return undefined;
  };

  return (
    <div className="flex flex-col gap-8">
      {/* Provider header */}
      <div>
        <h2 className="text-xl font-semibold text-text-primary font-sans">
          {config.name}
        </h2>
        <p className="mt-1 text-sm text-text-secondary">{config.description}</p>
      </div>

      {/* Numbered steps */}
      <div className="flex flex-col gap-3">
        {config.steps.map((step, i) => (
          <NeuCard key={i} variant="flat" padding="md" radius="md">
            <div className="flex gap-3">
              <div
                className="flex-shrink-0 flex items-center justify-center rounded-full font-mono text-xs font-bold text-accent"
                style={{
                  width: 28,
                  height: 28,
                  background: "var(--accent-subtle)",
                }}
              >
                {i + 1}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-text-primary">
                  {step.title}
                </p>
                <p className="text-sm text-text-secondary mt-0.5">
                  {step.body}
                </p>
                {step.link && (
                  <a
                    href={step.link.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 mt-2 text-sm font-medium text-accent hover:underline"
                  >
                    {step.link.label}
                    <span aria-hidden="true">&rarr;</span>
                  </a>
                )}
              </div>
            </div>
          </NeuCard>
        ))}
      </div>

      {/* Key inputs */}
      <div
        className="flex flex-col gap-4 rounded-xl p-4 transition-shadow duration-200"
        style={{ boxShadow: borderForState() }}
      >
        {config.fields.map((field) => (
          <NeuInput
            key={field.key}
            label={field.label}
            placeholder={field.placeholder}
            type={field.type ?? "text"}
            value={values[field.key]}
            onChange={(e) => handleChange(field.key, e.target.value)}
            className="font-mono"
            autoComplete="off"
          />
        ))}

        {/* Validation feedback */}
        <AnimatePresence mode="wait">
          {validation === "checking" && (
            <motion.p
              key="checking"
              initial={reducedMotion ? false : { opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="text-sm text-accent"
            >
              Verifying…
            </motion.p>
          )}
          {validation === "valid" && (
            <motion.p
              key="valid"
              initial={reducedMotion ? false : { opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="text-sm text-success flex items-center gap-1.5"
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                <path d="M3 8.5L6.5 12L13 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              Key verified
            </motion.p>
          )}
          {validation === "invalid" && (
            <motion.p
              key="invalid"
              initial={reducedMotion ? false : { opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="text-sm text-error"
            >
              {errorMsg || "Invalid key. Try again."}
            </motion.p>
          )}
        </AnimatePresence>
      </div>

      {/* Actions */}
      <div className="flex flex-col gap-3">
        <NeuButton
          variant="primary"
          disabled={!allFilled || validation === "checking"}
          loading={validation === "checking"}
          onClick={handleVerify}
        >
          {validation === "invalid" ? "Try again" : "Verify"}
        </NeuButton>

        <button
          type="button"
          onClick={onSkip}
          className="text-sm text-text-tertiary hover:text-text-secondary transition-colors text-center py-2 cursor-pointer border-0 bg-transparent font-sans"
          style={{ minHeight: 44 }}
        >
          Skip — you can always set this up later by asking Mona
        </button>
      </div>
    </div>
  );
}
