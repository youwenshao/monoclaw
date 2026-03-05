"use client";

import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  Zap,
  Brain,
  Code,
  Gauge,
  Package,
  Crown,
  Check,
  ArrowRight,
  Monitor,
  Info,
} from "lucide-react";
import {
  HARDWARE_OPTIONS,
  SOFTWARE_BASE_PRICE_HKD,
  MODEL_CATEGORIES,
  LLM_MODELS,
  BUNDLES,
  type ModelCategory,
} from "@/lib/constants";
import { formatHKD } from "@/lib/stripe";
import { cn } from "@/lib/utils";

const CATEGORY_ICONS: Record<ModelCategory, React.ElementType> = {
  fast: Zap,
  standard: Gauge,
  think: Brain,
  coder: Code,
};

const CATEGORY_LABELS: Record<ModelCategory, string> = {
  fast: "Fast (<2B)",
  standard: "Standard (2-7B)",
  think: "Think (>7B)",
  coder: "Coder (specialists)",
};

const SOFTWARE_FEATURES = [
  "Full OpenClaw agent framework",
  "Industry-specific pre-loaded software",
  "Voice integration (Trilingual: EN/繁中/简中)",
  "WhatsApp/Telegram integration",
  "Automated workflow engine",
  "24/7 autonomous operation",
  "Security hardened (immutable core, sandboxed execution)",
  "Free setup & configuration",
];

function computeAlaCarteTotal(bundleId: string, categoryIds: ModelCategory[]): number {
  let total = 0;
  for (const catId of categoryIds) {
    const cat = MODEL_CATEGORIES.find((c) => c.id === catId);
    if (!cat) continue;

    if (bundleId === "pro_bundle") {
      // Pro bundle offers 1 model per category
      total += cat.priceHkd;
    } else {
      // Max bundle offers all models in all categories
      const modelCount = LLM_MODELS.filter((m) => m.category === catId).length;
      total += cat.priceHkd * modelCount;
    }
  }
  return total;
}

