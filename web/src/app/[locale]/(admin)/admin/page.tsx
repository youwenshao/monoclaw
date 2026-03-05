import { setRequestLocale } from "next-intl/server";
import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import { AdminDashboardContent } from "./admin-dashboard-content";

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

  const { data: profile } = await supabase
    .from("profiles")
    .select("*")
    .eq("id", user.id)
    .single();

  if (profile?.role !== "admin" && profile?.role !== "technician") {
    redirect(`/${locale}/dashboard`);
  }

  const { data: orders } = await supabase
    .from("orders")
    .select("*")
    .order("created_at", { ascending: false });

  const { data: devices } = await supabase
    .from("devices")
    .select("*");

  const { data: testSummaries } = await supabase
    .from("device_test_summaries")
    .select("*");

  const allOrders = orders || [];
  const allDevices = devices || [];
  const allSummaries = testSummaries || [];

  const totalRevenue = allOrders.reduce((sum, o) => sum + o.total_price_hkd, 0);
  const devicesInProgress = allDevices.filter(
    (d) => d.setup_status === "provisioning" || d.setup_status === "testing"
  ).length;
  const avgPassRate = allSummaries.length > 0
    ? Math.round(
        allSummaries.reduce((sum, s) => sum + (s.total_tests > 0 ? (s.passed / s.total_tests) * 100 : 0), 0) /
          allSummaries.length
      )
    : 0;

  return (
    <AdminDashboardContent
      orders={allOrders}
      totalRevenue={totalRevenue}
      devicesInProgress={devicesInProgress}
      avgPassRate={avgPassRate}
      recentDevices={allDevices.slice(0, 10)}
    />
  );
}
