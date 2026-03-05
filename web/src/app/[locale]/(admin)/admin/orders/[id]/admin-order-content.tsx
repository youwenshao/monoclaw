"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Link } from "@/i18n/navigation";
import type { Order, OrderAddon, OrderStatusHistory, Device } from "@/types/database";
import { formatHKD } from "@/lib/stripe";
import { HARDWARE_OPTIONS, ORDER_STATUS_FLOW, LLM_MODELS, BUNDLES } from "@/lib/constants";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ArrowLeft, Check, Circle, ChevronRight } from "lucide-react";

export function AdminOrderContent({
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
  const router = useRouter();
  const hw = HARDWARE_OPTIONS.find((h) => h.id === order.hardware_type);
  const currentStepIndex = ORDER_STATUS_FLOW.findIndex((s) => s.status === order.status);
  const nextStatus = ORDER_STATUS_FLOW[currentStepIndex + 1];

  const [updating, setUpdating] = useState(false);

  async function advanceStatus() {
    if (!nextStatus) return;
    setUpdating(true);
    try {
      await fetch("/api/admin/update-status", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          orderId: order.id,
          fromStatus: order.status,
          toStatus: nextStatus.status,
        }),
      });
      router.refresh();
    } finally {
      setUpdating(false);
    }
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-10 sm:px-6 lg:px-8">
      <div className="mb-6">
        <Button variant="ghost" asChild size="sm">
          <Link href={"/admin" as never}>
            <ArrowLeft className="mr-2 h-4 w-4" /> Back to Admin
          </Link>
        </Button>
      </div>

      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Order Management</h1>
          <p className="text-sm text-muted-foreground">
            <code className="rounded bg-muted px-1.5 py-0.5 text-xs">{order.id}</code>
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Badge variant="secondary" className="text-base">
            {ORDER_STATUS_FLOW[currentStepIndex]?.label || order.status}
          </Badge>
          {nextStatus && (
            <Button onClick={advanceStatus} disabled={updating} size="sm">
              Advance to: {nextStatus.label} <ChevronRight className="ml-1 h-4 w-4" />
            </Button>
          )}
        </div>
      </div>

      <div className="mb-8">
        <Card>
          <CardHeader>
            <CardTitle>Status Timeline</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap items-center gap-2">
              {ORDER_STATUS_FLOW.map((step, i) => {
                const isComplete = i <= currentStepIndex;
                return (
                  <div key={step.status} className="flex items-center gap-1">
                    <div
                      className={`flex h-6 w-6 items-center justify-center rounded-full text-xs ${
                        isComplete
                          ? "bg-primary text-primary-foreground"
                          : "border bg-muted text-muted-foreground"
                      }`}
                    >
                      {isComplete ? <Check className="h-3 w-3" /> : i + 1}
                    </div>
                    <span className={`text-xs ${isComplete ? "font-medium" : "text-muted-foreground"}`}>
                      {step.label}
                    </span>
                    {i < ORDER_STATUS_FLOW.length - 1 && (
                      <ChevronRight className="h-3 w-3 text-muted-foreground" />
                    )}
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Order Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Hardware</span>
              <span className="font-medium">{hw?.name || order.hardware_type}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Total</span>
              <span className="font-medium">{formatHKD(order.total_price_hkd)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Stripe</span>
              <span className="font-mono text-xs">{order.stripe_checkout_session_id?.slice(0, 20) || "N/A"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Created</span>
              <span>{new Date(order.created_at).toLocaleString()}</span>
            </div>
            {order.notes && (
              <div>
                <span className="text-muted-foreground">Notes</span>
                <p className="mt-1">{order.notes}</p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Add-ons ({addons.length})</CardTitle>
          </CardHeader>
          <CardContent>
            {addons.length === 0 ? (
              <p className="text-sm text-muted-foreground">None</p>
            ) : (
              <ul className="space-y-2 text-sm">
                {addons.map((addon) => {
                  const bundle = BUNDLES.find((b) => b.id === addon.addon_name);
                  const model = LLM_MODELS.find((m) => m.id === addon.addon_name);
                  return (
                    <li key={addon.id} className="flex justify-between">
                      <span>{bundle?.name || model?.name || addon.addon_name}</span>
                      <span className="text-muted-foreground">{formatHKD(addon.price_hkd)}</span>
                    </li>
                  );
                })}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="mt-8">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Devices ({devices.length})</CardTitle>
          </CardHeader>
          <CardContent>
            {devices.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No devices linked to this order yet. A device will be registered
                when the technician begins provisioning.
              </p>
            ) : (
              <div className="space-y-3">
                {devices.map((device) => (
                  <div
                    key={device.id}
                    className="flex items-center justify-between rounded-lg border p-4"
                  >
                    <div>
                      <p className="font-medium">
                        Serial: {device.serial_number || "Pending"}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        MAC: {device.mac_address || "—"} &middot; Status: {device.setup_status}
                      </p>
                    </div>
                    <Badge variant="secondary">{device.setup_status}</Badge>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {statusHistory.length > 0 && (
        <div className="mt-8">
          <Card>
            <CardHeader>
              <CardTitle>Status History</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {statusHistory.map((entry) => (
                  <div key={entry.id} className="flex items-start gap-3 text-sm">
                    <div className="mt-1 h-2 w-2 rounded-full bg-primary" />
                    <div>
                      <p>
                        {entry.from_status && <><span className="text-muted-foreground">{entry.from_status}</span> → </>}
                        <span className="font-medium">{entry.to_status}</span>
                      </p>
                      {entry.notes && <p className="text-muted-foreground">{entry.notes}</p>}
                      <p className="text-xs text-muted-foreground">
                        {new Date(entry.created_at).toLocaleString()}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
