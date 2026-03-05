import { setRequestLocale } from "next-intl/server";
import { IndustryStep } from "./industry-step";

export default async function IndustryPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <IndustryStep />;
}
