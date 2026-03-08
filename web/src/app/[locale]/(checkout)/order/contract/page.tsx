import { setRequestLocale } from "next-intl/server";
import { ContractIdentityStep } from "./contract-identity-step";

export default async function ContractPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <ContractIdentityStep />;
}
