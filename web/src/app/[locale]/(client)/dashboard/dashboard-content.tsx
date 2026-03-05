"use client";

import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import type { Order, Profile } from "@/types/database";
import { formatHKD } from "@/lib/stripe";
import { HARDWARE_OPTIONS, ORDER_STATUS_FLOW } from "@/lib/constants";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Package, ArrowRight, ShoppingCart } from "lucide-react";

function statusBadgeVariant(status: string): "default" | "secondary" | "destructive" | "outline" {
  if (status === "completed" || status === "delivered") return "default";
  if (status === "pending_payment") return "destructive";
  return "secondary";
}

export function DashboardContent({
  orders,
  profile,
  locale,
}: {
  orders: Order[];
  profile: Profile | null;
  locale: string;
}) {
  const t = useTranslations("dashboard");

  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 lg:px-8">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">{t("title")}</h1>
          {profile?.contact_name && (
            <p className="text-muted-foreground">
              Welcome, {profile.contact_name}
            </p>
          )}
        </div>
        <Button asChild>
          <Link href={"/order" as never}>
            <ShoppingCart className="mr-2 h-4 w-4" /> New Order
          </Link>
        </Button>
      </div>

      <h2 className="mb-4 text-xl font-semibold">{t("orders")}</h2>

      {orders.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16">
            <Package className="mb-4 h-12 w-12 text-muted-foreground" />
            <p className="mb-4 text-muted-foreground">{t("noOrders")}</p>
            <Button asChild>
              <Link href={"/order" as never}>Place Your First Order</Link>
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {orders.map((order) => {
            const hw = HARDWARE_OPTIONS.find((h) => h.id === order.hardware_type);
            const statusConfig = ORDER_STATUS_FLOW.find((s) => s.status === order.status);
            return (
              <Link key={order.id} href={`/dashboard/orders/${order.id}` as never}>
                <Card className="transition-shadow hover:shadow-md">
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <CardTitle className="text-base font-medium">
                      {hw?.name || order.hardware_type}
                    </CardTitle>
                    <Badge variant={statusBadgeVariant(order.status)}>
                      {statusConfig?.label || order.status}
                    </Badge>
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center justify-between text-sm text-muted-foreground">
                      <span>{formatHKD(order.total_price_hkd)}</span>
                      <span>{new Date(order.created_at).toLocaleDateString()}</span>
                      <ArrowRight className="h-4 w-4" />
                    </div>
                  </CardContent>
                </Card>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
