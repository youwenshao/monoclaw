"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import { useCheckout } from "@/lib/checkout-context";
import { createClient } from "@/lib/supabase/client";
import {
  HARDWARE_OPTIONS,
  SOFTWARE_BASE_PRICE_HKD,
  LLM_MODELS,
  MODEL_CATEGORIES,
  BUNDLES,
  TOOL_SUITES,
} from "@/lib/constants";
import { formatHKD } from "@/lib/stripe";
import { CheckoutSteps } from "@/components/checkout-steps";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  ArrowLeft,
  CreditCard,
  Loader2,
  LogIn,
  FileSignature,
} from "lucide-react";
import type { User } from "@supabase/supabase-js";

export function ReviewStep() {
  const t = useTranslations("order");
  const { order, signingComplete, setCurrentStep } = useCheckout();
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [user, setUser] = useState<User | null>(null);
  const [authChecked, setAuthChecked] = useState(false);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getUser().then(({ data }) => {
      setUser(data.user);
      setAuthChecked(true);
    });
  }, []);

  const hardware = HARDWARE_OPTIONS.find((h) => h.id === order.hardwareType);
  const bundle = order.addons.bundle
    ? BUNDLES.find((b) => b.id === order.addons.bundle)
    : null;
  const selectedModels = order.addons.models
    .map((id) => LLM_MODELS.find((m) => m.id === id))
    .filter(Boolean);

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

  function handleSignIn() {
    const supabase = createClient();
    supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: `${window.location.origin}/auth/callback?next=${encodeURIComponent(`/${document.documentElement.lang || "en"}/order/review`)}`,
      },
    });
  }

  function handleContinueToContract() {
    setCurrentStep(5);
    router.push("/order/contract" as never);
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
          signingSessionId: order.signingSessionId,
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

  function renderActionButton() {
    if (!authChecked) {
      return (
        <Button size="lg" disabled>
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          Checking...
        </Button>
      );
    }

    if (!user) {
      return (
        <Button size="lg" onClick={handleSignIn}>
          <LogIn className="mr-2 h-4 w-4" />
          Sign in to Continue
        </Button>
      );
    }

    if (!signingComplete) {
      return (
        <Button size="lg" onClick={handleContinueToContract}>
          <FileSignature className="mr-2 h-4 w-4" />
          Continue to Contract
        </Button>
      );
    }

    return (
      <Button
        size="lg"
        onClick={handleCheckout}
        disabled={loading || !order.hardwareType}
      >
        {loading ? (
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        ) : (
          <CreditCard className="mr-2 h-4 w-4" />
        )}
        {t("pay")} &middot; {formatHKD(softwareTotal)}
      </Button>
    );
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
              <span className="font-medium">
                {formatHKD(SOFTWARE_BASE_PRICE_HKD)}
              </span>
            </div>
            {bundle && (
              <div className="flex items-center justify-between">
                <span>{bundle.name}</span>
                <span className="font-medium">
                  {formatHKD(bundle.priceHkd)}
                </span>
              </div>
            )}
            {!bundle &&
              selectedModels.length > 0 &&
              selectedModels.map((model) => {
                if (!model) return null;
                const cat = MODEL_CATEGORIES.find(
                  (c) => c.id === model.category,
                );
                return (
                  <div
                    key={model.id}
                    className="flex items-center justify-between text-sm"
                  >
                    <span>
                      {model.name} {model.parameterSize}
                    </span>
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
            <CardTitle className="text-lg">Included Tool Suites</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="mb-3 text-sm text-muted-foreground">
              All {TOOL_SUITES.length} tool suites are included with every Mona
              Mac. Mona auto-routes your requests to the right tool.
            </p>
            <div className="flex flex-wrap gap-1.5">
              {TOOL_SUITES.map((suite) => (
                <Badge key={suite.id} variant="secondary" className="text-xs">
                  {suite.name}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {!user && authChecked && (
        <Card className="mt-6 border-amber-500/30 bg-amber-50 dark:bg-amber-950/20">
          <CardContent className="pt-6">
            <p className="text-sm text-amber-800 dark:text-amber-200">
              You must sign in before proceeding to the contract and payment
              stage. Your order configuration will be preserved.
            </p>
          </CardContent>
        </Card>
      )}

      {user && !signingComplete && authChecked && (
        <Card className="mt-6 border-blue-500/30 bg-blue-50 dark:bg-blue-950/20">
          <CardContent className="pt-6">
            <p className="text-sm text-blue-800 dark:text-blue-200">
              Before payment, you must review and sign the service agreement.
              This is a legally binding contract under the Electronic
              Transactions Ordinance (Cap. 553).
            </p>
          </CardContent>
        </Card>
      )}

      <div className="mt-8 flex justify-between">
        <Button variant="outline" size="lg" onClick={handleBack}>
          <ArrowLeft className="mr-2 h-4 w-4" /> Back
        </Button>
        {renderActionButton()}
      </div>
    </>
  );
}
