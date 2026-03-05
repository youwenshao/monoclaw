import { setRequestLocale } from "next-intl/server";
import { createClient } from "@/lib/supabase/server";
import { redirect, notFound } from "next/navigation";
import { TestReportContent } from "./test-report-content";

export default async function TestReportPage({
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

  const { data: devices } = await supabase
    .from("devices")
    .select("*")
    .eq("order_id", id);

  const device = devices?.[0];
  if (!device) notFound();

  const { data: testResults } = await supabase
    .from("device_test_results")
    .select("*")
    .eq("device_id", device.id)
    .order("executed_at", { ascending: true });

  const { data: testSummary } = await supabase
    .from("device_test_summaries")
    .select("*")
    .eq("device_id", device.id)
    .order("created_at", { ascending: false })
    .limit(1)
    .single();

  return (
    <TestReportContent
      order={order}
      device={device}
      testResults={testResults || []}
      testSummary={testSummary}
    />
  );
}
