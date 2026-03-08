"use client";

import { motion } from "framer-motion";
import { useTranslations } from "next-intl";
import {
  Monitor,
  Cpu,
  Bot,
  Shield,
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
  ArrowRight,
  Check,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { Link } from "@/i18n/navigation";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  HARDWARE_OPTIONS,
  TOOL_SUITES,
  SOFTWARE_BASE_PRICE_HKD,
} from "@/lib/constants";
import { formatHKD } from "@/lib/stripe";

const fadeUp = {
  initial: { opacity: 0, y: 24 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-60px" },
  transition: { duration: 0.5, ease: "easeOut" as const },
};

const staggerContainer = {
  initial: {},
  whileInView: { transition: { staggerChildren: 0.1 } },
  viewport: { once: true, margin: "-60px" },
};

const TOOL_ICONS: Record<string, LucideIcon> = {
  "real-estate": Building2,
  immigration: Briefcase,
  "fnb-hospitality": UtensilsCrossed,
  accounting: Calculator,
  legal: Scale,
  "medical-dental": Stethoscope,
  construction: HardHat,
  "import-export": Ship,
  academic: GraduationCap,
  "vibe-coder": Code,
  solopreneur: Store,
  student: BookOpen,
};

const HOW_IT_WORKS_STEPS = [
  {
    icon: Monitor,
    title: "Choose Your Hardware",
    description: "Pick a Mac mini or iMac M4 — we handle the rest.",
  },
  {
    icon: Cpu,
    title: "We Set It Up",
    description:
      "OpenClaw installed with all 12 tool suites, tested, and ready.",
  },
  {
    icon: Bot,
    title: "Mona Gets to Work",
    description:
      "Your AI assistant starts automating tasks from day one.",
  },
  {
    icon: Shield,
    title: "You Stay in Control",
    description:
      "Monitor everything through a clean, real-time dashboard.",
  },
];

export function LandingContent() {
  const t = useTranslations("hero");

  const totalStartingPrice =
    SOFTWARE_BASE_PRICE_HKD + HARDWARE_OPTIONS[0].priceHkd;

  return (
    <div className="flex flex-col">
      {/* ── Hero ── */}
      <section className="relative overflow-hidden py-24 sm:py-32 lg:py-40">
        <div className="pointer-events-none absolute inset-0 -z-10 bg-gradient-to-b from-primary/5 via-transparent to-transparent" />
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <motion.div
            className="mx-auto max-w-3xl text-center"
            {...fadeUp}
          >
            <Badge variant="secondary" className="mb-6">
              Powered by local LLMs on Apple Silicon
            </Badge>
            <h1 className="text-5xl font-bold tracking-tight sm:text-6xl lg:text-7xl">
              {t("title")}
            </h1>
            <p className="mt-6 text-lg leading-relaxed text-muted-foreground sm:text-xl">
              {t("subtitle")}
            </p>
            <div className="mt-10 flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
              <Button size="lg" className="h-12 px-8 text-base" asChild>
                <Link href={"/order" as never}>
                  {t("cta")}
                  <ArrowRight className="ml-1 size-4" />
                </Link>
              </Button>
              <Button
                variant="outline"
                size="lg"
                className="h-12 px-8 text-base"
                asChild
              >
                <Link href={"/pricing" as never}>
                  {t("secondaryCta")}
                </Link>
              </Button>
            </div>
          </motion.div>
        </div>
      </section>

      {/* ── How It Works ── */}
      <section className="py-24 sm:py-32">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <motion.div className="mx-auto mb-16 max-w-2xl text-center" {...fadeUp}>
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
              How It Works
            </h2>
            <p className="mt-4 text-lg text-muted-foreground">
              From unboxing to automation in four simple steps.
            </p>
          </motion.div>

          <motion.div
            className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4"
            {...staggerContainer}
          >
            {HOW_IT_WORKS_STEPS.map((step, i) => {
              const Icon = step.icon;
              return (
                <motion.div key={step.title} {...fadeUp}>
                  <Card className="relative h-full border-0 bg-muted/40 shadow-none">
                    <CardHeader>
                      <div className="mb-2 flex items-center gap-3">
                        <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-bold text-primary-foreground">
                          {i + 1}
                        </span>
                        <Icon className="size-5 text-primary" />
                      </div>
                      <CardTitle className="text-lg">{step.title}</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <CardDescription className="text-sm leading-relaxed">
                        {step.description}
                      </CardDescription>
                    </CardContent>
                  </Card>
                </motion.div>
              );
            })}
          </motion.div>
        </div>
      </section>

      {/* ── Hardware Showcase ── */}
      <section className="border-y bg-muted/30 py-24 sm:py-32">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <motion.div className="mx-auto mb-16 max-w-2xl text-center" {...fadeUp}>
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
              Premium Apple Hardware
            </h2>
            <p className="mt-4 text-lg text-muted-foreground">
              Choose the Mac that fits your workspace. Both run Mona
              beautifully.
            </p>
          </motion.div>

          <div className="mx-auto grid max-w-4xl gap-8 lg:grid-cols-2">
            {HARDWARE_OPTIONS.map((hw) => (
              <motion.div key={hw.id} {...fadeUp}>
                <Card className="h-full">
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <div>
                        <CardTitle className="text-xl">{hw.name}</CardTitle>
                        <CardDescription className="mt-1">
                          Starting from{" "}
                          <span className="font-semibold text-foreground">
                            ~{formatHKD(hw.priceHkd)}
                          </span>
                        </CardDescription>
                      </div>
                      <Monitor className="size-8 text-muted-foreground/60" />
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="flex items-center gap-2 text-sm">
                      <Check className="size-4 text-primary" />
                      <span>{hw.specs.chip}</span>
                    </div>
                    <div className="flex items-center gap-2 text-sm">
                      <Check className="size-4 text-primary" />
                      <span>{hw.specs.ram}</span>
                    </div>
                    <div className="flex items-center gap-2 text-sm">
                      <Check className="size-4 text-primary" />
                      <span>{hw.specs.baseSsd}</span>
                    </div>
                    {hw.specs.display && (
                      <div className="flex items-center gap-2 text-sm">
                        <Check className="size-4 text-primary" />
                        <span>{hw.specs.display}</span>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Tool Suites Grid ── */}
      <section className="py-24 sm:py-32">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <motion.div className="mx-auto mb-16 max-w-2xl text-center" {...fadeUp}>
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
              12 Tool Suites, One Mac
            </h2>
            <p className="mt-4 text-lg text-muted-foreground">
              Every Mona Mac ships with all 12 tool suites. Mona auto-routes
              your requests to the right tool based on context.
            </p>
          </motion.div>

          <motion.div
            className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
            {...staggerContainer}
          >
            {TOOL_SUITES.map((suite) => {
              const Icon = TOOL_ICONS[suite.id] || Bot;
              return (
                <motion.div key={suite.id} {...fadeUp}>
                  <Link
                    href={`/industries/${suite.id}` as never}
                    className="group block h-full"
                  >
                    <Card className="h-full transition-shadow duration-200 group-hover:shadow-md">
                      <CardHeader>
                        <div className="mb-1 flex items-center gap-3">
                          <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
                            <Icon className="size-5" />
                          </div>
                          <Badge variant="secondary" className="text-xs">
                            {suite.tools.length} tools
                          </Badge>
                        </div>
                        <CardTitle className="text-base">
                          {suite.name}
                        </CardTitle>
                      </CardHeader>
                      <CardContent>
                        <p className="text-sm leading-relaxed text-muted-foreground">
                          {suite.description}
                        </p>
                      </CardContent>
                    </Card>
                  </Link>
                </motion.div>
              );
            })}
          </motion.div>
        </div>
      </section>

      {/* ── CTA ── */}
      <section className="border-t bg-gradient-to-b from-primary/5 to-transparent py-24 sm:py-32">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <motion.div className="mx-auto max-w-2xl text-center" {...fadeUp}>
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
              Ready to meet your AI employee?
            </h2>
            <p className="mt-4 text-lg text-muted-foreground">
              Starting from{" "}
              <span className="font-semibold text-foreground">
                {formatHKD(totalStartingPrice)}
              </span>{" "}
              — hardware + software, everything included.
            </p>
            <div className="mt-10">
              <Button size="lg" className="h-12 px-8 text-base" asChild>
                <Link href={"/order" as never}>
                  Get Started
                  <ArrowRight className="ml-1 size-4" />
                </Link>
              </Button>
            </div>
          </motion.div>
        </div>
      </section>
    </div>
  );
}