export function PricingContent() {
  const t = useTranslations("pricing");

  const minPrice = SOFTWARE_BASE_PRICE_HKD + HARDWARE_OPTIONS[0].priceHkd;
  const maxPrice =
    SOFTWARE_BASE_PRICE_HKD +
    HARDWARE_OPTIONS[1].priceHkd +
    BUNDLES[1].priceHkd;

  return (
    <div className="pb-20">
      {/* Header */}
      <section className="py-20 text-center">
        <div className="mx-auto max-w-3xl px-6">
          <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
            {t("title")}
          </h1>
          <p className="mt-4 text-lg text-muted-foreground">{t("subtitle")}</p>
        </div>
      </section>

      {/* Software Suite */}
      <section className="bg-muted/30 py-16">
        <div className="mx-auto max-w-4xl px-6">
          <Card className="relative overflow-hidden border-2 border-primary/20">
            <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-primary to-primary/60" />
            <CardHeader className="pt-8 text-center">
              <CardTitle className="text-2xl sm:text-3xl">
                {t("softwareSuite")}
              </CardTitle>
              <CardDescription className="text-base">
                Everything you need to deploy your AI employee
              </CardDescription>
              <div className="mt-6">
                <span className="text-5xl font-bold tracking-tight">
                  {formatHKD(SOFTWARE_BASE_PRICE_HKD)}
                </span>
                <span className="ml-2 text-muted-foreground">one-time</span>
              </div>
            </CardHeader>
            <Separator className="mx-6" />
            <CardContent className="pt-6">
              <p className="mb-4 font-medium">{t("includedFeatures")}</p>
              <div className="grid gap-3 sm:grid-cols-2">
                {SOFTWARE_FEATURES.map((feature) => (
                  <div key={feature} className="flex items-start gap-2">
                    <Check className="mt-0.5 size-4 shrink-0 text-primary" />
                    <span className="text-sm">{feature}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* Hardware */}
      <section className="py-16">
        <div className="mx-auto max-w-5xl px-6">
          <div className="mb-10 text-center">
            <div className="mb-3 inline-flex items-center gap-2">
              <Monitor className="size-5 text-primary" />
              <h2 className="text-2xl font-bold sm:text-3xl">
                {t("hardware")}
              </h2>
            </div>
            <p className="text-muted-foreground">
              Choose the Mac that fits your workspace
            </p>
          </div>

          <div className="mx-auto grid max-w-3xl gap-6 sm:grid-cols-2">
            {HARDWARE_OPTIONS.map((hw) => (
              <Card key={hw.id} className="flex flex-col">
                <CardHeader>
                  <CardTitle className="text-xl">{hw.name}</CardTitle>
                  <CardDescription>
                    {hw.id === "mac_mini_m4"
                      ? "Compact powerhouse"
                      : "All-in-one with display"}
                  </CardDescription>
                  <div className="mt-3">
                    <span className="text-3xl font-bold">
                      ~{formatHKD(hw.priceHkd)}
                    </span>
                  </div>
                </CardHeader>
                <CardContent className="flex-1">
                  <ul className="space-y-2 text-sm">
                    <li className="flex items-center gap-2">
                      <Check className="size-4 shrink-0 text-primary" />
                      {hw.specs.chip}
                    </li>
                    <li className="flex items-center gap-2">
                      <Check className="size-4 shrink-0 text-primary" />
                      {hw.specs.ram}
                    </li>
                    <li className="flex items-center gap-2">
                      <Check className="size-4 shrink-0 text-primary" />
                      {hw.specs.baseSsd}
                    </li>
                    {hw.specs.display && (
                      <li className="flex items-center gap-2">
                        <Check className="size-4 shrink-0 text-primary" />
                        {hw.specs.display}
                      </li>
                    )}
                  </ul>
                </CardContent>
              </Card>
            ))}
          </div>

          <p className="mt-6 flex items-start justify-center gap-2 text-center text-sm text-muted-foreground">
            <Info className="mt-0.5 size-4 shrink-0" />
            Hardware purchased separately from Apple. SSD, color, and Ethernet
            at your discretion.
          </p>
        </div>
      </section>

      {/* Local LLM Add-ons */}
      <section className="bg-muted/30 py-16">
        <div className="mx-auto max-w-5xl px-6">
          <div className="mb-10 text-center">
            <h2 className="text-2xl font-bold sm:text-3xl">{t("addons")}</h2>
            <p className="mt-2 text-muted-foreground">
              Expand capabilities with on-device language models
            </p>
          </div>

          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {MODEL_CATEGORIES.map((cat) => {
              const Icon = CATEGORY_ICONS[cat.id];
              const models = LLM_MODELS.filter((m) => m.category === cat.id);

              return (
                <Card key={cat.id} className="flex flex-col">
                  <CardHeader>
                    <div className="flex items-center gap-2">
                      <Icon className="size-5 text-primary" />
                      <CardTitle className="text-lg">
                        {CATEGORY_LABELS[cat.id]}
                      </CardTitle>
                    </div>
                    <div className="mt-3">
                      <span className="text-2xl font-bold">
                        {formatHKD(cat.priceHkd)}
                      </span>
                      <span className="ml-1 text-sm text-muted-foreground">
                        {t("perModel")}
                      </span>
                    </div>
                  </CardHeader>
                  <Separator className="mx-6" />
                  <CardContent className="flex-1 pt-4">
                    <ul className="space-y-1.5">
                      {models.map((model) => (
                        <li
                          key={model.id}
                          className="flex items-start gap-2 text-sm"
                        >
                          <Check className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" />
                          <span>
                            {model.name}{" "}
                            <span className="text-muted-foreground">
                              ({model.parameterSize})
                            </span>
                          </span>
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>
      </section>

      {/* Bundles */}
      <section className="py-16">
        <div className="mx-auto max-w-5xl px-6">
          <div className="mb-10 text-center">
            <h2 className="text-2xl font-bold sm:text-3xl">{t("bundles")}</h2>
            <p className="mt-2 text-muted-foreground">
              Save big with curated model bundles
            </p>
          </div>

          <div className="mx-auto grid max-w-3xl gap-6 sm:grid-cols-2">
            {BUNDLES.map((bundle) => {
              const alaCarte = computeAlaCarteTotal(bundle.id, bundle.includedCategories);
              const savings = alaCarte - bundle.priceHkd;
              const isMax = bundle.id === "max_bundle";

              return (
                <Card
                  key={bundle.id}
                  className={cn(
                    "relative flex flex-col overflow-hidden",
                    isMax && "border-2 border-primary/30"
                  )}
                >
                  {isMax && (
                    <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-primary to-primary/60" />
                  )}
                  <CardHeader className="pt-8">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        {isMax ? (
                          <Crown className="size-5 text-primary" />
                        ) : (
                          <Package className="size-5 text-primary" />
                        )}
                        <CardTitle className="text-xl">
                          {bundle.name}
                        </CardTitle>
                      </div>
                      <Badge variant={isMax ? "default" : "secondary"}>
                        {isMax ? t("bestValue") : t("popular")}
                      </Badge>
                    </div>
                    <CardDescription className="mt-1">
                      {bundle.description}
                    </CardDescription>
                    <div className="mt-4">
                      <span className="text-4xl font-bold">
                        {formatHKD(bundle.priceHkd)}
                      </span>
                    </div>
                  </CardHeader>
                  <Separator className="mx-6" />
                  <CardContent className="flex-1 pt-4">
                    <ul className="space-y-2">
                      {bundle.features.map((feat) => (
                        <li
                          key={feat}
                          className="flex items-start gap-2 text-sm"
                        >
                          <Check className="mt-0.5 size-4 shrink-0 text-primary" />
                          {feat}
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                  <CardFooter>
                    <p className="text-sm font-medium text-green-600 dark:text-green-400">
                      Save {formatHKD(savings)} vs à la carte
                    </p>
                  </CardFooter>
                </Card>
              );
            })}
          </div>
        </div>
      </section>

      {/* Total Price Calculator */}
      <section className="bg-muted/30 py-16">
        <div className="mx-auto max-w-3xl px-6 text-center">
          <h2 className="text-2xl font-bold sm:text-3xl">Your Investment</h2>
          <div className="mt-8 flex flex-col items-center gap-8 sm:flex-row sm:justify-center sm:gap-12">
            <div>
              <p className="text-sm font-medium uppercase tracking-wider text-muted-foreground">
                {t("startingFrom")}
              </p>
              <p className="mt-1 text-4xl font-bold tracking-tight">
                {formatHKD(minPrice)}
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                Mac mini + Software Suite
              </p>
            </div>
            <Separator
              orientation="vertical"
              className="hidden h-20 sm:block"
            />
            <Separator className="w-16 sm:hidden" />
            <div>
              <p className="text-sm font-medium uppercase tracking-wider text-muted-foreground">
                Up to
              </p>
              <p className="mt-1 text-4xl font-bold tracking-tight">
                {formatHKD(maxPrice)}
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                iMac + Software Suite + Max Bundle
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 text-center">
        <div className="mx-auto max-w-2xl px-6">
          <h2 className="text-2xl font-bold sm:text-3xl">
            Ready to hire your AI employee?
          </h2>
          <p className="mt-3 text-muted-foreground">
            Get started in minutes. One-time payment, no surprises.
          </p>
          <Button size="lg" className="mt-8" asChild>
            <Link href={"/order" as never}>
              Order Now
              <ArrowRight />
            </Link>
          </Button>
        </div>
      </section>
    </div>
  );
}
