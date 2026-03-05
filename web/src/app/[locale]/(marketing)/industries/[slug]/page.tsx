import type { Metadata } from "next";
import { setRequestLocale } from "next-intl/server";
import { notFound } from "next/navigation";
import { Link } from "@/i18n/navigation";
import { INDUSTRY_VERTICALS, CLIENT_PERSONAS } from "@/lib/constants";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Building2,
  Briefcase,
  UtensilsCrossed,
  Calculator,
  Scale,
  Stethoscope,
  HardHat,
  Ship,
  GraduationCap,
  Code,
  Store,
  BookOpen,
  AlertCircle,
  Check,
  ArrowRight,
  Sparkles,
} from "lucide-react";

const industryIcons: Record<string, React.ReactNode> = {
  "real-estate": <Building2 className="h-8 w-8" />,
  immigration: <Briefcase className="h-8 w-8" />,
  "fnb-hospitality": <UtensilsCrossed className="h-8 w-8" />,
  accounting: <Calculator className="h-8 w-8" />,
  legal: <Scale className="h-8 w-8" />,
  "medical-dental": <Stethoscope className="h-8 w-8" />,
  construction: <HardHat className="h-8 w-8" />,
  "import-export": <Ship className="h-8 w-8" />,
  "academic-researcher": <GraduationCap className="h-8 w-8" />,
  "vibe-coder": <Code className="h-8 w-8" />,
  solopreneur: <Store className="h-8 w-8" />,
  "curious-student": <BookOpen className="h-8 w-8" />,
};

const INDUSTRY_DETAILS: Record<
  string,
  {
    painPoints: string[];
    software: { name: string; description: string }[];
    valueProposition: string;
  }
