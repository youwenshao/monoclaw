"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Link } from "@/i18n/navigation";
import type { Order, OrderAddon, OrderStatusHistory, Device } from "@/types/database";
import { formatHKD } from "@/lib/stripe";
import {
  HARDWARE_OPTIONS,
  ORDER_STATUS_FLOW,
  LLM_MODELS,
  BUNDLES,
  MODEL_CATEGORIES,
  INDUSTRY_VERTICALS,
  CLIENT_PERSONAS,
} from "@/lib/constants";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { ArrowLeft, Check, ChevronRight, Save, User, Monitor, Brain, Building2, Truck } from "lucide-react";

interface ClientProfile {
  id: string;
  contact_name: string | null;
  company_name: string | null;
  contact_phone: string | null;
  industry: string | null;
  role: string;
  email: string | null;
}

export function AdminOrderContent({
  order,
  clientProfile,
  statusHistory,
  addons,
  devices,
}: {
  order: Order;
  clientProfile: ClientProfile | null;
  statusHistory: OrderStatusHistory[];
  addons: OrderAddon[];
  devices: Device[];
}) {
  const router = useRouter();
  const hw = HARDWARE_OPTIONS.find((h) => h.id === order.hardware_type);
  const currentStepIndex = ORDER_STATUS_FLOW.findIndex((s) => s.status === order.status);
  const nextStatus = ORDER_STATUS_FLOW[currentStepIndex + 1];

  const [updating, setUpdating] = useState(false);
  const [appleOrderNumber, setAppleOrderNumber] = useState(order.apple_order_number || "");
  const [notes, setNotes] = useState(order.notes || "");
  const [saving, setSaving] = useState(false);

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

  async function saveFields() {
    setSaving(true);
    try {
      await fetch(`/api/admin/orders/${order.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ apple_order_number: appleOrderNumber || null, notes: notes || null }),
      });
      router.refresh();
    } finally {
      setSaving(false);
    }
  }

  const industryInfo = INDUSTRY_VERTICALS.find((v) => v.slug === order.industry);
  const personaInfos = (order.personas || [])
    .map((slug) => CLIENT_PERSONAS.find((p) => p.slug === slug))
    .filter(Boolean);

  const bundleAddon = addons.find((a) => a.addon_type === "bundle");
  const modelAddons = addons.filter((a) => a.addon_type === "model");
  const bundleInfo = bundleAddon ? BUNDLES.find((b) => b.id === bundleAddon.addon_name) : null;

  const hwConfig = order.hardware_config as Record<string, string> | null;

  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 lg:px-8">
      <div className="mb-6">
        <Button variant="ghost" asChild size="sm">
          <Link href={"/admin" as never}>
            <ArrowLeft className="mr-2 h-4 w-4" /> Back to Admin
          </Link>
        </Button>
      </div>

      {/* Header */}
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

      {/* Status Timeline */}
      <Card className="mb-8">
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

      {/* Main grid */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* Client Info */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <User className="h-4 w-4" /> Client Info
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Name</span>
              <span className="font-medium">{clientProfile?.contact_name || "—"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Email</span>
              <span className="font-mono text-xs">{clientProfile?.email || "—"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Company</span>
              <span className="font-medium">{clientProfile?.company_name || "—"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Phone</span>
              <span>{clientProfile?.contact_phone || "—"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Client ID</span>
              <span className="font-mono text-xs">{order.client_id.slice(0, 8)}...</span>
            </div>
          </CardContent>
        </Card>

        {/* Hardware & Apple Order */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Monitor className="h-4 w-4" /> Hardware
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Type</span>
              <span className="font-medium">{hw?.name || order.hardware_type}</span>
            </div>
            {hwConfig?.ssd && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">SSD</span>
                <span>{hwConfig.ssd}</span>
              </div>
            )}
            {hwConfig?.color && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Color</span>
                <span>{hwConfig.color}</span>
              </div>
            )}
            {hwConfig?.ethernet && (
              <div className="flex justify-between">
                <span className="text-muted-foreground">Ethernet</span>
                <span>{hwConfig.ethernet}</span>
              </div>
            )}
            <Separator />
            <div>
              <label className="mb-1 block text-muted-foreground">Apple Order Number</label>
              <input
                type="text"
                value={appleOrderNumber}
                onChange={(e) => setAppleOrderNumber(e.target.value)}
                placeholder="e.g. W12345678"
                className="w-full rounded-md border bg-background px-3 py-1.5 text-sm"
              />
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Total</span>
              <span className="font-bold">{formatHKD(order.total_price_hkd)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Stripe</span>
              <span className="font-mono text-xs">{order.stripe_checkout_session_id?.slice(0, 20) || "N/A"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Created</span>
              <span>{new Date(order.created_at).toLocaleString()}</span>
            </div>
          </CardContent>
        </Card>

        {/* LLM Plan */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Brain className="h-4 w-4" /> LLM Plan
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm">
            {addons.length === 0 ? (
              <p className="text-muted-foreground">API only — no local models purchased</p>
            ) : bundleInfo ? (
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <Badge>{bundleInfo.name}</Badge>
                  <span className="text-muted-foreground">{formatHKD(bundleAddon!.price_hkd)}</span>
                </div>
                <p className="text-muted-foreground">{bundleInfo.description}</p>
                <ul className="list-inside list-disc space-y-1 text-muted-foreground">
                  {bundleInfo.features.map((f) => (
                    <li key={f}>{f}</li>
                  ))}
                </ul>
              </div>
            ) : (
              <div className="space-y-2">
                <p className="mb-2 font-medium">A la carte ({modelAddons.length} model{modelAddons.length > 1 ? "s" : ""})</p>
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
          </CardContent>
        </Card>

        {/* Industry & Personas */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Building2 className="h-4 w-4" /> Industry & Personas
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <div>
              <p className="mb-1 text-muted-foreground">Primary Industry</p>
              {industryInfo ? (
                <div>
                  <Badge className="mb-2">{industryInfo.name}</Badge>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {industryInfo.softwareStack.map((tool) => (
                      <Badge key={tool} variant="outline" className="text-xs">{tool}</Badge>
                    ))}
                  </div>
                </div>
              ) : (
                <span className="text-muted-foreground">Not selected</span>
              )}
            </div>
            <Separator />
            <div>
              <p className="mb-1 text-muted-foreground">Persona Add-ons (free)</p>
              {personaInfos.length > 0 ? (
                <div className="space-y-2">
                  {personaInfos.map((persona) => (
                    <div key={persona!.slug}>
                      <Badge variant="secondary" className="mb-1">{persona!.name}</Badge>
                      <div className="flex flex-wrap gap-1">
                        {persona!.softwareStack.map((tool) => (
                          <Badge key={tool} variant="outline" className="text-xs">{tool}</Badge>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <span className="text-muted-foreground">None selected</span>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Notes */}
      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Admin Notes</CardTitle>
        </CardHeader>
        <CardContent>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Internal notes about this order..."
            rows={3}
            className="w-full rounded-md border bg-background px-3 py-2 text-sm"
          />
          <div className="mt-3 flex justify-end">
            <Button onClick={saveFields} disabled={saving} size="sm">
              <Save className="mr-2 h-4 w-4" /> {saving ? "Saving..." : "Save Changes"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Devices */}
      <Card className="mt-6">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Truck className="h-4 w-4" /> Devices ({devices.length})
          </CardTitle>
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
                      MAC: {device.mac_address || "—"} &middot; ID: {device.id.slice(0, 8)}...
                    </p>
                    {device.setup_started_at && (
                      <p className="text-xs text-muted-foreground">
                        Started: {new Date(device.setup_started_at).toLocaleString()}
                      </p>
                    )}
                  </div>
                  <Badge variant="secondary">{device.setup_status}</Badge>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Status History */}
      {statusHistory.length > 0 && (
        <Card className="mt-6">
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
      )}
    </div>
  );
}
