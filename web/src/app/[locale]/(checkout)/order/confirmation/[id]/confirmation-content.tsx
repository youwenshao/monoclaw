"use client";

import { useEffect } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { useCheckout } from "@/lib/checkout-context";
import { HARDWARE_OPTIONS } from "@/lib/constants";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Check, ExternalLink, ArrowRight } from "lucide-react";

export function ConfirmationContent({ orderId }: { orderId: string }) {
  const t = useTranslations("order");
  const { order, resetOrder } = useCheckout();

  const hardware = HARDWARE_OPTIONS.find((h) => h.id === order.hardwareType);

  useEffect(() => {
    return () => {
      resetOrder();
    };
  }, [resetOrder]);

  return (
    <div className="mx-auto max-w-2xl py-10">
      <div className="mb-8 text-center">
        <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-100 text-green-600">
          <Check className="h-8 w-8" />
        </div>
        <h1 className="mb-2 text-3xl font-bold">{t("confirmation")}</h1>
        <p className="text-muted-foreground">{t("confirmationMessage")}</p>
        <p className="mt-2 text-sm text-muted-foreground">
          Order ID: <code className="rounded bg-muted px-2 py-0.5">{orderId}</code>
        </p>
      </div>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-lg">Next Steps</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-3">
            <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground">
              1
            </div>
            <div>
              <p className="font-medium">{t("appleRedirect")}</p>
              <p className="mb-2 text-sm text-muted-foreground">
                Purchase your {hardware?.name || "Mac"} from Apple Hong Kong.
              </p>
              {hardware && (
                <a
                  href={hardware.appleStoreUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
                >
                  Open Apple Store <ExternalLink className="h-3 w-3" />
                </a>
              )}
            </div>
          </div>

          <div className="flex gap-3">
            <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground">
              2
            </div>
            <div>
              <p className="font-medium">{t("shippingInstructions")}</p>
              <p className="text-sm text-muted-foreground">
                Set the delivery address to: <strong>Sentimento Technologies Limited, Hong Kong</strong>
              </p>
            </div>
          </div>

          <div className="flex gap-3">
            <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-bold text-muted-foreground">
              3
            </div>
            <div>
              <p className="font-medium">We handle the rest</p>
              <p className="text-sm text-muted-foreground">
                We&apos;ll install OpenClaw with all 12 tool suites, run comprehensive tests, and deliver your AI-ready device.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-center">
        <Button asChild>
          <Link href={"/dashboard" as never}>
            Go to Dashboard <ArrowRight className="ml-2 h-4 w-4" />
          </Link>
        </Button>
      </div>
    </div>
  );
}
