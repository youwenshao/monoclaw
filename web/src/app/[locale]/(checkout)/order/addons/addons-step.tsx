"use client";

import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import { useCheckout } from "@/lib/checkout-context";
import { LLM_MODELS, MODEL_CATEGORIES, BUNDLES } from "@/lib/constants";
import { formatHKD } from "@/lib/stripe";
import { CheckoutSteps } from "@/components/checkout-steps";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { ArrowRight, ArrowLeft, Package, Crown, Zap, Gauge, Brain, Code } from "lucide-react";
import type { ModelCategory } from "@/lib/constants";

const categoryIcons: Record<ModelCategory, React.ReactNode> = {
  fast: <Zap className="h-5 w-5" />,
  standard: <Gauge className="h-5 w-5" />,
  think: <Brain className="h-5 w-5" />,
  coder: <Code className="h-5 w-5" />,
};

export function AddonsStep() {
  const t = useTranslations("order");
  const tPricing = useTranslations("pricing");
  const { order, setAddons, setCurrentStep } = useCheckout();
  const router = useRouter();

  const selectedModels = order.addons.models;
  const selectedBundle = order.addons.bundle;

  function toggleModel(modelId: string) {
    const model = LLM_MODELS.find((m) => m.id === modelId);
    if (!model) return;

    const current = [...selectedModels];
    const idx = current.indexOf(modelId);

    if (idx >= 0) {
      current.splice(idx, 1);
    } else {
      if (selectedBundle === "pro_bundle") {
        // Pro bundle: check if we already have a model from this category
        const sameCategory = current.find((id) => {
          const m = LLM_MODELS.find((x) => x.id === id);
          return m?.category === model.category;
        });
        if (sameCategory) {
          // Replace existing model in this category
          const sameIdx = current.indexOf(sameCategory);
          current.splice(sameIdx, 1);
        }
        // Max 3 models for Pro bundle
        if (current.length >= 3) {
          return; // Should not happen with replacement logic above
        }
      }
      current.push(modelId);
    }
    setAddons({ models: current, bundle: selectedBundle });
  }

  function selectBundle(bundleId: string | null) {
    if (selectedBundle === bundleId) {
      setAddons({ models: [], bundle: null });
    } else {
      // When switching to Pro bundle, clear models as they need to be selected specifically
      // When switching to Max bundle, clear models as it includes all
      setAddons({ models: [], bundle: bundleId });
    }
  }

  function getModelStatus(modelId: string, categoryId: ModelCategory) {
    const isSelected = selectedModels.includes(modelId);
    const isDisabled = !!selectedBundle && selectedBundle !== "pro_bundle";

    if (selectedBundle === "pro_bundle") {
      const hasOtherInCategory = selectedModels.some((id) => {
        const m = LLM_MODELS.find((x) => x.id === id);
        return m?.category === categoryId && id !== modelId;
      });
      return { isSelected, isDisabled: false, hasOtherInCategory };
    }

    return { isSelected, isDisabled, hasOtherInCategory: false };
  }

  function handleBack() {
    setCurrentStep(1);
    router.push("/order" as never);
  }

  function handleNext() {
    if (selectedBundle === "pro_bundle" && selectedModels.length < 3) {
      // Optional: alert or validation for Pro bundle
    }
    setCurrentStep(3);
    router.push("/order/industry" as never);
  }

  return (
    <>
      <CheckoutSteps currentStep={2} />
      <h1 className="mb-2 text-3xl font-bold">{t("title")}</h1>
      <p className="mb-8 text-muted-foreground">{t("step2")}</p>

      <div className="mb-10">
        <h2 className="mb-4 text-xl font-semibold">{tPricing("bundles")}</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          {BUNDLES.map((bundle) => (
            <Card
              key={bundle.id}
              className={`cursor-pointer transition-all ${
                selectedBundle === bundle.id
                  ? "border-primary ring-2 ring-primary/20"
                  : "hover:border-primary/50"
              }`}
              onClick={() => selectBundle(bundle.id)}
            >
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {bundle.id === "pro_bundle" ? (
                      <Package className="h-5 w-5 text-primary" />
                    ) : (
                      <Crown className="h-5 w-5 text-primary" />
                    )}
                    <CardTitle className="text-lg">{bundle.name}</CardTitle>
                  </div>
                  <Badge
                    variant={bundle.id === "max_bundle" ? "default" : "secondary"}
                  >
                    {bundle.id === "pro_bundle"
                      ? tPricing("popular")
                      : tPricing("bestValue")}
                  </Badge>
                </div>
                <p className="text-2xl font-bold text-primary">
                  {formatHKD(bundle.priceHkd)}
                </p>
                <CardDescription>{bundle.description}</CardDescription>
              </CardHeader>
              <CardContent>
                <ul className="space-y-1 text-sm">
                  {bundle.features.map((f) => (
                    <li
                      key={f}
                      className="flex items-center gap-2 text-muted-foreground"
                    >
                      <span className="h-1.5 w-1.5 rounded-full bg-primary" />
                      {f}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      <div className="mb-10">
        <h2 className="mb-4 text-xl font-semibold">
          {selectedBundle === "pro_bundle"
            ? "Select Your 3 Models"
            : tPricing("addons")}{" "}
          <span className="text-sm font-normal text-muted-foreground">
            {selectedBundle === "pro_bundle"
              ? "(Pick one from each category)"
              : "(a-la-carte)"}
          </span>
        </h2>
        {MODEL_CATEGORIES.map((cat) => {
          const models = LLM_MODELS.filter((m) => m.category === cat.id);
          // Standard models are not part of Pro bundle
          const isCategoryInPro = ["fast", "think", "coder"].includes(cat.id);
          const isProMode = selectedBundle === "pro_bundle";

          return (
            <div
              key={cat.id}
              className={`mb-6 ${
                isProMode && !isCategoryInPro ? "opacity-50 grayscale" : ""
              }`}
            >
              <div className="mb-3 flex items-center gap-2">
                {categoryIcons[cat.id]}
                <h3 className="font-medium">{cat.name}</h3>
                {!isProMode && (
                  <Badge variant="outline">
                    {formatHKD(cat.priceHkd)} {tPricing("perModel")}
                  </Badge>
                )}
                <span className="text-xs text-muted-foreground">
                  {cat.parameterRange}
                </span>
              </div>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {models.map((model) => {
                  const { isSelected, isDisabled } = getModelStatus(
                    model.id,
                    cat.id
                  );
                  const isModelDisabled =
                    isDisabled || (isProMode && !isCategoryInPro);

                  return (
                    <label
                      key={model.id}
                      className={`flex cursor-pointer items-center gap-3 rounded-lg border p-3 transition-colors ${
                        isSelected
                          ? "border-primary bg-primary/5"
                          : "hover:bg-muted/50"
                      } ${isModelDisabled ? "pointer-events-none opacity-50" : ""}`}
                    >
                      <Checkbox
                        checked={isSelected}
                        onCheckedChange={() => toggleModel(model.id)}
                        disabled={isModelDisabled}
                      />
                      <div>
                        <p className="text-sm font-medium">
                          {model.name}{" "}
                          <span className="text-muted-foreground">
                            {model.parameterSize}
                          </span>
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {model.description}
                        </p>
                      </div>
                    </label>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>

      <p className="mb-6 text-center text-sm text-muted-foreground">
        Add-ons are optional. You can skip this step.
      </p>

      <div className="flex justify-between">
        <Button variant="outline" size="lg" onClick={handleBack}>
          <ArrowLeft className="mr-2 h-4 w-4" /> Back
        </Button>
        <Button size="lg" onClick={handleNext}>
          Continue <ArrowRight className="ml-2 h-4 w-4" />
        </Button>
      </div>
    </>
  );
}
