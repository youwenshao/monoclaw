"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import { useCheckout } from "@/lib/checkout-context";
import { HARDWARE_OPTIONS } from "@/lib/constants";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Check, ExternalLink, ArrowRight, Copy } from "lucide-react";

const DELIVERY_ADDRESS = `Rm 413R, 4/F, Ho Tim Hall
S. H. Ho College, CUHK
Shatin, New Territories
Hong Kong`;

export function ConfirmationContent({ orderId }: { orderId: string }) {
  const t = useTranslations("order");
  const { order, resetOrder } = useCheckout();
  const [copied, setCopied] = useState(false);

  const hardware = HARDWARE_OPTIONS.find((h) => h.id === order.hardwareType);

  useEffect(() => {
    return () => {
      resetOrder();
    };
  }, [resetOrder]);

  const handleCopyAddress = () => {
    navigator.clipboard.writeText(DELIVERY_ADDRESS);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

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
        <CardContent className="space-y-6">
          <div className="flex gap-3">
            <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground">
              1
            </div>
            <div>
              <p className="font-medium">{t("appleRedirect")}</p>
              <p className="mb-2 text-sm text-muted-foreground">
                Purchase your {hardware?.name || "Mac"} from Apple Hong Kong.
              </p>
              <p className="mb-3 text-sm text-muted-foreground">
                {t("step1ConfigReminder", { hardware: hardware?.name || "Mac" })}
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
            <div className="flex-1">
              <p className="font-medium">{t("shippingInstructions")}</p>
              <div className="mt-3 rounded-lg border bg-muted/30 p-4">
                <div className="flex items-start justify-between gap-4">
                  <pre className="font-sans text-sm leading-relaxed text-foreground">
                    {DELIVERY_ADDRESS}
                  </pre>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-8 shrink-0 gap-2"
                    onClick={handleCopyAddress}
                  >
                    {copied ? (
                      <>
                        <Check className="h-3.5 w-3.5" />
                        {t("copied")}
                      </>
                    ) : (
                      <>
                        <Copy className="h-3.5 w-3.5" />
                        {t("copyAddress")}
                      </>
                    )}
                  </Button>
                </div>
              </div>
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
