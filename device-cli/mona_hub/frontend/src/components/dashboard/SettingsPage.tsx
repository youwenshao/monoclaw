import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  NeuCard,
  NeuButton,
  NeuInput,
  GuidedKeySetup,
  ModelSelector,
  VoiceToggle,
} from "@/components/ui";
import {
  validateKey,
  saveLlmConfig,
  saveMessagingConfig,
  getLlmConfig,
  getDefaultModelStatus,
  getMessagingConfig,
  getRoutingConfig,
  setActiveModel,
  setRoutingMode,
  getInteractionMode,
  toggleVoice,
  getOnboardingState,
  saveProfile,
} from "@/lib/api";
import type { DefaultModelStatus, RoutingConfig, InteractionStatus } from "@/lib/api";
import { LLM_PROVIDERS, MESSAGING_PROVIDERS } from "@/lib/providers";

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

function CpuIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" className="h-5 w-5">
      <rect x="4" y="4" width="16" height="16" rx="2" />
      <rect x="9" y="9" width="6" height="6" />
      <path d="M9 1v3M15 1v3M9 20v3M15 20v3M20 9h3M20 14h3M1 9h3M1 14h3" />
    </svg>
  );
}

function MicIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" className="h-5 w-5">
      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      <line x1="12" y1="19" x2="12" y2="23" />
      <line x1="8" y1="23" x2="16" y2="23" />
    </svg>
  );
}

function UserIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" className="h-5 w-5">
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  );
}

const expandVariants = {
  collapsed: { height: 0, opacity: 0 },
  expanded: { height: "auto", opacity: 1, transition: { duration: 0.3, ease: [0.25, 0.1, 0.25, 1] as const } },
};

interface SectionHeaderProps {
  icon: React.ReactNode;
  title: string;
  open: boolean;
  onToggle: () => void;
  badge?: string;
}

function SectionHeader({ icon, title, open, onToggle, badge }: SectionHeaderProps) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className="flex w-full items-center justify-between border-0 bg-transparent cursor-pointer px-0 py-0"
    >
      <div className="flex items-center gap-3">
        <span className="text-accent">{icon}</span>
        <h3 className="text-lg font-medium text-text-primary">{title}</h3>
        {badge && (
          <span className="text-xs font-medium text-success px-2 py-0.5 rounded-full" style={{ background: "var(--accent-subtle)" }}>
            {badge}
          </span>
        )}
      </div>
      <ChevronIcon open={open} />
    </button>
  );
}

