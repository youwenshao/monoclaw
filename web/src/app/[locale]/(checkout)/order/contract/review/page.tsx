import { setRequestLocale } from "next-intl/server";
import { ContractReviewStep } from "./contract-review-step";

export default async function ContractReviewPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <ContractReviewStep />;
}
