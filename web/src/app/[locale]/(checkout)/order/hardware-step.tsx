"use client";

import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import { useCheckout } from "@/lib/checkout-context";
import { HARDWARE_OPTIONS } from "@/lib/constants";
import { formatHKD } from "@/lib/stripe";
import { CheckoutSteps } from "@/components/checkout-steps";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Monitor, Check, ArrowRight, Info } from "lucide-react";
import type { HardwareType } from "@/types/database";

export function HardwareStep() {
  const t = useTranslations("order");
  const { order, setHardware, setCurrentStep } = useCheckout();

  const router = useRouter();

  function handleSelect(hwId: string) {
    const hw = HARDWARE_OPTIONS.find((h) => h.id === hwId);
    if (hw) setHardware(hwId as HardwareType);
  }

  function handleNext() {
    if (order.hardwareType) {
      setCurrentStep(2);
      router.push("/order/addons" as never);
    }
  }

  return (
    <>
      <CheckoutSteps currentStep={1} />
      <h1 className="mb-2 text-3xl font-bold">{t("title")}</h1>
      <p className="mb-8 text-muted-foreground">{t("step1")}</p>

      <div className="mb-6 grid gap-6 sm:grid-cols-2">
        {HARDWARE_OPTIONS.map((hw) => (
          <Card
            key={hw.id}
            className={`cursor-pointer transition-all ${
              order.hardwareType === hw.id
                ? "border-primary ring-2 ring-primary/20"
                : "hover:border-primary/50"
            }`}
            onClick={() => handleSelect(hw.id)}
          >
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-xl">{hw.name}</CardTitle>
                {hw.specs.display && <Badge variant="secondary">Display</Badge>}
              </div>
              <p className="text-2xl font-bold text-primary">
                ~{formatHKD(hw.priceHkd)}
              </p>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2 text-sm">
                <li className="flex items-center gap-2">
                  <Check className="h-4 w-4 text-primary" /> {hw.specs.chip}
                </li>
                <li className="flex items-center gap-2">
                  <Check className="h-4 w-4 text-primary" /> {hw.specs.ram}
                </li>
                <li className="flex items-center gap-2">
                  <Check className="h-4 w-4 text-primary" /> {hw.specs.baseSsd}
                </li>
                {hw.specs.display && (
                  <li className="flex items-center gap-2">
                    <Monitor className="h-4 w-4 text-primary" /> {hw.specs.display}
                  </li>
                )}
              </ul>
              {hw.configurableOptions.length > 0 && (
                <p className="mt-4 text-xs text-muted-foreground">
                  Configurable: {hw.configurableOptions.join(", ")}
                </p>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="mb-8 flex items-start gap-2 rounded-lg border border-border bg-muted/30 p-4">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
        <div className="text-sm text-muted-foreground">
          <p>{t("hardwareNote")}</p>
          <p className="mt-1">{t("configNote")}</p>
        </div>
      </div>

      <div className="flex justify-end">
        <Button
          size="lg"
          onClick={handleNext}
          disabled={!order.hardwareType}
        >
          Continue <ArrowRight className="ml-2 h-4 w-4" />
        </Button>
      </div>
    </>
  );
}
