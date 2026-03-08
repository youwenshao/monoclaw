export const LOCALES = ["en", "zh-hant", "zh-hans"] as const;
export type Locale = (typeof LOCALES)[number];
export const DEFAULT_LOCALE: Locale = "en";

export const COMPANY = {
  name: "MonoClaw",
  legalName: "Sentimento Technologies Limited",
  website: "www.monoclaw.app",
  openclawWebsite: "www.openclaw.ai",
  location: "Hong Kong",
} as const;

export const SOFTWARE_BASE_PRICE_HKD = 39_999;

export interface HardwareOption {
  id: string;
  name: string;
  priceHkd: number;
  appleStoreUrl: string;
  specs: {
    chip: string;
    ram: string;
    baseSsd: string;
    display?: string;
  };
  configurableOptions: string[];
}

export const HARDWARE_OPTIONS: HardwareOption[] = [
  {
    id: "mac_mini_m4",
    name: "Mac mini M4",
    priceHkd: 5_000,
    appleStoreUrl: "https://www.apple.com/hk/shop/buy-mac/mac-mini",
    specs: {
      chip: "Apple M4",
      ram: "16GB Unified Memory",
      baseSsd: "256GB SSD",
    },
    configurableOptions: ["SSD storage", "Ethernet"],
  },
  {
    id: "imac_m4",
    name: "iMac M4",
    priceHkd: 10_000,
    appleStoreUrl: "https://www.apple.com/hk/shop/buy-mac/imac",
    specs: {
      chip: "Apple M4",
      ram: "16GB Unified Memory",
      baseSsd: "256GB SSD",
      display: '24" 4.5K Retina',
    },
    configurableOptions: ["SSD storage", "Color", "Ethernet"],
  },
];

export type ModelCategory = "fast" | "standard" | "think" | "coder";

export interface LlmModel {
  id: string;
  name: string;
  parameterSize: string;
  category: ModelCategory;
  description: string;
}

export const LLM_MODELS: LlmModel[] = [
  { id: "qwen-3.5-0.8b", name: "Qwen-3.5", parameterSize: "0.8B", category: "fast", description: "Ultra-fast responses for simple tasks" },
  { id: "deepseek-r1-1.5b", name: "DeepSeek-R1", parameterSize: "1.5B", category: "fast", description: "Reasoning model for quick analysis" },
  { id: "llama-3.1-1b", name: "Llama-3.1", parameterSize: "1B", category: "fast", description: "Meta's efficient small model" },
  { id: "smollm2-1.7b", name: "SmolLM2", parameterSize: "1.7B", category: "fast", description: "Compact yet capable" },
  { id: "gemma-3-1b", name: "Gemma-3", parameterSize: "1B", category: "fast", description: "Google's lightweight model" },
  { id: "deepseek-r1-7b", name: "DeepSeek-R1", parameterSize: "7B", category: "standard", description: "Strong reasoning at medium size" },
  { id: "llama-3.2-3b", name: "Llama-3.2", parameterSize: "3B", category: "standard", description: "Balanced performance model" },
  { id: "mistral-7b", name: "Mistral", parameterSize: "7B", category: "standard", description: "Efficient European AI model" },
  { id: "ministral-3b", name: "Ministral", parameterSize: "3B", category: "standard", description: "Mistral's compact variant" },
  { id: "gemma-3-4b", name: "Gemma-3", parameterSize: "4B", category: "standard", description: "Google's mid-range model" },
  { id: "qwen-3.5-9b", name: "Qwen-3.5", parameterSize: "9B", category: "think", description: "Deep reasoning and analysis" },
  { id: "glm-4-9b", name: "GLM-4", parameterSize: "9B", category: "think", description: "Zhipu's advanced thinking model" },
  { id: "llama-3.1-8b", name: "Llama-3.1", parameterSize: "8B", category: "think", description: "Meta's powerful reasoning model" },
  { id: "ministral-8b", name: "Ministral", parameterSize: "8B", category: "think", description: "Mistral's thinking-optimized model" },
  { id: "qwen-2.5-coder-7b", name: "Qwen-2.5-Coder", parameterSize: "7B", category: "coder", description: "Code generation specialist" },
  { id: "deepseek-coder-6.7b", name: "DeepSeek-Coder", parameterSize: "6.7B", category: "coder", description: "Programming-focused model" },
];

export interface ModelCategoryInfo {
  id: ModelCategory;
  name: string;
  priceHkd: number;
  description: string;
  parameterRange: string;
}

export const MODEL_CATEGORIES: ModelCategoryInfo[] = [
  { id: "fast", name: "Fast", priceHkd: 99, description: "Sub-2B models for instant responses", parameterRange: "<2B" },
  { id: "standard", name: "Standard", priceHkd: 399, description: "2-7B models for everyday tasks", parameterRange: "2-7B" },
  { id: "think", name: "Think", priceHkd: 599, description: "8B+ models for complex reasoning", parameterRange: ">7B" },
  { id: "coder", name: "Coder", priceHkd: 399, description: "Coding specialist models", parameterRange: "6-7B" },
];

