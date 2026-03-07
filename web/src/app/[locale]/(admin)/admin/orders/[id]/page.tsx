import { setRequestLocale } from "next-intl/server";
import { createClient, createServiceClient } from "@/lib/supabase/server";
import { redirect, notFound } from "next/navigation";
import { AdminOrderContent } from "./admin-order-content";

export const dynamic = "force-dynamic";

export default async function AdminOrderDetailPage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { locale, id } = await params;
  setRequestLocale(locale);

  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect(`/${locale}/auth/sign-in`);

  const service = await createServiceClient();
  const { data: profile } = await service
    .from("profiles")
    .select("role")
    .eq("id", user.id)
    .maybeSingle();

  const role = profile?.role?.toString?.().trim().toLowerCase();
  if (role !== "admin" && role !== "technician") {
    redirect(`/${locale}/dashboard`);
  }

  const { data: order } = await service
    .from("orders")
    .select("*")
    .eq("id", id)
    .single();

  if (!order) notFound();

  const [statusHistoryRes, addonsRes, devicesRes, clientProfileRes] = await Promise.all([
    service.from("order_status_history").select("*").eq("order_id", id).order("created_at", { ascending: true }),
    service.from("order_addons").select("*").eq("order_id", id),
    service.from("devices").select("*").eq("order_id", id),
    service.from("profiles").select("id, contact_name, company_name, contact_phone, industry, role").eq("id", order.client_id).maybeSingle(),
  ]);

  let clientEmail: string | null = null;
  if (order.client_id && order.client_id !== "00000000-0000-0000-0000-000000000000") {
    const { data: authUser } = await service.auth.admin.getUserById(order.client_id);
    clientEmail = authUser?.user?.email ?? null;
  }

  return (
    <AdminOrderContent
      order={order}
      clientProfile={clientProfileRes.data ? { ...clientProfileRes.data, email: clientEmail } : null}
      statusHistory={statusHistoryRes.data || []}
      addons={addonsRes.data || []}
      devices={devicesRes.data || []}
    />
  );
}
