import { setRequestLocale } from "next-intl/server";
import { SignatureStep } from "./signature-step";

export default async function SignPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <SignatureStep />;
}
