import { setRequestLocale } from "next-intl/server";
import { ReviewStep } from "./review-step";

export default async function ReviewPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <ReviewStep />;
}