export interface Bundle {
  id: string;
  name: string;
  priceHkd: number;
  description: string;
  includedCategories: ModelCategory[];
  features: string[];
}

export const BUNDLES: Bundle[] = [
  {
    id: "pro_bundle",
    name: "Pro Bundle",
    priceHkd: 999,
    description: "One Fast + One Think + One Coder model",
    includedCategories: ["fast", "think", "coder"],
    features: [
      "1 Fast model of your choice",
      "1 Think model of your choice",
      "1 Coder model of your choice",
      "3 models total",
    ],
  },
  {
    id: "max_bundle",
    name: "Max Bundle",
    priceHkd: 1_999,
    description: "All models + automated routing",
    includedCategories: ["fast", "standard", "think", "coder"],
    features: [
      "All 16 supported models",
      "Automated complexity routing",
      "System auto-selects optimal model",
      "Best value for power users",
    ],
  },
];

export interface ToolSuite {
  id: string;
  name: string;
  description: string;
  tools: string[];
}

export const TOOL_SUITES: ToolSuite[] = [
  { id: "real-estate", name: "Real Estate & Property", description: "One-click listing distribution, automated tenancy paperwork, 24/7 viewing coordination", tools: ["PropertyGPT", "ListingSync Agent", "TenancyDoc Automator", "ViewingBot"] },
  { id: "immigration", name: "Immigration Consulting", description: "Automated document verification, real-time policy alerts, zero-touch client updates", tools: ["VisaDoc OCR", "FormAutoFill", "PolicyWatcher", "ClientPortal Bot"] },
  { id: "fnb-hospitality", name: "F&B & Hospitality", description: "Zero double-bookings, automated no-show prevention, digital queue management", tools: ["TableMaster AI", "NoShowShield", "QueueBot", "SommelierMemory"] },
  { id: "accounting", name: "Accounting & Bookkeeping", description: "Automated invoice processing, hands-off bank reconciliation, zero missed tax deadlines", tools: ["InvoiceOCR Pro", "ReconcileAgent", "TaxCalendar Bot", "FXTracker"] },
  { id: "legal", name: "Legal & Professional Services", description: "AI-powered document review, automated deadline management, zero-conflict client intake", tools: ["LegalDoc Analyzer", "DiscoveryAssistant", "DeadlineGuardian", "IntakeBot"] },
  { id: "medical-dental", name: "Medical & Dental Clinics", description: "24/7 appointment booking, automated scribing, instant insurance verification", tools: ["ClinicScheduler", "MedReminder Bot", "ScribeAI", "InsuranceAgent"] },
  { id: "construction", name: "Construction & Property Management", description: "Automated BD permit tracking, digital safety compliance, photo-based defect logging", tools: ["PermitTracker", "SafetyForm Bot", "DefectsManager", "SiteCoordinator"] },
  { id: "import-export", name: "Import/Export & Trading", description: "Automated customs paperwork, 24/7 supplier chasing, real-time inventory reconciliation", tools: ["TradeDoc AI", "SupplierBot", "StockReconcile", "FXInvoice"] },
  { id: "academic", name: "Academic Researcher", description: "AI-powered literature review, auto-formatted citations, grant deadline tracking", tools: ["PaperSieve", "CiteBot", "TranslateAssist", "GrantTracker"] },
  { id: "vibe-coder", name: "Vibe Coder", description: "Local coding assistant, HK-specific dev tools, zero API costs", tools: ["CodeQwen-9B", "HKDevKit", "DocuWriter", "GitAssistant"] },
  { id: "solopreneur", name: "Solopreneur", description: "Unified business dashboard, automated MPF, one-click social posting", tools: ["BizOwner OS", "MPFCalc", "SocialSync", "SupplierLedger"] },
  { id: "student", name: "Student", description: "Private study assistant, interview prep, job tracking, thesis formatting", tools: ["StudyBuddy", "InterviewPrep", "JobTracker", "ThesisFormatter"] },
];

interface OrderStatusConfig {
  status: string;
  label: string;
  step: number;
}

export const ORDER_STATUS_FLOW: OrderStatusConfig[] = [
  { status: "pending_payment", label: "Pending Payment", step: 1 },
  { status: "paid", label: "Payment Confirmed", step: 2 },
  { status: "hardware_pending", label: "Awaiting Hardware", step: 3 },
  { status: "hardware_received", label: "Hardware Received", step: 4 },
  { status: "provisioning", label: "Setting Up", step: 5 },
  { status: "testing", label: "Quality Testing", step: 6 },
  { status: "ready", label: "Ready to Ship", step: 7 },
  { status: "shipped", label: "Shipped", step: 8 },
  { status: "delivered", label: "Delivered", step: 9 },
  { status: "completed", label: "Completed", step: 10 },
];
