import { setRequestLocale } from "next-intl/server";
import { getTranslations } from "next-intl/server";
import { getLegalHtml } from "@/lib/legal";
import { LegalDocViewer } from "@/components/legal-doc-viewer";
import { notFound } from "next/navigation";

export default async function PrivacyPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("footer");

  let html: string;
  try {
    html = await getLegalHtml("privacy");
  } catch {
    notFound();
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-20 sm:px-6 lg:px-8">
      <div className="mb-8 text-center">
        <h1 className="mb-4 text-4xl font-bold tracking-tight sm:text-5xl">
          {t("privacy")}
        </h1>
        <p className="mx-auto max-w-2xl text-lg text-muted-foreground">
          How we collect, use, and protect your personal information.
        </p>
      </div>
      <LegalDocViewer title={t("privacy")} html={html} />
    </div>
  );
}