> = {
  "real-estate": {
    painPoints: [
      "Manually copy-pasting property descriptions across 5+ platforms",
      "15+ back-and-forth messages per viewing to coordinate schedules",
      "Collecting and verifying documents for lease agreements",
      "Manual tracking of commission splits and referral fees",
    ],
    software: [
      {
        name: "PropertyGPT",
        description:
          "Fine-tuned RAG system with Hong Kong building database including floor areas, school nets, and MTR walking times",
      },
      {
        name: "ListingSync Agent",
        description:
          "Multi-agent system that rewrites property descriptions for each platform's SEO requirements and auto-posts",
      },
      {
        name: "TenancyDoc Automator",
        description:
          "Generates HK SAR standard tenancy agreements, stamp duty calculations, and inventory checklists",
      },
      {
        name: "ViewingBot",
        description:
          "WhatsApp integration that checks calendars and books viewings without human intervention",
      },
    ],
    valueProposition:
      "One-click listing distribution, automated tenancy paperwork, 24/7 viewing coordination",
  },
  immigration: {
    painPoints: [
      "Manually checking 50+ documents per visa application for completeness",
      "Copying client data into 12+ different IRD and Immigration Department forms",
      "Monitoring changes to GEP, ASMTP, TTPS, QMAS schemes across government gazettes",
      "Clients constantly calling for application status updates",
    ],
    software: [
      {
        name: "VisaDoc OCR",
        description:
          "Specialized document parser for HKID, passports, bank statements with Chinese/English bilingual support",
      },
      {
        name: "FormAutoFill",
        description:
          "Populates Immigration Department forms (ID990A, ID990B) from client database with 99.4% accuracy",
      },
      {
        name: "PolicyWatcher",
        description:
          "Scrapes HK Government gazettes daily and alerts when visa criteria change",
      },
      {
        name: "ClientPortal Bot",
        description:
          "WhatsApp/Telegram bot providing real-time application status without consultant intervention",
      },
    ],
    valueProposition:
      "Automated document verification, real-time policy alerts, zero-touch client updates",
  },
  "fnb-hospitality": {
    painPoints: [
      "Managing bookings across WhatsApp, phone, OpenRice, inline, and Instagram DMs",
      "15-20% of bookings result in no-shows with manual confirmation calls",
      "Manual paper lists for walk-in queue management during peak hours",
      "No centralized record of VIP customer preferences and allergies",
    ],
    software: [
      {
        name: "TableMaster AI",
        description:
          "Unified inbox for WhatsApp/Instagram/OpenRice bookings with automatic conflict detection",
      },
      {
        name: "NoShowShield",
        description:
          "Automated WhatsApp confirmations 24hrs ahead with auto-fill from waitlist on cancellations",
      },
      {
        name: "QueueBot",
        description:
          "Digital queuing system with SMS alerts when tables are ready, integrated with POS",
      },
      {
        name: "SommelierMemory",
        description:
          "CRM logging customer preferences like dietary requirements and celebration dates",
      },
    ],
    valueProposition:
      "Zero double-bookings, automated no-show prevention, digital queue management",
  },
  accounting: {
    painPoints: [
      "Manually typing invoice details from WhatsApp photos into accounting software",
      "Matching 500+ monthly transactions across HSBC, Hang Seng, and virtual banks",
      "Tracking 3,000+ client deadlines for Profits Tax and Employer's Returns",
      "Converting multi-currency transactions at correct exchange rates",
    ],
    software: [
      {
        name: "InvoiceOCR Pro",
        description:
          "Extracts line items from Chinese/English invoices with ABSS/Xero/QuickBooks integration",
      },
      {
        name: "ReconcileAgent",
        description:
          "Auto-matches bank feeds to ledger entries and flags discrepancies for human review",
      },
      {
        name: "TaxCalendar Bot",
        description:
          "Tracks HK IRD deadlines per client with automated reminders 7/30/60 days before",
      },
      {
        name: "FXTracker",
        description:
          "Auto-logs exchange rates for multi-currency transactions and generates FX reports",
      },
    ],
    valueProposition:
      "Automated invoice processing, hands-off bank reconciliation, zero missed tax deadlines",
  },
  legal: {
    painPoints: [
      "Paralegals spending 40% of time on due diligence and contract clause checking",
      "Sifting through 10,000+ emails in litigation for privileged communications",
      "Manually calendaring court deadlines and limitation periods",
      "2-hour initial consultations gathering basic information",
    ],
    software: [
      {
        name: "LegalDoc Analyzer",
        description:
          "Clause extraction for HK standard contracts with unusual term flagging",
      },
      {
        name: "DiscoveryAssistant",
        description:
          "E-discovery tool identifying privileged communications and auto-categorizing documents",
      },
      {
        name: "DeadlineGuardian",
        description:
          "Integration with HK e-Litigation system, auto-calculates limitation periods",
      },
      {
        name: "IntakeBot",
        description:
          "WhatsApp/WeChat bot collecting client details, conflict checking, and scheduling",
      },
    ],
    valueProposition:
      "AI-powered document review, automated deadline management, zero-conflict client intake",
  },
  "medical-dental": {
    painPoints: [
      "Phone lines jammed 9am-12pm with patients hanging up after 10 rings",
      "25% of dental appointments missed with last-minute cancellations",
      "Doctors handwriting notes while nurses spend 2 hours/day transcribing",
      "Manual prescription refill verification for chronic medications",
    ],
    software: [
      {
        name: "ClinicScheduler",
        description:
          "24/7 WhatsApp booking with real-time availability, integrates with HKMA electronic health records",
      },
      {
        name: "MedReminder Bot",
        description:
          "SMS/WhatsApp medication reminders and refill requests with photo upload",
      },
      {
        name: "ScribeAI",
        description:
          "Voice-to-text clinical notes in English/Traditional Chinese, auto-structured for medical records",
      },
      {
        name: "InsuranceAgent",
        description:
          "Pre-authorization checking with Bupa, AXA, and Cigna with co-pay estimates",
      },
    ],
    valueProposition:
      "24/7 appointment booking, automated scribing, instant insurance verification",
  },
  construction: {
    painPoints: [
      "Manual checking of Buildings Department submission approvals",
      "Daily site safety forms and Smart Site Safety System documentation",
      "Tenants WhatsApping defect photos logged manually into Excel",
      "Scheduling 15+ subcontractors across 5 sites via WhatsApp",
    ],
    software: [
      {
        name: "PermitTracker",
        description:
          "Scrapes BD approval status and alerts when submissions progress",
      },
      {
        name: "SafetyForm Bot",
        description:
          "Daily automated safety checks with photo upload and SSSS compliance logging",
      },
      {
        name: "DefectsManager",
        description:
          "WhatsApp photo auto-logging with location tagging, generates contractor work orders",
      },
      {
        name: "SiteCoordinator",
        description:
          "Multi-agent scheduling system optimizing contractor routes across HK sites",
      },
    ],
    valueProposition:
      "Automated BD permit tracking, digital safety compliance, photo-based defect logging",
  },
  "import-export": {
    painPoints: [
      "Manual HS code classification and copying shipping details into 8+ forms",
      "Chasing factories in Shenzhen/Dongguan for production updates via WeChat",
      "Matching arrival notices with actual warehouse stock",
      "Generating invoices in USD while settling in CNH and accounting in HKD",
    ],
    software: [
      {
        name: "TradeDoc AI",
        description:
          "Auto-classifies HS codes and generates HKTID export/import licenses and commercial invoices",
      },
      {
        name: "SupplierBot",
        description:
          "WeChat-integrated agent pinging factories for updates and translating responses",
      },
      {
        name: "StockReconcile",
        description:
          "Matches shipping manifests with warehouse receipts, flags quantity mismatches",
      },
      {
        name: "FXInvoice",
        description:
          "Auto-generates multi-currency invoices with hedging suggestions for large exposures",
      },
    ],
    valueProposition:
      "Automated customs paperwork, 24/7 supplier chasing, real-time inventory reconciliation",
  },
  "academic-researcher": {
    painPoints: [
      "Reading 200+ papers for systematic literature reviews",
      "Formatting citations for various academic standards",
      "Translating Chinese academic sources to English summaries",
      "Tracking grant application deadlines across multiple bodies",
    ],
    software: [
      {
        name: "PaperSieve",
        description:
          "RAG system indexing papers, answers specific research questions with citations",
      },
      {
        name: "CiteBot",
        description:
          "Auto-formats references for APA/Harvard/MLA and checks DOI accuracy",
      },
      {
        name: "TranslateAssist",
        description:
          "Academic Chinese-to-English translation preserving technical terminology",
      },
      {
        name: "GrantTracker",
        description:
          "Monitors RGC, ITF, and NSFC deadlines and auto-populates application forms",
      },
    ],
    valueProposition:
      "AI-powered literature review, auto-formatted citations, grant deadline tracking",
  },
  "vibe-coder": {
    painPoints: [
      "Writing boilerplate CRUD code for HK-specific integrations",
      "Debugging CSS for mobile-responsive designs",
      "Writing README documentation and API docs",
      "Managing GitHub Issues and PR descriptions",
    ],
    software: [
      {
        name: "CodeQwen-9B",
        description:
          "Local coding specialist model fine-tuned for Python/JavaScript/React",
      },
      {
        name: "HKDevKit",
        description:
          "Pre-built connectors for FPS, Octopus API, and GovHK data",
      },
      {
        name: "DocuWriter",
        description:
          "Auto-generates technical documentation from code comments",
      },
      {
        name: "GitAssistant",
        description:
          "Drafts PR descriptions, suggests reviewers, and writes release notes",
      },
    ],
    valueProposition:
      "Local coding assistant, HK-specific dev tools, zero API costs",
  },
  solopreneur: {
    painPoints: [
      "Replying to 'Are you open today?' WhatsApp messages at 11pm",
      "Calculating staff MPF contributions manually each month",
      "Posting the same promotion to Instagram, Facebook, and WhatsApp Status",
      "Tracking which supplier owes credit notes",
    ],
    software: [
      {
        name: "BizOwner OS",
        description:
          "Unified dashboard integrating WhatsApp Business, POS data, and basic accounting",
      },
      {
        name: "MPFCalc",
        description:
          "Auto-calculates 5% MPF contributions (HK$1,500 cap) and generates remittance statements",
      },
      {
        name: "SocialSync",
        description:
          "One-click post distribution across IG/FB/WhatsApp with HK-style CTA optimization",
      },
      {
        name: "SupplierLedger",
        description:
          "Tracks payables/receivables by supplier with auto-sent monthly statements",
      },
    ],
    valueProposition:
      "Unified business dashboard, automated MPF, one-click social posting",
  },
  "curious-student": {
    painPoints: [
      "Formatting thesis documents with proper TOC and citations",
      "Summarizing 50-page case studies for exams",
      "Practicing coding interview questions without guidance",
      "Managing job application tracking across 50+ companies",
    ],
    software: [
      {
        name: "StudyBuddy",
        description:
          "Local document Q&A for course materials including PDFs, slides, and readings",
      },
      {
        name: "InterviewPrep",
        description:
          "Coding practice with local explanations and weak area tracking",
      },
      {
        name: "JobTracker",
        description:
          "Parses job descriptions from CTgoodjobs, JobsDB, LinkedIn and matches against CV",
      },
      {
        name: "ThesisFormatter",
        description:
          "Auto-generates table of contents, figure lists, and university thesis formatting",
      },
    ],
    valueProposition:
      "Private study assistant, interview prep, job tracking, thesis formatting",
  },
};

