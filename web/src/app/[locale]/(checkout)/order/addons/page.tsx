import { setRequestLocale } from "next-intl/server";
import { AddonsStep } from "./addons-step";

export default async function AddonsPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <AddonsStep />;
}
