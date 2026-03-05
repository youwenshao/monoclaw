"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import { useCheckout } from "@/lib/checkout-context";
import {
  HARDWARE_OPTIONS,
  SOFTWARE_BASE_PRICE_HKD,
  LLM_MODELS,
  MODEL_CATEGORIES,
  BUNDLES,
  INDUSTRY_VERTICALS,
  CLIENT_PERSONAS,
} from "@/lib/constants";
import { formatHKD } from "@/lib/stripe";
import { CheckoutSteps } from "@/components/checkout-steps";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { ArrowLeft, CreditCard, Loader2 } from "lucide-react";

export function ReviewStep() {
  const t = useTranslations("order");
  const { order, setCurrentStep } = useCheckout();
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  const hardware = HARDWARE_OPTIONS.find((h) => h.id === order.hardwareType);
  const bundle = order.addons.bundle
    ? BUNDLES.find((b) => b.id === order.addons.bundle)
    : null;
  const selectedModels = order.addons.models.map((id) =>
    LLM_MODELS.find((m) => m.id === id)
  ).filter(Boolean);

  const industry = INDUSTRY_VERTICALS.find((i) => i.slug === order.industry) ||
    CLIENT_PERSONAS.find((p) => p.slug === order.industry);

  const personas = order.personas.map((s) =>
    CLIENT_PERSONAS.find((p) => p.slug === s)
  ).filter(Boolean);

  let addonsTotal = 0;
  if (bundle) {
    addonsTotal = bundle.priceHkd;
  } else {
    for (const model of selectedModels) {
      if (!model) continue;
      const cat = MODEL_CATEGORIES.find((c) => c.id === model.category);
      if (cat) addonsTotal += cat.priceHkd;
    }
  }

  const softwareTotal = SOFTWARE_BASE_PRICE_HKD + addonsTotal;

  function handleBack() {
    setCurrentStep(3);
    router.push("/order/industry" as never);
  }

  async function handleCheckout() {
    setLoading(true);
    try {
      const res = await fetch("/api/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          hardwareType: order.hardwareType,
          hardwareConfig: order.hardwareConfig,
          addons: order.addons,
          industry: order.industry,
          personas: order.personas,
        }),
      });
      const data = await res.json();
      if (data.url) {
        window.location.href = data.url;
      }
    } catch (err) {
      console.error("Checkout error:", err);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <CheckoutSteps currentStep={4} />
      <h1 className="mb-2 text-3xl font-bold">{t("title")}</h1>
      <p className="mb-8 text-muted-foreground">{t("step4")}</p>

      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Hardware</CardTitle>
          </CardHeader>
          <CardContent>
            {hardware ? (
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">{hardware.name}</p>
                  <p className="text-sm text-muted-foreground">
                    {hardware.specs.chip} &middot; {hardware.specs.ram}
                  </p>
                </div>
                <p className="text-sm text-muted-foreground">
                  ~{formatHKD(hardware.priceHkd)} (purchased from Apple)
                </p>
              </div>
            ) : (
              <p className="text-muted-foreground">No hardware selected</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Software & Add-ons</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between">
              <span>OpenClaw Software Suite</span>
              <span className="font-medium">{formatHKD(SOFTWARE_BASE_PRICE_HKD)}</span>
            </div>
            {bundle && (
              <div className="flex items-center justify-between">
                <span>{bundle.name}</span>
                <span className="font-medium">{formatHKD(bundle.priceHkd)}</span>
              </div>
            )}
            {!bundle && selectedModels.length > 0 && selectedModels.map((model) => {
              if (!model) return null;
              const cat = MODEL_CATEGORIES.find((c) => c.id === model.category);
              return (
                <div key={model.id} className="flex items-center justify-between text-sm">
                  <span>{model.name} {model.parameterSize}</span>
                  <span>{cat ? formatHKD(cat.priceHkd) : ""}</span>
                </div>
              );
            })}
            <Separator />
            <div className="flex items-center justify-between text-lg font-bold">
              <span>{t("total")}</span>
              <span>{formatHKD(softwareTotal)}</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Industry Configuration</CardTitle>
          </CardHeader>
          <CardContent>
            {industry && (
              <div className="mb-2">
                <p className="font-medium">{industry.name}</p>
                <p className="text-sm text-muted-foreground">
                  {industry.softwareStack.join(", ")}
                </p>
              </div>
            )}
            {personas.length > 0 && (
              <div className="mt-3">
                <p className="text-sm text-muted-foreground">Additional profiles:</p>
                <p className="text-sm">{personas.map((p) => p?.name).join(", ")}</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="mt-8 flex justify-between">
        <Button variant="outline" size="lg" onClick={handleBack}>
          <ArrowLeft className="mr-2 h-4 w-4" /> Back
        </Button>
        <Button size="lg" onClick={handleCheckout} disabled={loading || !order.hardwareType}>
          {loading ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <CreditCard className="mr-2 h-4 w-4" />
          )}
          {t("pay")} &middot; {formatHKD(softwareTotal)}
        </Button>
      </div>
    </>
  );
}