function findIndustry(slug: string) {
  const vertical = INDUSTRY_VERTICALS.find((v) => v.slug === slug);
  if (vertical) return vertical;
  const persona = CLIENT_PERSONAS.find((p) => p.slug === slug);
  return persona ?? null;
}

export async function generateStaticParams() {
  const allSlugs = [
    ...INDUSTRY_VERTICALS.map((v) => v.slug),
    ...CLIENT_PERSONAS.map((p) => p.slug),
  ];
  return allSlugs.map((slug) => ({ slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const industry = findIndustry(slug);
  if (!industry) return {};
  return {
    title: `${industry.name} — MonoClaw`,
  };
}

export default async function IndustryDetailPage({
  params,
}: {
  params: Promise<{ locale: string; slug: string }>;
}) {
  const { locale, slug } = await params;
  setRequestLocale(locale);

  const industry = findIndustry(slug);
  if (!industry) notFound();

  const details = INDUSTRY_DETAILS[slug];
  if (!details) notFound();

  return (
    <div className="mx-auto max-w-5xl px-4 py-20 sm:px-6 lg:px-8">
      {/* Hero */}
      <div className="mb-16 rounded-2xl bg-primary/5 px-8 py-12 text-center">
        <div className="mb-4 flex justify-center text-primary">
          {industryIcons[slug]}
        </div>
        <h1 className="mb-3 text-4xl font-bold tracking-tight">
          {industry.name}
        </h1>
        <p className="mx-auto max-w-2xl text-lg text-muted-foreground">
          {industry.tagline}
        </p>
      </div>

      {/* Pain Points */}
      <section className="mb-16">
        <h2 className="mb-8 text-2xl font-semibold">Pain Points We Solve</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          {details.painPoints.map((point) => (
            <div
              key={point}
              className="flex items-start gap-3 rounded-lg border p-4"
            >
              <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-red-500" />
              <p className="text-sm text-muted-foreground">{point}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Software Stack */}
      <section className="mb-16">
        <h2 className="mb-8 text-2xl font-semibold">Pre-loaded Software</h2>
        <div className="grid gap-6 sm:grid-cols-2">
          {details.software.map((tool) => (
            <Card key={tool.name}>
              <CardHeader>
                <div className="mb-2 flex items-center gap-2">
                  <Check className="h-5 w-5 text-primary" />
                  <CardTitle className="text-lg">{tool.name}</CardTitle>
                </div>
                <CardDescription>{tool.description}</CardDescription>
              </CardHeader>
            </Card>
          ))}
        </div>
      </section>

      {/* Value Proposition */}
      <section className="mb-16">
        <div className="flex items-start gap-4 rounded-2xl border border-primary/20 bg-primary/5 p-8">
          <Sparkles className="mt-1 h-6 w-6 shrink-0 text-primary" />
          <div>
            <h3 className="mb-2 text-lg font-semibold">Value Proposition</h3>
            <p className="text-muted-foreground">
              {details.valueProposition}
            </p>
          </div>
        </div>
      </section>

      {/* CTA */}
      <div className="text-center">
        <Button asChild size="lg">
          <Link href={"/order" as never}>
            Get Started with {industry.name}
            <ArrowRight className="ml-2 h-4 w-4" />
          </Link>
        </Button>
      </div>
    </div>
  );
}
