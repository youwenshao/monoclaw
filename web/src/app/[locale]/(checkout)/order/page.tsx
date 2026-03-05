import { setRequestLocale } from "next-intl/server";
import { HardwareStep } from "./hardware-step";

export default async function OrderPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <HardwareStep />;
}
