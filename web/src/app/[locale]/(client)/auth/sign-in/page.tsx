import { setRequestLocale } from "next-intl/server";
import { SignInForm } from "./sign-in-form";

export default async function SignInPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  return (
    <div className="flex min-h-[80vh] items-center justify-center px-4">
      <SignInForm />
    </div>
  );
}
