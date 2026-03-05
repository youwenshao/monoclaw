import { setRequestLocale } from "next-intl/server";
import { createClient } from "@/lib/supabase/server";
import { redirect, notFound } from "next/navigation";
import { OrderDetailContent } from "./order-detail-content";

export default async function OrderDetailPage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { locale, id } = await params;
  setRequestLocale(locale);

  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect(`/${locale}/auth/sign-in`);

  const { data: order } = await supabase
    .from("orders")
    .select("*")
    .eq("id", id)
    .single();

  if (!order) notFound();

  const { data: statusHistory } = await supabase
    .from("order_status_history")
    .select("*")
    .eq("order_id", id)
    .order("created_at", { ascending: true });

  const { data: addons } = await supabase
    .from("order_addons")
    .select("*")
    .eq("order_id", id);

  const { data: devices } = await supabase
    .from("devices")
    .select("*")
    .eq("order_id", id);

  return (
    <OrderDetailContent
      order={order}
      statusHistory={statusHistory || []}
      addons={addons || []}
      devices={devices || []}
    />
  );
}
