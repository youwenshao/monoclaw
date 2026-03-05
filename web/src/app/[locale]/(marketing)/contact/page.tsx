import { setRequestLocale } from "next-intl/server";
import { COMPANY, INDUSTRY_VERTICALS } from "@/lib/constants";
import { Button } from "@/components/ui/button";
import { Mail, Globe, MapPin } from "lucide-react";

export default async function ContactPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);

  return (
    <div className="mx-auto max-w-5xl px-4 py-20 sm:px-6 lg:px-8">
      <div className="mb-16 text-center">
        <h1 className="mb-4 text-4xl font-bold tracking-tight sm:text-5xl">
          Get in Touch
        </h1>
        <p className="mx-auto max-w-2xl text-lg text-muted-foreground">
          Have questions about MonoClaw? We&apos;d love to hear from you.
        </p>
      </div>

      <div className="grid gap-12 lg:grid-cols-5">
        {/* Contact Info */}
        <div className="space-y-8 lg:col-span-2">
          <div>
            <h2 className="mb-6 text-2xl font-semibold">
              {COMPANY.legalName}
            </h2>
            <div className="space-y-4">
              <div className="flex items-center gap-3 text-muted-foreground">
                <Mail className="h-5 w-5 shrink-0 text-primary" />
                <a
                  href="mailto:hello@monoclaw.app"
                  className="hover:text-foreground hover:underline"
                >
                  hello@monoclaw.app
                </a>
              </div>
              <div className="flex items-center gap-3 text-muted-foreground">
                <Globe className="h-5 w-5 shrink-0 text-primary" />
                <a
                  href={`https://${COMPANY.website}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hover:text-foreground hover:underline"
                >
                  {COMPANY.website}
                </a>
              </div>
              <div className="flex items-center gap-3 text-muted-foreground">
                <MapPin className="h-5 w-5 shrink-0 text-primary" />
                <span>{COMPANY.location}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Contact Form */}
        <div className="rounded-2xl border p-8 lg:col-span-3">
          <h2 className="mb-6 text-xl font-semibold">Send us a message</h2>
          <form className="space-y-5" onSubmit={undefined}>
            <div className="grid gap-5 sm:grid-cols-2">
              <div>
                <label
                  htmlFor="name"
                  className="mb-1.5 block text-sm font-medium"
                >
                  Name
                </label>
                <input
                  type="text"
                  id="name"
                  name="name"
                  placeholder="Your name"
                  className="w-full rounded-md border bg-background px-3 py-2 text-sm outline-none ring-offset-background placeholder:text-muted-foreground focus:ring-2 focus:ring-ring focus:ring-offset-2"
                />
              </div>
              <div>
                <label
                  htmlFor="email"
                  className="mb-1.5 block text-sm font-medium"
                >
                  Email
                </label>
                <input
                  type="email"
                  id="email"
                  name="email"
                  placeholder="you@company.com"
                  className="w-full rounded-md border bg-background px-3 py-2 text-sm outline-none ring-offset-background placeholder:text-muted-foreground focus:ring-2 focus:ring-ring focus:ring-offset-2"
                />
              </div>
            </div>

            <div>
              <label
                htmlFor="company"
                className="mb-1.5 block text-sm font-medium"
              >
                Company
              </label>
              <input
                type="text"
                id="company"
                name="company"
                placeholder="Your company name"
                className="w-full rounded-md border bg-background px-3 py-2 text-sm outline-none ring-offset-background placeholder:text-muted-foreground focus:ring-2 focus:ring-ring focus:ring-offset-2"
              />
            </div>

            <div>
              <label
                htmlFor="industry"
                className="mb-1.5 block text-sm font-medium"
              >
                Industry
              </label>
              <select
                id="industry"
                name="industry"
                className="w-full rounded-md border bg-background px-3 py-2 text-sm outline-none ring-offset-background focus:ring-2 focus:ring-ring focus:ring-offset-2"
                defaultValue=""
              >
                <option value="" disabled>
                  Select your industry
                </option>
                {INDUSTRY_VERTICALS.map((v) => (
                  <option key={v.slug} value={v.slug}>
                    {v.name}
                  </option>
                ))}
                <option value="other">Other</option>
              </select>
            </div>

            <div>
              <label
                htmlFor="message"
                className="mb-1.5 block text-sm font-medium"
              >
                Message
              </label>
              <textarea
                id="message"
                name="message"
                rows={5}
                placeholder="Tell us how we can help..."
                className="w-full rounded-md border bg-background px-3 py-2 text-sm outline-none ring-offset-background placeholder:text-muted-foreground focus:ring-2 focus:ring-ring focus:ring-offset-2"
              />
            </div>

            <Button type="button" size="lg" className="w-full">
              Send Message
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