export function SettingsPage() {
  const [openSection, setOpenSection] = useState<string | null>(null);

  const [llmConfig, setLlmConfig] = useState<Record<string, unknown>>({});
  const [messagingConfig, setMessagingConfig] = useState<Record<string, unknown>>({});
  const [routingConfig, setRoutingConfig] = useState<RoutingConfig | null>(null);
  const [interactionStatus, setInteractionStatus] = useState<InteractionStatus | null>(null);
  const [profile, setProfile] = useState<{ name: string; language_pref: string; communication_style: string }>({
    name: "",
    language_pref: "",
    communication_style: "",
  });

  const [expandedLlm, setExpandedLlm] = useState<string | null>(null);
  const [expandedMessaging, setExpandedMessaging] = useState<string | null>(null);
  const [savedProviders, setSavedProviders] = useState<Set<string>>(new Set());
  const [profileSaved, setProfileSaved] = useState(false);
  const [defaultModelStatus, setDefaultModelStatus] = useState<DefaultModelStatus | null>(null);

  useEffect(() => {
    getLlmConfig().then(setLlmConfig).catch(() => {});
    getDefaultModelStatus().then(setDefaultModelStatus).catch(() => {});
    getMessagingConfig().then(setMessagingConfig).catch(() => {});
    getRoutingConfig().then(setRoutingConfig).catch(() => {});
    getInteractionMode().then(setInteractionStatus).catch(() => {});
    getOnboardingState()
      .then((state) => {
        if (state.profile) {
          setProfile({
            name: state.profile.name || "",
            language_pref: state.profile.language_pref || "",
            communication_style: state.profile.communication_style || "",
          });
        }
      })
      .catch(() => {});
  }, []);

  const toggle = (id: string) => setOpenSection((prev) => (prev === id ? null : id));

  const handleLlmComplete = useCallback(
    async (providerId: string, credentials: Record<string, string>) => {
      try {
        await saveLlmConfig(providerId, credentials.api_key);
        setLlmConfig({ provider: providerId, api_key: credentials.api_key });
        getDefaultModelStatus().then(setDefaultModelStatus).catch(() => {});
      } catch {}
      setSavedProviders((prev) => new Set(prev).add(providerId));
    },
    [],
  );

  const handleMessagingComplete = useCallback(
    async (platformId: string, credentials: Record<string, string>) => {
      try {
        await saveMessagingConfig(platformId, credentials);
        setMessagingConfig((prev) => ({ ...prev, [platformId]: credentials }));
      } catch {}
      setSavedProviders((prev) => new Set(prev).add(platformId));
      setExpandedMessaging(null);
    },
    [],
  );

  const handleModelSelect = useCallback(
    async (modelId: string) => {
      try {
        await setActiveModel(modelId);
        setRoutingConfig((prev) =>
          prev ? { ...prev, active_model_id: modelId } : prev,
        );
      } catch {}
    },
    [],
  );

  const handleRoutingToggle = useCallback(
    async (auto: boolean) => {
      try {
        await setRoutingMode(auto);
        setRoutingConfig((prev) =>
          prev ? { ...prev, auto_routing_enabled: auto } : prev,
        );
      } catch {}
    },
    [],
  );

  const handleVoiceToggle = useCallback(
    async (enabled: boolean) => {
      try {
        await toggleVoice(enabled);
        setInteractionStatus((prev) =>
          prev ? { ...prev, voice_enabled: enabled } : prev,
        );
      } catch {}
    },
    [],
  );

  const handleProfileSave = useCallback(async () => {
    try {
      await saveProfile(profile);
      setProfileSaved(true);
      setTimeout(() => setProfileSaved(false), 2000);
    } catch {}
  }, [profile]);

  const activeLlmProvider = (llmConfig as { provider?: string }).provider;
  const connectedMessagingPlatforms = Object.keys(messagingConfig).filter(
    (k) => messagingConfig[k] && typeof messagingConfig[k] === "object",
  );

  return (
    <div className="mx-auto max-w-2xl px-6 py-10 sm:px-8">
      <h1 className="mb-2 text-2xl font-light text-text-primary">Settings</h1>
      <p className="mb-10 text-text-secondary">
        Manage your API keys, messaging services, model routing, and profile.
      </p>

      <div className="flex flex-col gap-4">
        {/* Cloud Language Models */}
        <NeuCard variant="raised" padding="lg">
          <SectionHeader
            icon={<BrainIcon />}
            title="Cloud language models"
            open={openSection === "llm"}
            onToggle={() => toggle("llm")}
            badge={activeLlmProvider ? `${activeLlmProvider} connected` : undefined}
          />

          <AnimatePresence>
            {openSection === "llm" && (
              <motion.div
                variants={expandVariants}
                initial="collapsed"
                animate="expanded"
                exit="collapsed"
                className="overflow-hidden"
              >
                <p className="mt-4 mb-6 text-sm text-text-secondary">
                  Your Mac has local models. Cloud models are optional for heavier tasks.
                </p>
                {defaultModelStatus && (!defaultModelStatus.has_default_model || !defaultModelStatus.gateway_healthy) && defaultModelStatus.message && (
                  <p className="mb-4 text-sm text-text-secondary rounded-md px-3 py-2" style={{ background: "var(--accent-subtle)" }}>
                    {defaultModelStatus.message}
                  </p>
                )}
                <div className="flex flex-col gap-3">
                  {LLM_PROVIDERS.map((provider) => {
                    const isExpanded = expandedLlm === provider.id;
                    const isConnected = activeLlmProvider === provider.id;
                    const justSaved = savedProviders.has(provider.id);

                    return (
                      <div key={provider.id}>
                        <NeuCard
                          variant={isExpanded ? "inset" : "flat"}
                          padding="md"
                          className={`cursor-pointer transition-all ${isExpanded ? "ring-2 ring-accent/50" : ""}`}
                          onClick={() => setExpandedLlm(isExpanded ? null : provider.id)}
                          whileHover={{ scale: 1.01 }}
                          whileTap={{ scale: 0.99 }}
                        >
                          <div className="flex items-center justify-between">
                            <div>
                              <p className="font-medium text-text-primary">{provider.name}</p>
                              <p className="text-sm text-text-secondary">{provider.description}</p>
                            </div>
                            <div className="flex items-center gap-2">
                              {(isConnected || justSaved) && (
                                <span className="text-xs text-success">
                                  {isConnected ? "Connected" : "Saved"} ✓
                                </span>
                              )}
                              <ChevronIcon open={isExpanded} />
                            </div>
                          </div>
                        </NeuCard>

                        <AnimatePresence>
                          {isExpanded && (
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
                                  onSkip={() => setExpandedLlm(null)}
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
              </motion.div>
            )}
          </AnimatePresence>
        </NeuCard>

        {/* Messaging Platforms */}
        <NeuCard variant="raised" padding="lg">
          <SectionHeader
            icon={<MessageIcon />}
            title="Messaging platforms"
            open={openSection === "messaging"}
            onToggle={() => toggle("messaging")}
            badge={
              connectedMessagingPlatforms.length > 0
                ? `${connectedMessagingPlatforms.length} connected`
                : undefined
            }
          />

          <AnimatePresence>
            {openSection === "messaging" && (
              <motion.div
                variants={expandVariants}
                initial="collapsed"
                animate="expanded"
                exit="collapsed"
                className="overflow-hidden"
              >
                <p className="mt-4 mb-6 text-sm text-text-secondary">
                  Let Mona send and receive messages on your behalf.
                </p>

                <div className="flex flex-col gap-3">
                  {MESSAGING_PROVIDERS.map((provider) => {
                    const isExpanded = expandedMessaging === provider.id;
                    const isConnected = connectedMessagingPlatforms.includes(provider.id);
                    const justSaved = savedProviders.has(provider.id);

                    return (
                      <div key={provider.id}>
                        <NeuCard variant="flat" padding="none" className="overflow-hidden">
                          <button
                            type="button"
                            onClick={() => setExpandedMessaging(isExpanded ? null : provider.id)}
                            className="flex w-full items-center justify-between px-6 py-4 text-left border-0 bg-transparent cursor-pointer"
                          >
                            <div>
                              <p className="font-medium text-text-primary">{provider.name}</p>
                              <p className="text-sm text-text-secondary">{provider.description}</p>
                            </div>
                            <div className="flex items-center gap-2">
                              {(isConnected || justSaved) && (
                                <span className="text-xs text-success">
                                  {isConnected ? "Connected" : "Saved"} ✓
                                </span>
                              )}
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
              </motion.div>
            )}
          </AnimatePresence>
        </NeuCard>

        {/* Model Routing */}
        <NeuCard variant="raised" padding="lg">
          <SectionHeader
            icon={<CpuIcon />}
            title="Model routing"
            open={openSection === "routing"}
            onToggle={() => toggle("routing")}
            badge={
              routingConfig?.auto_routing_enabled ? "Auto" : routingConfig?.active_model_id ? "Manual" : undefined
            }
          />

          <AnimatePresence>
            {openSection === "routing" && routingConfig && (
              <motion.div
                variants={expandVariants}
                initial="collapsed"
                animate="expanded"
                exit="collapsed"
                className="overflow-hidden"
              >
                <p className="mt-4 mb-6 text-sm text-text-secondary">
                  Choose how Mona selects which model to use for each request.
                </p>

                <div className="flex items-center gap-4">
                  <span className="text-sm text-text-primary">Active model:</span>
                  <ModelSelector
                    models={routingConfig.available_models}
                    activeModel={routingConfig.active_model_id}
                    autoRoutingEnabled={true}
                    autoRoutingActive={routingConfig.auto_routing_enabled}
                    onSelectModel={handleModelSelect}
                    onToggleAutoRouting={handleRoutingToggle}
                  />
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </NeuCard>

        {/* Voice */}
        <NeuCard variant="raised" padding="lg">
          <SectionHeader
            icon={<MicIcon />}
            title="Voice interaction"
            open={openSection === "voice"}
            onToggle={() => toggle("voice")}
            badge={interactionStatus?.voice_enabled ? "On" : "Off"}
          />

          <AnimatePresence>
            {openSection === "voice" && interactionStatus && (
              <motion.div
                variants={expandVariants}
                initial="collapsed"
                animate="expanded"
                exit="collapsed"
                className="overflow-hidden"
              >
                <p className="mt-4 mb-6 text-sm text-text-secondary">
                  Enable or disable Mona's voice input and output.
                </p>

                <div className="flex items-center justify-between">
                  <span className="text-sm text-text-primary">
                    {interactionStatus.voice_enabled
                      ? "Voice is enabled — Mona can listen and speak"
                      : "Voice is disabled — text only"}
                  </span>
                  <VoiceToggle
                    enabled={interactionStatus.voice_enabled}
                    onToggle={handleVoiceToggle}
                  />
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </NeuCard>

        {/* Profile */}
        <NeuCard variant="raised" padding="lg">
          <SectionHeader
            icon={<UserIcon />}
            title="Profile"
            open={openSection === "profile"}
            onToggle={() => toggle("profile")}
          />

          <AnimatePresence>
            {openSection === "profile" && (
              <motion.div
                variants={expandVariants}
                initial="collapsed"
                animate="expanded"
                exit="collapsed"
                className="overflow-hidden"
              >
                <p className="mt-4 mb-6 text-sm text-text-secondary">
                  Help Mona personalise interactions to your preferences.
                </p>

                <div className="flex flex-col gap-4">
                  <NeuInput
                    label="Name"
                    placeholder="Your name"
                    value={profile.name}
                    onChange={(e) => setProfile((p) => ({ ...p, name: e.target.value }))}
                  />
                  <NeuInput
                    label="Preferred language"
                    placeholder="e.g. English, Cantonese, Mandarin"
                    value={profile.language_pref}
                    onChange={(e) => setProfile((p) => ({ ...p, language_pref: e.target.value }))}
                  />
                  <NeuInput
                    label="Communication style"
                    placeholder="e.g. Formal, Casual, Concise"
                    value={profile.communication_style}
                    onChange={(e) => setProfile((p) => ({ ...p, communication_style: e.target.value }))}
                  />

                  <div className="flex items-center gap-3 pt-2">
                    <NeuButton variant="primary" size="sm" onClick={handleProfileSave}>
                      Save profile
                    </NeuButton>
                    {profileSaved && (
                      <motion.span
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="text-sm text-success"
                      >
                        Saved ✓
                      </motion.span>
                    )}
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </NeuCard>
      </div>
    </div>
  );
}
