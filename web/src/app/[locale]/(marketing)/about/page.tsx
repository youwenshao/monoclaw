import { setRequestLocale } from "next-intl/server";
import { COMPANY } from "@/lib/constants";
import { Building, Globe, Cpu, ExternalLink } from "lucide-react";

export default async function AboutPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  return (
    <div className="mx-auto max-w-4xl px-4 py-20 sm:px-6 lg:px-8">
      <div className="mb-16 text-center">
        <h1 className="mb-4 text-4xl font-bold tracking-tight sm:text-5xl">
          About {COMPANY.name}
        </h1>
        <p className="mx-auto max-w-2xl text-lg text-muted-foreground">
          Deploying AI employees on local hardware for Hong Kong businesses.
        </p>
      </div>

      <div className="mb-16 space-y-12">
        {/* Mission */}
        <section className="rounded-2xl border p-8">
          <div className="mb-4 flex items-center gap-3">
            <div className="rounded-lg bg-primary/10 p-2 text-primary">
              <Cpu className="h-6 w-6" />
            </div>
            <h2 className="text-2xl font-semibold">Our Mission</h2>
          </div>
          <p className="leading-relaxed text-muted-foreground">
            We believe every Hong Kong business deserves an AI-powered virtual
            employee that runs entirely on local hardware. No cloud dependency,
            no data leaving your office, no recurring API fees. MonoClaw deploys
            Mona — your dedicated AI assistant — on Apple Silicon Macs, pre-loaded
            with 12 pre-installed tool suites covering Hong Kong&apos;s key industries
            and professional needs.
          </p>
        </section>

        {/* Company */}
        <section className="rounded-2xl border p-8">
          <div className="mb-4 flex items-center gap-3">
            <div className="rounded-lg bg-primary/10 p-2 text-primary">
              <Building className="h-6 w-6" />
            </div>
            <h2 className="text-2xl font-semibold">The Company</h2>
          </div>
          <div className="space-y-3 text-muted-foreground">
            <p>
              <span className="font-medium text-foreground">
                {COMPANY.legalName}
              </span>{" "}
              is the parent company behind MonoClaw. Based in{" "}
              {COMPANY.location}, we specialise in deploying practical AI
              solutions for small and medium businesses across the city.
            </p>
            <div className="flex flex-col gap-2 pt-2 sm:flex-row sm:gap-6">
              <a
                href={`https://${COMPANY.website}`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 font-medium text-primary hover:underline"
              >
                <Globe className="h-4 w-4" />
                {COMPANY.website}
                <ExternalLink className="h-3 w-3" />
              </a>
            </div>
          </div>
        </section>

        {/* OpenClaw */}
        <section className="rounded-2xl border p-8">
          <div className="mb-4 flex items-center gap-3">
            <div className="rounded-lg bg-primary/10 p-2 text-primary">
              <Globe className="h-6 w-6" />
            </div>
            <h2 className="text-2xl font-semibold">Powered by OpenClaw</h2>
          </div>
          <div className="space-y-3 text-muted-foreground">
            <p>
              MonoClaw is built on top of{" "}
              <span className="font-medium text-foreground">OpenClaw</span>, our
              open-source agent platform. OpenClaw provides the runtime, model
              management, and tool framework that powers Mona and all
              tool suites.
            </p>
            <a
              href={`https://${COMPANY.openclawWebsite}`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 font-medium text-primary hover:underline"
            >
              <Globe className="h-4 w-4" />
              {COMPANY.openclawWebsite}
              <ExternalLink className="h-3 w-3" />
            </a>
          </div>
        </section>
      </div>
    </div>
  );
}
