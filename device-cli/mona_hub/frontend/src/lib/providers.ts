import type { ProviderConfig } from "@/components/ui";

export const LLM_PROVIDERS: ProviderConfig[] = [
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

export const MESSAGING_PROVIDERS: ProviderConfig[] = [
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
