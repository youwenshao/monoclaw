"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import type { Order, OrderAddon, OrderStatusHistory, Device } from "@/types/database";
import { formatHKD } from "@/lib/stripe";
import {
  HARDWARE_OPTIONS,
  ORDER_STATUS_FLOW,
  LLM_MODELS,
  BUNDLES,
  MODEL_CATEGORIES,
  TOOL_SUITES,
} from "@/lib/constants";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Checkbox } from "@/components/ui/checkbox";
import { Check, Circle, ArrowLeft, FileText, Monitor, Brain, Wrench, Package } from "lucide-react";

export function OrderDetailContent({
  order,
  statusHistory,
  addons,
  devices,
}: {
  order: Order;
  statusHistory: OrderStatusHistory[];
  addons: OrderAddon[];
  devices: Device[];
}) {
  const t = useTranslations("dashboard");
  const [confirmLoading, setConfirmLoading] = useState(false);
  const [confirmed, setConfirmed] = useState(order.status === "delivered");
  const [receiptConfirmed, setReceiptConfirmed] = useState(false);
  const hw = HARDWARE_OPTIONS.find((h) => h.id === order.hardware_type);
  const currentStepIndex = ORDER_STATUS_FLOW.findIndex((s) => s.status === order.status);

  async function handleConfirmReceived() {
    setConfirmLoading(true);
    try {
      const res = await fetch("/api/orders/confirm-received", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ order_id: order.id }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || "Failed to confirm");
      }
      setConfirmed(true);
    } catch (err) {
      console.error("Confirm received failed:", err);
    } finally {
      setConfirmLoading(false);
    }
  }

  const bundleAddon = addons.find((a) => a.addon_type === "bundle");
  const modelAddons = addons.filter((a) => a.addon_type === "model");
  const bundleInfo = bundleAddon ? BUNDLES.find((b) => b.id === bundleAddon.addon_name) : null;

  return (
    <div className="mx-auto max-w-4xl px-4 py-10 sm:px-6 lg:px-8">
      <div className="mb-6">
        <Button variant="ghost" asChild size="sm">
          <Link href={"/dashboard" as never}>
            <ArrowLeft className="mr-2 h-4 w-4" /> {t("orders")}
          </Link>
        </Button>
      </div>

      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{t("orderDetails")}</h1>
          <p className="text-sm text-muted-foreground">
            Order ID: <code className="rounded bg-muted px-1.5 py-0.5 text-xs">{order.id}</code>
          </p>
        </div>
        <Badge variant="secondary" className="text-base">
          {ORDER_STATUS_FLOW[currentStepIndex]?.label || order.status}
        </Badge>
      </div>

      {/* Status Timeline */}
      <Card className="mb-8">
        <CardHeader>
          <CardTitle>{t("statusTimeline")}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {ORDER_STATUS_FLOW.map((step, i) => {
              const historyEntry = statusHistory.find((h) => h.to_status === step.status);
              const isComplete = i <= currentStepIndex;
              const isCurrent = i === currentStepIndex;

              return (
                <div key={step.status} className="flex items-start gap-4">
                  <div className="flex flex-col items-center">
                    <div
                      className={`flex h-8 w-8 items-center justify-center rounded-full ${
                        isComplete
                          ? "bg-primary text-primary-foreground"
                          : "border-2 border-muted bg-background"
                      }`}
                    >
                      {isComplete ? (
                        <Check className="h-4 w-4" />
                      ) : (
                        <Circle className="h-3 w-3 text-muted-foreground" />
                      )}
                    </div>
                    {i < ORDER_STATUS_FLOW.length - 1 && (
                      <div
                        className={`my-1 h-6 w-0.5 ${
                          isComplete ? "bg-primary" : "bg-muted"
                        }`}
                      />
                    )}
                  </div>
                  <div className="pb-2">
                    <p
                      className={`text-sm font-medium ${
                        isCurrent ? "text-primary" : isComplete ? "" : "text-muted-foreground"
                      }`}
                    >
                      {step.label}
                    </p>
                    {historyEntry && (
                      <p className="text-xs text-muted-foreground">
                        {new Date(historyEntry.created_at).toLocaleString()}
                        {historyEntry.notes && ` — ${historyEntry.notes}`}
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Mac Login Credentials — shown when shipped or delivered */}
      {(order.status === "shipped" || order.status === "delivered") && (
        <Card className="mb-8 border-blue-500/30 bg-blue-50 dark:bg-blue-950/20">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Monitor className="h-5 w-5 text-blue-600" />
              Your Mac Login Credentials
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Use this password to log into your new Mac for the first time.
            </p>
            <div className="flex flex-col items-center gap-1 rounded-lg border bg-background p-4">
              <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Default Password
              </p>
              <p className="font-mono text-3xl font-bold tracking-[0.3em]">1234</p>
            </div>
            <p className="text-sm font-medium text-orange-600 dark:text-orange-400">
              Please change this password to something unique after your first login.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Confirm Device Received — checkbox-gated */}
      {order.status === "shipped" && !confirmed && (
        <Card className="mb-8 border-primary/30 bg-primary/5">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Package className="h-5 w-5 text-primary" />
              Your device has been shipped!
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Once you have received and logged into your Mac, please confirm below.
            </p>
            <label className="flex items-start gap-3 cursor-pointer">
              <Checkbox
                checked={receiptConfirmed}
                onCheckedChange={(checked) => setReceiptConfirmed(checked === true)}
                className="mt-0.5"
              />
              <span className="text-sm leading-relaxed">
                I hereby declare the confirmation of my receipt of the hardware from Sentimento Technologies Limited and the completion of all outstanding payments.
              </span>
            </label>
            <Button
              onClick={handleConfirmReceived}
              disabled={!receiptConfirmed || confirmLoading}
            >
              {confirmLoading ? "Confirming…" : "Confirm"}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Receipt confirmed — success card */}
      {confirmed && (
        <Card className="mb-8 border-green-500/30 bg-green-50 dark:bg-green-950/20">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Check className="h-5 w-5 text-green-600" />
              Receipt confirmed
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Thank you for confirming. Your Mona agent is ready to use on your Mac.
              If you need help, email{" "}
              <a href="mailto:team@sentimento.dev" className="underline hover:text-foreground">
                team@sentimento.dev
              </a>
            </p>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 md:grid-cols-2">
        {/* Hardware */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Monitor className="h-5 w-5" /> Hardware
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <p className="font-medium">{hw?.name || order.hardware_type}</p>
            {hw && (
              <ul className="space-y-1 text-muted-foreground">
                <li>{hw.specs.chip}</li>
                <li>{hw.specs.ram}</li>
                <li>{hw.specs.baseSsd}</li>
                {hw.specs.display && <li>{hw.specs.display}</li>}
              </ul>
            )}
            {order.apple_order_number && (
              <>
                <Separator />
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Apple Order #</span>
                  <span className="font-mono text-xs">{order.apple_order_number}</span>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        {/* LLM Plan */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Brain className="h-5 w-5" /> LLM Plan
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm">
            {addons.length === 0 ? (
              <p className="text-muted-foreground">API only — no local models</p>
            ) : bundleInfo ? (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <Badge>{bundleInfo.name}</Badge>
                  <span className="text-muted-foreground">{formatHKD(bundleAddon!.price_hkd)}</span>
                </div>
                <p className="text-muted-foreground">{bundleInfo.description}</p>
              </div>
            ) : (
              <div className="space-y-2">
                <p className="font-medium">A la carte ({modelAddons.length} model{modelAddons.length > 1 ? "s" : ""})</p>
                {modelAddons.map((addon) => {
                  const model = LLM_MODELS.find((m) => m.id === addon.addon_name);
                  const cat = MODEL_CATEGORIES.find((c) => c.id === addon.category);
                  return (
                    <div key={addon.id} className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-xs">{cat?.name || addon.category}</Badge>
                        <span>{model ? `${model.name} ${model.parameterSize}` : addon.addon_name}</span>
                      </div>
                      <span className="text-muted-foreground">{formatHKD(addon.price_hkd)}</span>
                    </div>
                  );
                })}
              </div>
            )}
            <Separator className="my-3" />
            <div className="flex justify-between font-medium">
              <span>Total</span>
              <span>{formatHKD(order.total_price_hkd)}</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Supported Tools */}
      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Wrench className="h-5 w-5" /> Supported Tools
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          <p className="text-muted-foreground">
            All {TOOL_SUITES.length} tool suites are pre-installed on your Mac.
            Mona auto-routes requests to the right tool based on context.
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            {TOOL_SUITES.map((suite) => (
              <div key={suite.id}>
                <Badge className="mb-1">{suite.name}</Badge>
                <div className="flex flex-wrap gap-1">
                  {suite.tools.map((tool) => (
                    <Badge key={tool} variant="outline" className="text-xs">{tool}</Badge>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Devices */}
      {devices.length > 0 && (
        <div className="mt-8">
          <h2 className="mb-4 text-xl font-semibold">{t("deviceInfo")}</h2>
          {devices.map((device) => (
            <Card key={device.id} className="mb-4">
              <CardContent className="flex items-center justify-between pt-6">
                <div>
                  <p className="font-medium">Serial: {device.serial_number || "Pending"}</p>
                  <p className="text-sm text-muted-foreground">
                    Status: {device.setup_status}
                  </p>
                </div>
                {(device.setup_status === "passed" || device.setup_status === "testing") && (
                  <Button variant="outline" asChild size="sm">
                    <Link href={`/dashboard/orders/${order.id}/test-report` as never}>
                      <FileText className="mr-2 h-4 w-4" />
                      {t("testReport")}
                    </Link>
                  </Button>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
