import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useNavigate } from "react-router-dom";
import {
  PageTransition,
  FadeUp,
  NeuCard,
  NeuButton,
  GuidedKeySetup,
} from "@/components/ui";
import { validateKey, saveLlmConfig, saveMessagingConfig } from "@/lib/api";
import { childVariants } from "@/lib/animations";
import { LLM_PROVIDERS, MESSAGING_PROVIDERS } from "@/lib/providers";

function BrainIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" className="h-5 w-5">
      <path d="M12 2a4 4 0 0 1 4 4c0 1.1-.9 2-2 2h-4a2 2 0 0 1-2-2 4 4 0 0 1 4-4z" />
      <path d="M8 8v2a6 6 0 0 0 8 0V8" />
      <path d="M6 14a6 6 0 0 0 12 0" />
      <line x1="12" y1="14" x2="12" y2="22" />
      <line x1="9" y1="18" x2="15" y2="18" />
    </svg>
  );
}

function MessageIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" className="h-5 w-5">
      <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
    </svg>
  );
}

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <motion.svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-4 w-4 text-text-tertiary"
      animate={{ rotate: open ? 180 : 0 }}
      transition={{ duration: 0.2 }}
    >
      <polyline points="6 9 12 15 18 9" />
    </motion.svg>
  );
}

const expandVariants = {
  collapsed: { height: 0, opacity: 0 },
  expanded: { height: "auto", opacity: 1, transition: { duration: 0.3, ease: [0.25, 0.1, 0.25, 1] as const } },
};

export function ApiKeys() {
  const navigate = useNavigate();
  const [selectedLlm, setSelectedLlm] = useState<string | null>(null);
  const [expandedMessaging, setExpandedMessaging] = useState<string | null>(null);
  const [completedProviders, setCompletedProviders] = useState<Set<string>>(new Set());

  const handleLlmComplete = useCallback(
    async (providerId: string, credentials: Record<string, string>) => {
      try {
        await validateKey(providerId, credentials);
        await saveLlmConfig(providerId, credentials.api_key);
      } catch {}
      setCompletedProviders((prev) => new Set(prev).add(providerId));
    },
    [],
  );

  const handleMessagingComplete = useCallback(
    async (platformId: string, credentials: Record<string, string>) => {
      try {
        await validateKey(platformId, credentials);
        await saveMessagingConfig(platformId, credentials);
      } catch {}
      setCompletedProviders((prev) => new Set(prev).add(platformId));
      setExpandedMessaging(null);
    },
    [],
  );

  return (
    <PageTransition>
      <FadeUp>
        <h2 className="mb-2 text-2xl font-light text-text-primary">
          Connect external services
        </h2>
        <p className="mb-8 text-text-secondary">
          Optional — everything essential already works locally. You can always set these up later by asking Mona.
        </p>
      </FadeUp>

      {/* Section 1: Cloud LLM Providers */}
      <FadeUp className="mb-10">
        <div className="mb-4 flex items-center gap-2">
          <span className="text-accent"><BrainIcon /></span>
          <h3 className="text-lg font-medium text-text-primary">Cloud language models</h3>
        </div>
        <p className="mb-6 text-sm text-text-secondary">
          Your Mac has local models. Cloud models are optional for heavier tasks.
        </p>

        <div className="flex flex-col gap-3">
          {LLM_PROVIDERS.map((provider) => {
            const isSelected = selectedLlm === provider.id;
            const isCompleted = completedProviders.has(provider.id);

            return (
              <div key={provider.id}>
                <NeuCard
                  variant={isSelected ? "inset" : "raised"}
                  padding="md"
                  className={`cursor-pointer transition-all ${isSelected ? "ring-2 ring-accent/50" : ""}`}
                  onClick={() => setSelectedLlm(isSelected ? null : provider.id)}
                  whileHover={{ scale: 1.01 }}
                  whileTap={{ scale: 0.99 }}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium text-text-primary">{provider.name}</p>
                      <p className="text-sm text-text-secondary">{provider.description}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      {isCompleted && <span className="text-xs text-success">Saved ✓</span>}
                      <div
                        className="flex h-5 w-5 items-center justify-center rounded-full border-2 transition-colors"
                        style={{
                          borderColor: isSelected ? "var(--accent)" : "var(--text-tertiary)",
                          background: isSelected ? "var(--accent)" : "transparent",
                        }}
                      >
                        {isSelected && (
                          <div className="h-2 w-2 rounded-full bg-white" />
                        )}
                      </div>
                    </div>
                  </div>
                </NeuCard>

                <AnimatePresence>
                  {isSelected && (
                    <motion.div
                      variants={expandVariants}
                      initial="collapsed"
                      animate="expanded"
                      exit="collapsed"
                      className="overflow-hidden"
                    >
                      <div className="px-2 pt-4 pb-2">
                        <GuidedKeySetup
                          config={provider}
                          onComplete={(creds) => handleLlmComplete(provider.id, creds)}
                          onSkip={() => setSelectedLlm(null)}
                          onValidate={(creds) => validateKey(provider.id, creds)}
                        />
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            );
          })}
        </div>
      </FadeUp>

      {/* Section 2: Messaging Platforms */}
      <FadeUp className="mb-10">
        <div className="mb-4 flex items-center gap-2">
          <span className="text-accent"><MessageIcon /></span>
          <h3 className="text-lg font-medium text-text-primary">Messaging platforms</h3>
        </div>
        <p className="mb-6 text-sm text-text-secondary">
          Let Mona send and receive messages on your behalf.
        </p>

        <div className="flex flex-col gap-3">
          {MESSAGING_PROVIDERS.map((provider) => {
            const isExpanded = expandedMessaging === provider.id;
            const isCompleted = completedProviders.has(provider.id);

            return (
              <div key={provider.id}>
                <NeuCard variant="raised" padding="none" className="overflow-hidden">
                  <button
                    onClick={() => setExpandedMessaging(isExpanded ? null : provider.id)}
                    className="flex w-full items-center justify-between px-6 py-4 text-left"
                  >
                    <div>
                      <p className="font-medium text-text-primary">{provider.name}</p>
                      <p className="text-sm text-text-secondary">{provider.description}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      {isCompleted && <span className="text-xs text-success">Saved ✓</span>}
                      <ChevronIcon open={isExpanded} />
                    </div>
                  </button>

                  <AnimatePresence>
                    {isExpanded && (
                      <motion.div
                        variants={expandVariants}
                        initial="collapsed"
                        animate="expanded"
                        exit="collapsed"
                        className="overflow-hidden"
                      >
                        <div className="border-t border-white/5 px-6 py-4">
                          <GuidedKeySetup
                            config={provider}
                            onComplete={(creds) => handleMessagingComplete(provider.id, creds)}
                            onSkip={() => setExpandedMessaging(null)}
                            onValidate={(creds) => validateKey(provider.id, creds)}
                          />
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </NeuCard>
              </div>
            );
          })}
        </div>
      </FadeUp>

      {/* Navigation */}
      <motion.div
        variants={childVariants}
        initial="initial"
        animate="enter"
        className="mt-10 flex flex-col items-center gap-3"
      >
        <NeuButton onClick={() => navigate("/welcome/voice")}>
          Continue
        </NeuButton>
        <NeuButton variant="ghost" size="sm" onClick={() => navigate("/welcome/voice")}>
          Skip all
        </NeuButton>
      </motion.div>
    </PageTransition>
  );
}
