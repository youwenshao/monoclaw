import { useTranslations } from "next-intl";
import { setRequestLocale } from "next-intl/server";

export default async function HomePage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  return <LandingContent />;
}

function LandingContent() {
  const t = useTranslations("hero");

  return (
    <div className="flex min-h-[80vh] flex-col items-center justify-center px-4 text-center">
      <h1 className="mb-6 text-5xl font-bold tracking-tight sm:text-7xl">
        {t("title")}
      </h1>
      <p className="mb-10 max-w-2xl text-lg text-muted-foreground sm:text-xl">
        {t("subtitle")}
      </p>
      <div className="flex gap-4">
        <a
          href="/order"
          className="rounded-lg bg-primary px-8 py-3 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
        >
          {t("cta")}
        </a>
        <a
          href="/pricing"
          className="rounded-lg border border-border px-8 py-3 text-sm font-medium transition-colors hover:bg-accent"
        >
          {t("secondaryCta")}
        </a>
      </div>
    </div>
  );
}
