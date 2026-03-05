import { setRequestLocale } from "next-intl/server";
import { PricingContent } from "./pricing-content";

export default async function PricingPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  return <PricingContent />;
}
