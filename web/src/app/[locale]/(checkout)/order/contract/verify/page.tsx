import { setRequestLocale } from "next-intl/server";
import { VerifyStep } from "./verify-step";

export default async function VerifyPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <VerifyStep />;
}
