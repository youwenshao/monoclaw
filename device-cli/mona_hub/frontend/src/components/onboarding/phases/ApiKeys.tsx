import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useNavigate } from "react-router-dom";
import {
  PageTransition,
  FadeUp,
  NeuCard,
  NeuButton,
  GuidedKeySetup,
  type ProviderConfig,
} from "@/components/ui";
import { validateKey, saveLlmConfig, saveMessagingConfig } from "@/lib/api";
import { childVariants } from "@/lib/animations";

const LLM_PROVIDERS: ProviderConfig[] = [
  {
    id: "deepseek",
    name: "DeepSeek",
    description: "High-performance reasoning and coding models.",
    steps: [
      { title: "Create account", body: "Sign up at platform.deepseek.com", link: { label: "Open DeepSeek", url: "https://platform.deepseek.com" } },
      { title: "Add payment", body: "Go to /usage and add a payment method." },
      { title: "Create API key", body: "Navigate to /api_keys and generate a new key (starts with sk-).", link: { label: "API Keys", url: "https://platform.deepseek.com/api_keys" } },
      { title: "Paste below", body: "Copy the key and paste it into the field below." },
    ],
    fields: [{ key: "api_key", label: "API Key", placeholder: "sk-..." }],
    validationErrors: { "401": "Key not recognised (starts with sk-)", "402": "Needs payment method", network: "Can't reach servers" },
  },
  {
    id: "kimi",
    name: "Kimi K2.5",
    description: "Moonshot AI's multimodal model with 256K context — great for long documents.",
    steps: [
      { title: "Create account", body: "Sign up at platform.moonshot.cn", link: { label: "Open Moonshot", url: "https://platform.moonshot.cn" } },
      { title: "Top up credits", body: "Go to /console/billing and add credits.", link: { label: "Billing", url: "https://platform.moonshot.cn/console/billing" } },
      { title: "Generate key", body: "Navigate to /console/api-keys and create a new key.", link: { label: "API Keys", url: "https://platform.moonshot.cn/console/api-keys" } },
      { title: "Paste below", body: "Copy the key and paste it into the field below." },
    ],
    fields: [{ key: "api_key", label: "API Key", placeholder: "Your Moonshot API key" }],
    validationErrors: { "401": "Key not recognised", "402": "Insufficient credits", network: "Can't reach servers" },
  },
  {
    id: "glm5",
    name: "GLM-5",
    description: "Zhipu AI's flagship 745B model — state-of-the-art coding and reasoning.",
    steps: [
      { title: "Create account", body: "Sign up at z.ai/model-api", link: { label: "Open Zhipu AI", url: "https://z.ai/model-api" } },
      { title: "Add credits", body: "Go to z.ai/manage-apikey/billing and top up.", link: { label: "Billing", url: "https://z.ai/manage-apikey/billing" } },
      { title: "Create key", body: "Generate a key at z.ai/manage-apikey/apikey-list.", link: { label: "API Keys", url: "https://z.ai/manage-apikey/apikey-list" } },
      { title: "Paste below", body: "Copy the key and paste it into the field below." },
    ],
    fields: [{ key: "api_key", label: "API Key", placeholder: "Your Zhipu AI API key" }],
    validationErrors: { "401": "Key not recognised", "402": "Needs credits", network: "Can't reach servers" },
  },
];

const MESSAGING_PROVIDERS: ProviderConfig[] = [
  {
    id: "whatsapp",
    name: "WhatsApp",
    description: "Let Mona send and receive WhatsApp messages on your behalf via Twilio.",
    steps: [
      { title: "Create Twilio account", body: "Sign up at twilio.com.", link: { label: "Open Twilio", url: "https://www.twilio.com/console" } },
      { title: "Meta Business account", body: "Set up a Meta Business account for WhatsApp." },
      { title: "Register sender", body: "Register a WhatsApp sender in the Twilio Console." },
      { title: "Copy credentials", body: "Find your Account SID and Auth Token on the Twilio dashboard." },
      { title: "Paste below", body: "Enter both credentials in the fields below." },
    ],
    fields: [
      { key: "account_sid", label: "Account SID", placeholder: "AC..." },
      { key: "auth_token", label: "Auth Token", placeholder: "Your auth token", type: "password" },
    ],
    validationErrors: { "401": "Invalid credentials", network: "Can't reach Twilio" },
  },
  {
    id: "telegram",
    name: "Telegram",
    description: "Let Mona send and receive Telegram messages through a dedicated bot.",
    steps: [
      { title: "Find @BotFather", body: "Open Telegram and search for @BotFather.", link: { label: "Open BotFather", url: "https://t.me/BotFather" } },
      { title: "Create bot", body: "Send /newbot, then choose a name and username ending in 'bot'." },
      { title: "Copy token", body: "BotFather will give you a bot token — copy it." },
      { title: "Paste below", body: "Enter the token in the field below." },
    ],
    fields: [
      { key: "bot_token", label: "Bot Token", placeholder: "7123456789:AAHdqTcvCH1v...", type: "password" },
    ],
    validationErrors: { "401": "Token not recognised", network: "Can't reach Telegram" },
  },
  {
    id: "discord",
    name: "Discord",
    description: "Let Mona join your Discord server and respond to messages.",
    steps: [
      { title: "Developer Portal", body: "Open the Discord Developer Portal.", link: { label: "Open Portal", url: "https://discord.com/developers/applications" } },
      { title: "Create application", body: "Click 'New Application' and give it a name." },
      { title: "Get bot token", body: "Go to the Bot tab, reset the token, and copy it." },
      { title: "Invite bot", body: "Use OAuth2 to generate an invite link and add the bot to your server." },
      { title: "Paste below", body: "Enter the bot token in the field below." },
    ],
    fields: [
      { key: "bot_token", label: "Bot Token", placeholder: "Your Discord bot token", type: "password" },
    ],
    validationErrors: { "401": "Token not recognised", network: "Can't reach Discord" },
  },
  {
    id: "email",
    name: "Email",
    description: "Let Mona send and receive emails on your behalf via SMTP.",
    steps: [
      { title: "SMTP settings", body: "Find your email provider's SMTP server and port." },
      { title: "App password", body: "Generate an app-specific password (required for Gmail, Outlook, etc.)." },
      { title: "Paste below", body: "Enter your SMTP details in the fields below." },
    ],
    fields: [
      { key: "smtp_server", label: "SMTP Server", placeholder: "smtp.gmail.com" },
      { key: "smtp_port", label: "Port", placeholder: "587" },
      { key: "email", label: "Email", placeholder: "you@example.com" },
      { key: "password", label: "Password", placeholder: "App password", type: "password" },
    ],
    validationErrors: { "401": "Authentication failed", network: "Can't reach mail server" },
  },
];

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
  expanded: { height: "auto", opacity: 1, transition: { duration: 0.3, ease: [0.25, 0.1, 0.25, 1] } },
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
        <NeuButton onClick={() => navigate("/welcome/tools")}>
          Continue
        </NeuButton>
        <NeuButton variant="ghost" size="sm" onClick={() => navigate("/welcome/tools")}>
          Skip all
        </NeuButton>
      </motion.div>
    </PageTransition>
  );
}
