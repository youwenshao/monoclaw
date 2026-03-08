"use client";

import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import type { Order, Device } from "@/types/database";
import { formatHKD } from "@/lib/stripe";
import { ORDER_STATUS_FLOW, BUNDLES } from "@/lib/constants";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { DollarSign, Package, Cpu, Activity } from "lucide-react";

function getLlmPlanLabel(addons: { addon_type: string; addon_name: string; category: string }[] | undefined): string {
  if (!addons || addons.length === 0) return "API only";
  const bundle = addons.find((a) => a.addon_type === "bundle");
  if (bundle) {
    const b = BUNDLES.find((x) => x.id === bundle.addon_name);
    return b?.name || bundle.addon_name;
  }
  return `${addons.length} model${addons.length > 1 ? "s" : ""} (a la carte)`;
}

export function AdminDashboardContent({
  orders,
  profileMap,
  addonsByOrder,
  totalRevenue,
  devicesInProgress,
  avgPassRate,
  recentDevices,
}: {
  orders: Order[];
  profileMap: Record<string, { contact_name: string | null; company_name: string | null }>;
  addonsByOrder: Record<string, { addon_type: string; addon_name: string; category: string }[]>;
  totalRevenue: number;
  devicesInProgress: number;
  avgPassRate: number;
  recentDevices: Device[];
}) {
  const t = useTranslations("admin");

  return (
    <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
      <h1 className="mb-8 text-3xl font-bold">{t("title")}</h1>

      <div className="mb-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t("totalOrders")}</CardTitle>
            <Package className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{orders.length}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t("revenue")}</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{formatHKD(totalRevenue)}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t("devicesInProgress")}</CardTitle>
            <Cpu className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{devicesInProgress}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{t("avgTestPassRate")}</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{avgPassRate}%</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t("orders")}</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Order ID</TableHead>
                <TableHead>Client</TableHead>
                <TableHead>Hardware</TableHead>
                <TableHead>LLM Plan</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Total</TableHead>
                <TableHead>Date</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {orders.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center text-muted-foreground">
                    No orders yet
                  </TableCell>
                </TableRow>
              ) : (
                orders.slice(0, 30).map((order) => {
                  const statusConfig = ORDER_STATUS_FLOW.find((s) => s.status === order.status);
                  const clientProfile = profileMap[order.client_id];
                  const llmPlan = getLlmPlanLabel(addonsByOrder[order.id]);
                  return (
                    <TableRow key={order.id}>
                      <TableCell>
                        <Link
                          href={`/admin/orders/${order.id}` as never}
                          className="text-primary hover:underline"
                        >
                          {order.id.slice(0, 8)}...
                        </Link>
                      </TableCell>
                      <TableCell className="max-w-[140px] truncate">
                        {clientProfile?.contact_name || clientProfile?.company_name || order.client_id.slice(0, 8)}
                      </TableCell>
                      <TableCell>{order.hardware_type === "mac_mini_m4" ? "Mac mini" : "iMac"}</TableCell>
                      <TableCell className="text-xs">{llmPlan}</TableCell>
                      <TableCell>
                        <Badge variant="secondary">
                          {statusConfig?.label || order.status}
                        </Badge>
                      </TableCell>
                      <TableCell>{formatHKD(order.total_price_hkd)}</TableCell>
                      <TableCell>{new Date(order.created_at).toLocaleDateString()}</TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
