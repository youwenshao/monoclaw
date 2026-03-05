import { setRequestLocale } from "next-intl/server";
import { ConfirmationContent } from "./confirmation-content";

export default async function ConfirmationPage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { locale, id } = await params;
  setRequestLocale(locale);
  return <ConfirmationContent orderId={id} />;
}
