import { setRequestLocale } from "next-intl/server";
import { createClient, createServiceClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { AdminDashboardContent } from "./admin-dashboard-content";

export const dynamic = "force-dynamic";

export default async function AdminPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
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

  const [ordersRes, devicesRes, summariesRes, addonsRes, profilesRes] = await Promise.all([
    service.from("orders").select("*").order("created_at", { ascending: false }),
    service.from("devices").select("*"),
    service.from("device_test_summaries").select("*"),
    service.from("order_addons").select("*"),
    service.from("profiles").select("id, contact_name, company_name, role"),
  ]);

  const allOrders = ordersRes.data || [];
  const allDevices = devicesRes.data || [];
  const allSummaries = summariesRes.data || [];
  const allAddons = addonsRes.data || [];
  const allProfiles = profilesRes.data || [];

  const profileMap: Record<string, { contact_name: string | null; company_name: string | null }> = {};
  for (const p of allProfiles) {
    profileMap[p.id] = { contact_name: p.contact_name, company_name: p.company_name };
  }

  const addonsByOrder: Record<string, { addon_type: string; addon_name: string; category: string }[]> = {};
  for (const a of allAddons) {
    if (!addonsByOrder[a.order_id]) addonsByOrder[a.order_id] = [];
    addonsByOrder[a.order_id].push(a);
  }

  const totalRevenue = allOrders.reduce((sum: number, o: { total_price_hkd: number }) => sum + o.total_price_hkd, 0);
  const devicesInProgress = allDevices.filter(
    (d: { setup_status: string }) => d.setup_status === "provisioning" || d.setup_status === "testing"
  ).length;
  const avgPassRate = allSummaries.length > 0
    ? Math.round(
        allSummaries.reduce((sum: number, s: { total_tests: number; passed: number }) => sum + (s.total_tests > 0 ? (s.passed / s.total_tests) * 100 : 0), 0) /
          allSummaries.length
      )
    : 0;

  return (
    <AdminDashboardContent
      orders={allOrders}
      profileMap={profileMap}
      addonsByOrder={addonsByOrder}
      totalRevenue={totalRevenue}
      devicesInProgress={devicesInProgress}
      avgPassRate={avgPassRate}
      recentDevices={allDevices.slice(0, 10)}
    />
  );
}
